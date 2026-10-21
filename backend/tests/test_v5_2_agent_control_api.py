from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app import models  # noqa: F401
from app.api.routes_agent_control import get_agent_control
from app.db.session import Base, create_database_engine
from app.main import app
from app.models.agent_event import AgentEvent
from app.models.agent_evaluation import AgentEvaluation
from app.models.agent_run import AgentRun
from app.models.knowledge_space import KnowledgeSpace
from app.modules.agent_control.contracts import ExecuteEvaluation, StartEvaluation
from app.modules.agent_control.service import SqlAgentControl
from tests.test_v5_2_agent_control_sql import RecordingExecutor, evaluation_report


CORRUPT_PROVIDER_SECRET = "api_key=" + "sk-" + "provider-boundary-secret"
CORRUPT_ERROR_SECRET = "password=" + "database-error-secret"
PRIVATE_EVENT_SECRET = "sk-" + "private-secret"


@pytest.fixture()
def api_control(tmp_path: Path):
    database_path = tmp_path / "agent-control-api.db"
    engine = create_database_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    control = SqlAgentControl(factory)
    app.dependency_overrides[get_agent_control] = lambda: control
    try:
        yield control, factory
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def _data(response):
    payload = response.json()
    assert payload["success"] is True
    return payload["data"]


def test_evaluation_http_start_list_detail_and_compare_use_strict_persisted_contract(api_control) -> None:
    control, _factory = api_control
    with TestClient(app) as client:
        opened = client.post(
            "/api/v1/agent-evaluations",
            json={"schema_version": 1, "request_id": "api-eval-left", "label": "API baseline"},
        )
        assert opened.status_code == 201
        receipt = _data(opened)
        assert receipt["status"] == "queued"
        replay = client.post(
            "/api/v1/agent-evaluations",
            json={"schema_version": 1, "request_id": "api-eval-left", "label": "API baseline"},
        )
        assert _data(replay)["replayed"] is True
        control.execute(
            ExecuteEvaluation(receipt["evaluation_id"], "api-worker"),
            RecordingExecutor(),
        )

        right = control.submit(StartEvaluation(request_id="api-eval-right", label="API regression"))
        control.execute(
            ExecuteEvaluation(right.evaluation_id, "api-worker"),
            RecordingExecutor(evaluation_report(failed_case_id="single_hop-01")),
        )

        catalog = _data(client.get("/api/v1/agent-evaluations?limit=10"))
        assert {item["id"] for item in catalog["items"]} == {right.evaluation_id, receipt["evaluation_id"]}
        assert all(item["mode"] == "deterministic_recording" for item in catalog["items"])

        detail = _data(client.get(f"/api/v1/agent-evaluations/{receipt['evaluation_id']}"))
        assert detail["report_schema_version"] == 2
        assert detail["summary"]["case_count"] == 60
        assert detail["summary"]["external_provider_calls"] == 0
        assert len(detail["cases"]) == 60
        assert detail["provider_boundary"].endswith("not a real-model quality benchmark.")

        comparison = _data(
            client.get(
                "/api/v1/agent-evaluations/compare",
                params={"left_id": receipt["evaluation_id"], "right_id": right.evaluation_id},
            )
        )
        assert comparison["verdict"] == "regressed"
        assert comparison["new_failure_case_ids"] == ["single_hop-01"]


@pytest.mark.parametrize(
    "extra",
    [
        {"mode": "real"},
        {"dataset_path": "C:/Users/private/cases.jsonl"},
        {"command": "powershell"},
        {"output_path": "docs/report.json"},
        {"provider_mode": "recording"},
    ],
)
def test_start_route_rejects_arbitrary_execution_and_provider_fields(api_control, extra) -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/agent-evaluations",
            json={"request_id": "invalid-extra", "label": "Invalid", **extra},
        )
    assert response.status_code == 422


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/agent-evaluations?limit=0",
        "/api/v1/agent-evaluations?limit=101",
        "/api/v1/agent-evaluations?status=pretend_success",
        "/api/v1/agent-evaluations/compare?left_id=same&right_id=same",
    ],
)
def test_query_routes_reject_invalid_filters_or_same_snapshot(api_control, path: str) -> None:
    with TestClient(app) as client:
        response = client.get(path)
    assert response.status_code == 422


def test_missing_evaluation_and_run_errors_never_fall_back_or_expose_sql(api_control) -> None:
    with TestClient(app) as client:
        missing_evaluation = client.get("/api/v1/agent-evaluations/missing")
        missing_run = client.get("/api/v1/evidence-runs/missing/trace")
    assert missing_evaluation.status_code == 404
    assert missing_run.status_code == 404
    rendered = json.dumps(
        [missing_evaluation.json(), missing_run.json()],
        ensure_ascii=False,
    ).lower()
    assert "demo" not in rendered
    assert "recording" not in rendered
    assert "select " not in rendered
    assert "agent_evaluations" not in rendered
    assert "traceback" not in rendered


@pytest.mark.parametrize(
    "path",
    [
        f"/api/v1/agent-evaluations/{'a' * 37}",
        "/api/v1/agent-evaluations/invalid%2Fid",
        f"/api/v1/evidence-runs/{'r' * 37}/trace",
        "/api/v1/evidence-runs/invalid%20id/trace",
    ],
)
def test_identifier_paths_are_bounded_and_reject_unsafe_characters(api_control, path: str) -> None:
    with TestClient(app) as client:
        response = client.get(path)
    assert response.status_code in {404, 422}


def test_detail_read_path_redacts_manually_corrupted_secret_fields(api_control) -> None:
    _control, factory = api_control
    with factory.begin() as session:
        session.add(
            AgentEvaluation(
                id="evaluation-corrupt-secret",
                request_id="request-corrupt-secret",
                request_payload_hash="a" * 64,
                label="Corrupt fixture",
                mode="deterministic_recording",
                status="failed",
                policy_fingerprint="b" * 64,
                case_count=0,
                failure_case_count=0,
                provider_boundary=CORRUPT_PROVIDER_SECRET,
                error_code="EVALUATION_EXECUTOR_FAILED",
                error_message=CORRUPT_ERROR_SECRET,
                attempt=1,
            )
        )
    with TestClient(app) as client:
        response = client.get("/api/v1/agent-evaluations/evaluation-corrupt-secret")
    assert response.status_code == 200
    rendered = response.text
    assert CORRUPT_PROVIDER_SECRET not in rendered
    assert CORRUPT_ERROR_SECRET not in rendered
    detail = _data(response)
    assert detail["provider_boundary"] == "[redacted]"
    assert detail["error_message"] == "[redacted]"


def test_run_trace_route_serializes_redacted_private_events_only(api_control) -> None:
    _control, factory = api_control
    now = datetime(2026, 8, 27, 10, 0, tzinfo=UTC)
    with factory.begin() as session:
        space = KnowledgeSpace(name="Trace API", description="V5.2")
        session.add(space)
        session.flush()
        run = AgentRun(
            id="trace-api-run",
            space_id=space.id,
            goal="Explain the trace",
            requested_mode="force_agent",
            effective_mode=None,
            status="running",
            phase="route",
            version=2,
            execution_epoch=0,
            scope_snapshot_json="{}",
            scope_digest="a" * 64,
            deliverable_json="{}",
            policy_snapshot_json="{}",
            budget_limits_json="{}",
            budget_usage_json="{}",
            provider_mode="demo",
            trace_id="trace-api",
            active_elapsed_ms=0,
            created_at=now,
        )
        session.add(run)
        session.flush()
        session.add_all(
            (
                AgentEvent(
                    event_id="trace-api-public",
                    run_id=run.id,
                    run_sequence=1,
                    run_version=1,
                    event_type="run.opened",
                    payload_json='{"status":"queued","api_key":"public-secret"}',
                    schema_version=1,
                    visibility="public",
                    trace_id=run.trace_id,
                    created_at=now,
                ),
                AgentEvent(
                    event_id="trace-api-private",
                    run_id=run.id,
                    run_sequence=2,
                    run_version=2,
                    event_type="model.started",
                    payload_json=json.dumps({"prompt": "private prompt", "api_key": PRIVATE_EVENT_SECRET}),
                    schema_version=1,
                    visibility="private",
                    trace_id=run.trace_id,
                    created_at=now,
                ),
            )
        )

    with TestClient(app) as client:
        response = client.get("/api/v1/evidence-runs/trace-api-run/trace")
    assert response.status_code == 200
    trace = _data(response)
    assert trace["events"][1]["redacted"] is True
    assert trace["events"][1]["facts"] == []
    assert trace["replay"]["redacted_event_count"] == 1
    rendered = response.text
    assert "private prompt" not in rendered
    assert PRIVATE_EVENT_SECRET not in rendered
    assert "public-secret" not in rendered
