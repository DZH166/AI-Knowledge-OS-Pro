from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.api.routes_optimizer import get_agent_policy_optimizer
from app.db.session import Base, create_database_engine
from app.main import app
from app.models.agent_policy import AgentPolicyVersion
from app.modules.agent_policy.config import RetrievalPolicyConfig, canonical_policy_json, policy_fingerprint
from app.modules.agent_policy_optimizer.contracts import (
    ScoreWeights,
    SearchSpace,
    SearchSpaceBound,
    StudyObjective,
)
from app.modules.agent_policy_optimizer.service import SqlAgentPolicyOptimizer

from tests.test_v5_4a_optimizer_sql import (
    NOW,
    SPACE,
    WEIGHTS,
    _recording_executor,
    _study_command,
    DEFAULT_POLICY_ID,
)

VALID_CONVERT_BODY = {"schema_version": 1, "request_id": "api-convert-1"}


@pytest.fixture()
def loop_api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    engine = create_database_engine(f"sqlite:///{(tmp_path / 'loop-api.db').as_posix()}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    config = RetrievalPolicyConfig()
    with factory.begin() as session:
        session.add(
            AgentPolicyVersion(
                id=DEFAULT_POLICY_ID,
                policy_key="default-research",
                version=1,
                label="Balanced evidence retrieval",
                status="active",
                config_schema_version=1,
                config_json=canonical_policy_json(config),
                config_sha256=policy_fingerprint(config),
                base_policy_id=None,
                created_by="system:test",
                has_been_active=1,
            )
        )
    optimizer = SqlAgentPolicyOptimizer(
        factory,
        clock=lambda: NOW,
        lease_seconds=900,
        evaluation_lease_seconds=900,
    )
    app.dependency_overrides[get_agent_policy_optimizer] = lambda: optimizer
    client = TestClient(app, raise_server_exceptions=False)
    yield client, optimizer, factory
    app.dependency_overrides.pop(get_agent_policy_optimizer, None)
    engine.dispose()


def _data(response):
    payload = response.json()
    assert payload["success"] is True, payload
    return payload["data"]


def _post(client: TestClient, path: str, payload) -> object:
    return client.post(path, content=json.dumps(payload), headers={"Content-Type": "application/json"})


def _completed_study(client: TestClient, optimizer, factory) -> tuple[str, str]:
    from app.modules.agent_policy_optimizer.contracts import ExecuteTrial

    receipt = optimizer.submit(
        _study_command(
            request_id="api-loop-study",
            label="API loop study",
            base_policy_id=DEFAULT_POLICY_ID,
            objective=StudyObjective.BALANCED,
            max_candidates=2,
            max_evaluations=2,
            search_space=SPACE,
            weights=WEIGHTS,
            seed=42,
        )
    )
    study_id = receipt["study_id"]
    optimizer.start(study_id)
    with factory() as session:
        from app.models.optimizer import OptimizationTrial as TrialRow
        from sqlalchemy import select

        trial_ids = session.scalars(
            select(TrialRow.id).where(TrialRow.study_id == study_id).order_by(TrialRow.ordinal)
        ).all()
    for trial_id in trial_ids:
        optimizer.execute(ExecuteTrial(trial_id=trial_id, worker_id="worker:test"), _recording_executor())
    winner = _data(client.get(f"/api/v1/optimizer/studies/{study_id}/pareto"))["items"][0]["trial_id"]
    _data(client.get(f"/api/v1/optimizer/studies/{study_id}/recommendation"))
    return study_id, winner


def test_convert_draft_endpoint_creates_draft_and_diff_works(loop_api) -> None:
    client, optimizer, factory = loop_api
    study_id, trial_id = _completed_study(client, optimizer, factory)

    response = _post(
        client,
        f"/api/v1/optimizer/studies/{study_id}/recommendation/{trial_id}/convert-draft",
        VALID_CONVERT_BODY,
    )
    assert response.status_code == 200, response.text
    body = _data(response)
    assert body["status"] == "draft"
    assert body["policy_config_sha256"]

    trial_detail = _data(client.get(f"/api/v1/optimizer/trials/{trial_id}"))
    assert trial_detail["draft_policy_id"] == body["policy_id"]

    diff = _data(client.get(f"/api/v1/optimizer/studies/{study_id}/trials/{trial_id}/diff"))
    assert diff["trial_id"] == trial_id
    assert diff["active_policy_id"] == DEFAULT_POLICY_ID

    # Active policy unchanged: still the baseline (query the same isolated DB).
    from app.models.agent_policy import AgentPolicyVersion as PolicyRow
    from sqlalchemy import select as _select

    with factory() as session:
        actives = session.scalars(
            _select(PolicyRow).where(PolicyRow.status == "active")
        ).all()
        assert len(actives) == 1 and actives[0].id == DEFAULT_POLICY_ID
        drafts = session.scalars(
            _select(PolicyRow).where(PolicyRow.status == "draft")
        ).all()
        assert len(drafts) == 1 and drafts[0].config_sha256 == body["policy_config_sha256"]

    # Idempotent: different request_id returns the same draft.
    again = _post(
        client,
        f"/api/v1/optimizer/studies/{study_id}/recommendation/{trial_id}/convert-draft",
        {"schema_version": 1, "request_id": "api-convert-2"},
    )
    assert _data(again)["policy_id"] == body["policy_id"]
    assert _data(again)["replayed"] is True


def test_convert_draft_rejects_bad_inputs(loop_api) -> None:
    client, optimizer, factory = loop_api
    study_id, trial_id = _completed_study(client, optimizer, factory)

    response = _post(
        client,
        f"/api/v1/optimizer/studies/{study_id}/recommendation/{trial_id}/convert-draft",
        {**VALID_CONVERT_BODY, "unexpected": 1},
    )
    assert response.status_code == 422

    response = _post(
        client,
        f"/api/v1/optimizer/studies/{study_id}/recommendation/{trial_id}/convert-draft",
        {"schema_version": 1, "request_id": True},
    )
    assert response.status_code == 422

    response = _post(
        client,
        f"/api/v1/optimizer/studies/{study_id}/recommendation/{trial_id}/convert-draft",
        {"schema_version": 1, "request_id": "bad-label", "label": "api_key=sk-abcdefgh12345678"},
    )
    assert response.status_code == 422

    response = client.get(f"/api/v1/optimizer/studies/{study_id}/trials/{trial_id}/diff")
    assert response.status_code == 200


def test_fail_study_endpoint_and_retry_endpoint(loop_api) -> None:
    client, optimizer, factory = loop_api
    receipt = optimizer.submit(
        _study_command(
            request_id="api-fail-study",
            label="API fail study",
            base_policy_id=DEFAULT_POLICY_ID,
            objective=StudyObjective.BALANCED,
            max_candidates=3,
            max_evaluations=3,
            search_space=SPACE,
            weights=WEIGHTS,
            seed=11,
        )
    )
    study_id = receipt["study_id"]
    optimizer.start(study_id)

    response = _post(client, f"/api/v1/optimizer/studies/{study_id}/fail", {"schema_version": 1})
    assert response.status_code == 200
    assert _data(response)["status"] == "failed"

    again = _post(client, f"/api/v1/optimizer/studies/{study_id}/fail", {"schema_version": 1})
    assert again.status_code == 200
    assert _data(again)["cancelled"] is False

    response = _post(client, f"/api/v1/optimizer/studies/{study_id}/fail", {"schema_version": 1, "reason": True})
    assert response.status_code == 422

    response = _post(
        client,
        f"/api/v1/optimizer/studies/{study_id}/fail",
        {"schema_version": 1, "reason": "x" * 201},
    )
    assert response.status_code == 422

    response = _post(
        client,
        f"/api/v1/optimizer/studies/{study_id}/recommendation/nonexistent/convert-draft",
        {"schema_version": 1, "request_id": "bad id with spaces"},
    )
    assert response.status_code == 422
