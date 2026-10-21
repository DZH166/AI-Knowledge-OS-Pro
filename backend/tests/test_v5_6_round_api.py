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
from app.models.optimizer import OptimizationTrial as TrialRow
from app.modules.agent_policy.config import RetrievalPolicyConfig, canonical_policy_json, policy_fingerprint
from app.modules.agent_policy_optimizer.contracts import (
    ExecuteTrial,
    StudyCommand,
    StudyObjective,
)
from app.modules.agent_policy_optimizer.service import SqlAgentPolicyOptimizer

from tests.test_v5_4a_optimizer_sql import (
    DEFAULT_POLICY_ID,
    NOW,
    SPACE,
    WEIGHTS,
    _recording_executor,
)


@pytest.fixture()
def loop_api(tmp_path: Path):
    engine = create_database_engine(f"sqlite:///{(tmp_path / 'round-api.db').as_posix()}")
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


def _completed_study(optimizer, factory) -> tuple[str, list[str]]:
    receipt = optimizer.submit(
        StudyCommand(
            request_id="api-round-study",
            label="API round study",
            base_policy_id=DEFAULT_POLICY_ID,
            objective=StudyObjective.BALANCED,
            max_candidates=6,
            max_evaluations=9,
            search_space=SPACE,
            weights=WEIGHTS,
            seed=42,
        )
    )
    study_id = receipt["study_id"]
    optimizer.start(study_id)
    with factory() as session:
        trial_ids = session.scalars(
            select(TrialRow.id).where(TrialRow.study_id == study_id).order_by(TrialRow.ordinal)
        ).all()
    for trial_id in trial_ids:
        optimizer.execute(ExecuteTrial(trial_id=trial_id, worker_id="worker:test"), _recording_executor())
    return study_id, list(trial_ids)


from sqlalchemy import select  # noqa: E402


def test_next_round_endpoint_roundtrip_and_categories(loop_api) -> None:
    client, optimizer, factory = loop_api
    study_id, trial_ids = _completed_study(optimizer, factory)

    response = _post(client, f"/api/v1/optimizer/studies/{study_id}/next-round", {"schema_version": 1, "request_id": "nr-1"})
    assert response.status_code == 200, response.text
    body = _data(response)
    assert body["round_no"] == 2
    assert body["created"] >= 1

    replay = _post(client, f"/api/v1/optimizer/studies/{study_id}/next-round", {"schema_version": 1, "request_id": "nr-1"})
    assert _data(replay)["replayed"] is True
    assert _data(replay)["created"] == body["created"]

    detail = _data(client.get(f"/api/v1/optimizer/studies/{study_id}"))
    assert detail["status"] == "running"

    categories = _data(
        client.get(f"/api/v1/optimizer/studies/{study_id}/trials/{trial_ids[0]}/categories")
    )
    assert categories["trial_id"] == trial_ids[0]
    assert len(categories["items"]) == 7
    row = categories["items"][0]
    assert row["case_count"] >= 1
    assert 0.0 <= row["pass_rate_left"] <= 1.0
    assert 0.0 <= row["pass_rate_right"] <= 1.0
    assert row["verdict"] in {"improved", "regressed", "tied"}


def test_next_round_endpoint_validation_and_errors(loop_api) -> None:
    client, optimizer, factory = loop_api
    study_id, trial_ids = _completed_study(optimizer, factory)

    response = _post(client, f"/api/v1/optimizer/studies/{study_id}/next-round", {"schema_version": 1, "request_id": "nr-bad", "extra": 1})
    assert response.status_code == 422

    response = _post(client, f"/api/v1/optimizer/studies/{study_id}/next-round", {"schema_version": 1, "request_id": True})
    assert response.status_code == 422

    missing = client.get(f"/api/v1/optimizer/studies/{study_id}/trials/nope/categories")
    assert missing.status_code == 404

    # External provider calls remain zero across the flow.
    with factory() as session:
        for trial in session.scalars(select(TrialRow).where(TrialRow.study_id == study_id)):
            assert trial.external_provider_calls == 0


def test_create_study_with_warm_start_via_api(loop_api) -> None:
    client, optimizer, factory = loop_api
    study_id, _ = _completed_study(optimizer, factory)

    body = {
        "schema_version": 1,
        "request_id": "api-warm-1",
        "label": "Warm started",
        "base_policy_id": DEFAULT_POLICY_ID,
        "objective": "balanced",
        "max_candidates": 2,
        "max_evaluations": 6,
        "search_space": {
            "factual_top_k": {"minimum": 4, "maximum": 16},
            "comparative_top_k": {"minimum": 6, "maximum": 20},
            "temporal_top_k": {"minimum": 4, "maximum": 18},
            "minimum_score_millis": {"minimum": 0, "maximum": 200},
            "max_hits_per_source": {"minimum": 1, "maximum": 6},
            "neighbor_before": {"minimum": 0, "maximum": 2},
            "neighbor_after": {"minimum": 0, "maximum": 2},
        },
        "weights": {"quality_weight_permille": 700, "cost_weight_permille": 300},
        "seed": 42,
        "warm_start_study_id": study_id,
    }
    response = _post(client, "/api/v1/optimizer/studies", body)
    assert response.status_code == 201, response.text
    created = _data(response)["study_id"]
    detail = _data(client.get(f"/api/v1/optimizer/studies/{created}"))
    assert detail["round_no"] == 2

    missing = _post(client, "/api/v1/optimizer/studies", {**body, "request_id": "api-warm-2", "warm_start_study_id": "study-none"})
    assert missing.status_code == 404
