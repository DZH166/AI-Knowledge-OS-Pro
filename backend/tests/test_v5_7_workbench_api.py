from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.api.routes_optimizer import get_agent_policy_optimizer
from app.modules.agent_control.contracts import GetRunTrace
from app.modules.agent_control.service import SqlAgentControl
from app.modules.agent_run_share.service import SqlAgentRunShare
from app.modules.agent_run_share.wiring import get_agent_run_share
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
from app.models.agent_run import AgentRun
from app.models.knowledge_space import KnowledgeSpace
from sqlalchemy import select


@pytest.fixture()
def workbench_api(tmp_path: Path):
    engine = create_database_engine(f"sqlite:///{(tmp_path / 'workbench-api.db').as_posix()}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    config = RetrievalPolicyConfig()
    with factory.begin() as session:
        session.add(KnowledgeSpace(id=99, name="Workbench", description="api share tests"))
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
    share = SqlAgentRunShare(
        factory,
        clock=lambda: NOW,
        trace_reader=lambda run_id: SqlAgentControl(factory).inspect(GetRunTrace(run_id)),
    )
    app.dependency_overrides[get_agent_policy_optimizer] = lambda: optimizer
    app.dependency_overrides[get_agent_run_share] = lambda: share
    client = TestClient(app, raise_server_exceptions=False)
    yield client, optimizer, factory
    app.dependency_overrides.pop(get_agent_policy_optimizer, None)
    app.dependency_overrides.pop(get_agent_run_share, None)
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
            request_id="api-wb-study",
            label="API workbench study",
            base_policy_id=DEFAULT_POLICY_ID,
            objective=StudyObjective.BALANCED,
            max_candidates=3,
            max_evaluations=6,
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
    optimizer.inspect_recommendation(study_id)
    return study_id, list(trial_ids)


def test_overview_endpoint(workbench_api) -> None:
    client, optimizer, factory = workbench_api
    study_id, _ = _completed_study(optimizer, factory)
    overview = _data(client.get(f"/api/v1/optimizer/studies/{study_id}/overview"))
    assert overview["study"]["id"] == study_id
    assert len(overview["trials"]) == 3
    assert all(item["metrics"] for item in overview["trials"])
    assert overview["frontier"]
    assert overview["study"]["created_at"].endswith("Z")
    assert any(item["action"] == "next-round" for item in overview["actions"])
    missing = client.get("/api/v1/optimizer/studies/nope/overview")
    assert missing.status_code == 404


def test_templates_endpoints(workbench_api) -> None:
    client, optimizer, factory = workbench_api
    catalog = _data(client.get("/api/v1/optimizer/study-templates"))
    keys = {item["key"] for item in catalog["items"]}
    assert keys == {"quality_first", "balanced", "cost_first"}
    assert all(set(item["search_space"]) == {
        "factual_top_k", "comparative_top_k", "temporal_top_k",
        "minimum_score_millis", "max_hits_per_source", "neighbor_before", "neighbor_after",
    } for item in catalog["items"])
    assert all(set(item["weights"]) == {"quality_weight_permille", "cost_weight_permille"} for item in catalog["items"])

    response = _post(
        client,
        "/api/v1/optimizer/studies/from-template",
        {
            "schema_version": 1,
            "request_id": "tpl-api-1",
            "label": "From template API",
            "base_policy_id": DEFAULT_POLICY_ID,
            "template_key": "balanced",
            "overrides": {"seed": 7, "max_candidates": 3},
        },
    )
    assert response.status_code == 201, response.text
    study_id = _data(response)["study_id"]
    detail = _data(client.get(f"/api/v1/optimizer/studies/{study_id}"))
    assert detail["objective"] == "balanced"
    assert detail["seed"] == 7
    catalog = _data(client.get("/api/v1/optimizer/studies?limit=100"))
    assert catalog["items"][0]["created_at"].endswith("Z")

    unknown = _post(
        client,
        "/api/v1/optimizer/studies/from-template",
        {"schema_version": 1, "request_id": "tpl-api-2", "label": "x", "base_policy_id": DEFAULT_POLICY_ID, "template_key": "nope"},
    )
    assert unknown.status_code == 404

    bad = _post(
        client,
        "/api/v1/optimizer/studies/from-template",
        {"schema_version": 1, "request_id": "tpl-api-3", "label": "x", "base_policy_id": DEFAULT_POLICY_ID, "template_key": "balanced", "extra": 1},
    )
    assert bad.status_code == 422

    bad_override = _post(
        client,
        "/api/v1/optimizer/studies/from-template",
        {
            "schema_version": 1,
            "request_id": "tpl-api-4",
            "label": "x",
            "base_policy_id": DEFAULT_POLICY_ID,
            "template_key": "balanced",
            "overrides": {"provider": "external"},
        },
    )
    assert bad_override.status_code == 422
    expanded_budget = _post(
        client,
        "/api/v1/optimizer/studies/from-template",
        {
            "schema_version": 1,
            "request_id": "tpl-api-5",
            "label": "x",
            "base_policy_id": DEFAULT_POLICY_ID,
            "template_key": "balanced",
            "overrides": {"max_candidates": 5},
        },
    )
    assert expanded_budget.status_code == 422


def test_events_endpoint_pagination(workbench_api) -> None:
    client, optimizer, factory = workbench_api
    study_id, _ = _completed_study(optimizer, factory)
    page = _data(client.get(f"/api/v1/optimizer/studies/{study_id}/events?limit=3"))
    assert len(page["items"]) == 3
    last_id = page["items"][-1]["id"]
    next_page = _data(client.get(f"/api/v1/optimizer/studies/{study_id}/events?limit=3&after={last_id}"))
    first_ids = {item["id"] for item in page["items"]}
    for item in next_page["items"]:
        assert item["id"] not in first_ids


def test_export_comparison_endpoint(workbench_api) -> None:
    client, optimizer, factory = workbench_api
    study_id, trial_ids = _completed_study(optimizer, factory)
    response = _post(
        client,
        f"/api/v1/optimizer/studies/{study_id}/export-comparison",
        {
            "schema_version": 1,
            "trial_ids": trial_ids[:2],
            "include_categories": True,
        },
    )
    assert response.status_code == 200, response.text
    body = _data(response)
    assert body["markdown"].startswith("# ")
    assert len(body["sha256"]) == 64

    too_few = _post(
        client,
        f"/api/v1/optimizer/studies/{study_id}/export-comparison",
        {"schema_version": 1, "trial_ids": trial_ids[:1], "include_categories": False},
    )
    assert too_few.status_code == 422

    loose_boolean = _post(
        client,
        f"/api/v1/optimizer/studies/{study_id}/export-comparison",
        {"schema_version": 1, "trial_ids": trial_ids[:2], "include_categories": 1},
    )
    assert loose_boolean.status_code == 422


def test_fail_reason_rejects_secret_looking_text(workbench_api) -> None:
    client, _optimizer_service, _factory = workbench_api
    created = _post(
        client,
        "/api/v1/optimizer/studies/from-template",
        {
            "schema_version": 1,
            "request_id": "bounded-reason-study",
            "label": "Bounded reason study",
            "base_policy_id": DEFAULT_POLICY_ID,
            "template_key": "balanced",
            "overrides": {},
        },
    )
    study_id = _data(created)["study_id"]

    response = _post(
        client,
        f"/api/v1/optimizer/studies/{study_id}/fail",
        {"schema_version": 1, "reason": "api_key=sk-super-secret-value"},
    )

    assert response.status_code == 422


def test_share_link_endpoints(workbench_api) -> None:
    client, optimizer, factory = workbench_api
    with factory.begin() as session:
        session.add(
            AgentRun(
                space_id=99,
                id="run-api-share",
                scope_snapshot_json="{}",
                scope_digest="d" * 64,
                deliverable_json="{}",
                trace_id="trace-api-share",
                goal="Share via API",
                requested_mode="force_quick",
                status="completed",
                phase="done",
                provider_mode="demo",
                version=1,
                execution_epoch=0,
                active_elapsed_ms=0,
                budget_limits_json="{}",
                budget_usage_json="{}",
            )
        )

    created = _post(client, "/api/v1/agent-runs/run-api-share/share", {"schema_version": 1})
    assert created.status_code == 201, created.text
    token = _data(created)["token"]
    assert len(token) == 64
    active_links = client.get("/api/v1/agent-runs/run-api-share/shares")
    assert _data(active_links)["items"][0]["token"] == token
    assert active_links.headers["Cache-Control"] == "no-store"

    shared = client.get(f"/api/v1/agent-runs/shared/{token}")
    assert shared.status_code == 200
    trace = _data(shared)
    assert trace["run_id"] == "run-api-share"

    # The direct trace endpoint uses its own production wiring, which is not
    # overridden in this isolated-DB test; the shared view (same data shape)
    # is the behavior under test here.
    assert trace["replay"]["stored_terminal_state"] == "completed"

    revoked = client.delete(f"/api/v1/agent-runs/shared/{token}")
    assert revoked.status_code == 200
    gone = client.get(f"/api/v1/agent-runs/shared/{token}")
    assert gone.status_code == 404
    assert _data(client.get("/api/v1/agent-runs/run-api-share/shares"))["items"] == []

    invalid = client.get("/api/v1/agent-runs/shared/" + "f" * 64)
    assert invalid.status_code == 404
