from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.api.routes_agent_control import get_agent_control
from app.api.routes_agent_policy import get_agent_policy
from app.api.routes_agent_runs import get_evidence_agent
from app.db.session import Base, create_database_engine
from app.main import app
from app.models.agent_event import AgentEvent
from app.models.agent_policy import AgentPolicyVersion
from app.models.agent_run import AgentRequirement, AgentRun, AgentToolCall
from app.models.knowledge_space import KnowledgeSpace
from app.modules.agent_control.contracts import ExecuteEvaluation
from app.modules.agent_control.service import SqlAgentControl
from app.modules.agent_policy.config import RetrievalPolicyConfig, canonical_policy_json, policy_fingerprint
from app.modules.agent_policy.contracts import GetActivePolicy, GetPolicy, PolicyDetail
from app.modules.agent_policy.service import SqlAgentPolicy
from app.modules.evidence_agent.service import SqlEvidenceAgent
from tests.test_v5_3_agent_policy_evaluation import RecordingPolicyExecutor


DEFAULT_POLICY_ID = "00000000-0000-0000-0000-000000000001"


@pytest.fixture()
def policy_api(tmp_path: Path):
    engine = create_database_engine(f"sqlite:///{(tmp_path / 'policy-api.db').as_posix()}")
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
        session.add(KnowledgeSpace(id=1, name="Policy API", description="test"))
    policy = SqlAgentPolicy(factory)

    def resolve(policy_id: str | None) -> PolicyDetail:
        result = policy.inspect(GetPolicy(policy_id)) if policy_id else policy.inspect(GetActivePolicy())
        assert isinstance(result, PolicyDetail)
        return result

    control = SqlAgentControl(factory, policy_resolver=resolve)
    agent = SqlEvidenceAgent(factory, active_policy=lambda: resolve(None))
    app.dependency_overrides[get_agent_policy] = lambda: policy
    app.dependency_overrides[get_agent_control] = lambda: control
    app.dependency_overrides[get_evidence_agent] = lambda: agent
    try:
        yield policy, control, factory
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def _data(response):
    payload = response.json()
    assert payload["success"] is True, payload
    return payload["data"]


def test_policy_http_candidate_evaluation_activation_and_rollback(policy_api) -> None:
    _policy, control, _factory = policy_api
    with TestClient(app) as client:
        active = _data(client.get("/api/v1/agent-policies/active"))
        assert active["id"] == DEFAULT_POLICY_ID
        created = _data(
            client.post(
                "/api/v1/agent-policies",
                json={
                    "schema_version": 1,
                    "request_id": "policy-api-create",
                    "label": "API candidate",
                    "base_policy_id": DEFAULT_POLICY_ID,
                    "config": {
                        **active["config"],
                        "comparative_top_k": 18,
                        "neighbor_before": 2,
                    },
                },
            )
        )
        assert created["status"] == "draft"
        policy_id = created["policy_id"]

        catalog = _data(client.get("/api/v1/agent-policies?limit=10"))
        assert [item["version"] for item in catalog["items"]] == [2, 1]
        comparison = _data(
            client.get(
                "/api/v1/agent-policies/compare",
                params={"left_id": DEFAULT_POLICY_ID, "right_id": policy_id},
            )
        )
        assert [item["field"] for item in comparison["changes"]] == [
            "comparative_top_k",
            "neighbor_before",
        ]

        evaluation = _data(
            client.post(
                "/api/v1/agent-evaluations",
                json={
                    "schema_version": 1,
                    "request_id": "policy-api-evaluation",
                    "label": "API candidate evaluation",
                    "policy_id": policy_id,
                },
            )
        )
        control.execute(
            ExecuteEvaluation(evaluation["evaluation_id"], "api-policy-worker"),
            RecordingPolicyExecutor(),
        )
        activated = _data(
            client.post(
                f"/api/v1/agent-policies/{policy_id}/activate",
                json={
                    "schema_version": 1,
                    "request_id": "policy-api-activate",
                    "expected_active_policy_id": DEFAULT_POLICY_ID,
                    "evaluation_id": evaluation["evaluation_id"],
                },
            )
        )
        assert activated["active_policy_id"] == policy_id
        assert _data(client.get("/api/v1/agent-policies/active"))["id"] == policy_id
        opened_run = _data(
            client.post(
                "/api/v1/evidence-runs",
                json={
                    "schema_version": 1,
                    "request_id": "policy-api-pinned-run",
                    "space_id": 1,
                    "goal": "Inspect the pinned policy",
                    "scope": {"source_ids": []},
                    "deliverable": {"kind": "answer", "title": "Pinned policy"},
                    "mode": "force_quick",
                    "permissions": {"read_only": True, "allow_scope_expansion": False},
                    "provider_mode": "demo",
                },
            )
        )
        run_view = _data(client.get(f"/api/v1/evidence-runs/{opened_run['run_id']}"))
        assert run_view["decision_policy"] == {
            "id": policy_id,
            "version": 2,
            "config_sha256": _data(client.get(f"/api/v1/agent-policies/{policy_id}"))["config_sha256"],
        }

        rolled_back = _data(
            client.post(
                f"/api/v1/agent-policies/{DEFAULT_POLICY_ID}/rollback",
                json={
                    "schema_version": 1,
                    "request_id": "policy-api-rollback",
                    "expected_active_policy_id": policy_id,
                },
            )
        )
        assert rolled_back["active_policy_id"] == DEFAULT_POLICY_ID


def test_policy_http_simulation_uses_persisted_allowlisted_facts(policy_api) -> None:
    _policy, _control, factory = policy_api
    with factory.begin() as session:
        session.add(
            AgentRun(
                id="run-policy-api-simulation",
                space_id=1,
                goal="private simulation goal",
                requested_mode="force_agent",
                effective_mode="force_agent",
                status="completed",
                phase="persist_artifact",
                version=2,
                execution_epoch=0,
                scope_snapshot_json="{}",
                scope_digest="a" * 64,
                deliverable_json="{}",
                policy_snapshot_json="{}",
                budget_limits_json="{}",
                budget_usage_json="{}",
                provider_mode="demo",
                trace_id="trace-policy-api",
                active_elapsed_ms=0,
            )
        )
        session.flush()
        session.add(
            AgentRequirement(
                id="requirement-policy-api",
                run_id="run-policy-api-simulation",
                plan_version=1,
                ordinal=1,
                text="private requirement",
                kind="factual",
                priority="must",
                depends_on_json="[]",
                status="covered",
            )
        )
        session.add(
            AgentToolCall(
                id="tool-policy-api",
                run_id="run-policy-api-simulation",
                invocation_key="search:requirement-policy-api:1",
                tool_name="search_evidence",
                tool_version="1",
                effect="read_evidence",
                arguments_json="private arguments are deliberately not valid JSON",
                arguments_digest="b" * 64,
                status="completed",
                result_json="{}",
                execution_epoch=0,
            )
        )
        session.add(
            AgentEvent(
                event_id="event-policy-api",
                run_id="run-policy-api-simulation",
                run_sequence=1,
                run_version=2,
                event_type="tool.started",
                payload_json=json.dumps(
                    {
                        "tool": "search_evidence",
                        "retrieval_policy": {
                            "policy_id": DEFAULT_POLICY_ID,
                            "policy_version": 1,
                            "reason_code": "requirement_kind:factual",
                            "top_k": 10,
                        },
                    },
                    separators=(",", ":"),
                ),
                visibility="public",
                tool_call_id="tool-policy-api",
                trace_id="trace-policy-api",
            )
        )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/agent-policies/simulate",
            json={
                "schema_version": 1,
                "run_id": "run-policy-api-simulation",
                "policy_id": DEFAULT_POLICY_ID,
            },
        )
    assert response.status_code == 200
    simulation = _data(response)
    assert simulation["projected_candidate_window_delta"] == -2
    assert "no model, retrieval" in simulation["boundary"]
    assert "private simulation goal" not in response.text
    assert "private requirement" not in response.text


@pytest.mark.parametrize(
    "body",
    [
        {"config": {"factual_top_k": True}},
        {"config": {"factual_top_k": 0}},
        {"config": {"neighbor_after": 4}},
        {"config": {"arbitrary_python": "import os"}},
        {"command": "powershell"},
        {"dataset_path": "C:/private.jsonl"},
    ],
)
def test_policy_http_rejects_unknown_executable_and_out_of_range_fields(policy_api, body) -> None:
    valid = {
        "schema_version": 1,
        "request_id": "policy-api-invalid",
        "label": "Invalid candidate",
        "base_policy_id": DEFAULT_POLICY_ID,
        "config": RetrievalPolicyConfig().as_dict(),
    }
    if "config" in body:
        valid["config"] = {**valid["config"], **body["config"]}
        body = {key: value for key, value in body.items() if key != "config"}
    with TestClient(app) as client:
        response = client.post("/api/v1/agent-policies", json={**valid, **body})
    assert response.status_code == 422


def test_policy_http_errors_never_fall_back_or_expose_sql(policy_api) -> None:
    with TestClient(app) as client:
        missing = client.get("/api/v1/agent-policies/policy-missing")
        bad_identifier = client.get("/api/v1/agent-policies/invalid%2Fid")
    assert missing.status_code == 404
    assert bad_identifier.status_code in {404, 422}
    rendered = json.dumps([missing.json(), bad_identifier.json()]).lower()
    assert "demo policy" not in rendered
    assert "select " not in rendered
    assert "agent_policy_versions" not in rendered
    assert "traceback" not in rendered
