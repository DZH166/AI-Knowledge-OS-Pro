from __future__ import annotations

from collections.abc import Iterator
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.db.session import Base, create_database_engine
from app.main import app
from app.models.knowledge_space import KnowledgeSpace
from app.modules.evidence_agent.service import SqlEvidenceAgent
from app.modules.evidence_agent.wiring import get_evidence_agent


@pytest.fixture()
def stream_client(tmp_path: Path) -> Iterator[TestClient]:
    engine = create_database_engine(f"sqlite:///{(tmp_path / 'agent-stream.db').as_posix()}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions.begin() as session:
        session.add(KnowledgeSpace(id=1, name="Stream regression"))
    agent = SqlEvidenceAgent(sessions)
    app.dependency_overrides[get_evidence_agent] = lambda: agent
    client = TestClient(app)
    try:
        yield client
    finally:
        client.close()
        app.dependency_overrides.pop(get_evidence_agent, None)
        engine.dispose()


@pytest.fixture()
def cancelled_run(stream_client: TestClient) -> tuple[dict, dict]:
    opened = stream_client.post(
        "/api/v1/evidence-runs",
        json={
            "request_id": "v512-open-stream",
            "space_id": 1,
            "goal": "验证任务事件恢复",
            "provider_mode": "recording",
        },
    )
    assert opened.status_code == 201
    receipt = opened.json()["data"]
    cancelled = stream_client.post(
        f"/api/v1/evidence-runs/{receipt['run_id']}/commands",
        json={
            "request_id": "v512-cancel-stream",
            "expected_version": receipt["run_version"],
            "signal": "cancel",
        },
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["data"]["status"] == "cancelled"
    return receipt, cancelled.json()["data"]


def _sse_frames(body: str) -> list[dict]:
    frames = []
    for block in body.strip().split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.splitlines())
        frames.append(
            {"id": int(fields["id"]), "event": fields["event"], "data": json.loads(fields["data"])}
        )
    return frames


@pytest.mark.parametrize(
    ("query", "last_event_id"),
    [("", None), ("?after=0", None), ("?after=999999", None), ("", "0"), ("", "999999")],
)
def test_missing_run_stream_returns_the_same_structured_404_as_run_detail(
    stream_client: TestClient,
    query: str,
    last_event_id: str | None,
) -> None:
    headers = {"X-Request-ID": "v512-missing-run-stream"}
    if last_event_id is not None:
        headers["Last-Event-ID"] = last_event_id
    detail = stream_client.get("/api/v1/evidence-runs/missing-run", headers=headers)
    assert detail.status_code == 404
    assert detail.json()["error"]["code"] == "RUN_NOT_FOUND"

    streamed = stream_client.get(f"/api/v1/evidence-runs/missing-run/stream{query}", headers=headers)

    assert streamed.status_code == 404
    assert streamed.headers["content-type"].startswith("application/json")
    assert streamed.json() == detail.json()
    assert streamed.json()["request_id"] == "v512-missing-run-stream"
    assert streamed.json()["error"]["request_id"] == "v512-missing-run-stream"
    assert streamed.headers["x-request-id"] == "v512-missing-run-stream"


def test_cancelled_run_stream_preserves_public_history_and_resumes_at_durable_cursor(
    stream_client: TestClient,
    cancelled_run: tuple[dict, dict],
) -> None:
    opened, cancelled = cancelled_run
    path = f"/api/v1/evidence-runs/{opened['run_id']}/stream"
    full = stream_client.get(f"{path}?after=0")

    assert full.status_code == 200
    assert full.headers["content-type"].startswith("text/event-stream")
    assert full.headers["cache-control"] == "no-cache"
    assert full.headers["x-accel-buffering"] == "no"
    frames = _sse_frames(full.text)
    assert [(frame["id"], frame["event"]) for frame in frames] == [
        (opened["cursor"], "run.opened"),
        (cancelled["cursor"], "run.cancelled"),
    ]
    assert frames[0]["data"]["schema_version"] == 1
    assert frames[0]["data"]["cursor"] == opened["cursor"]
    assert frames[0]["data"]["run_version"] == opened["run_version"]
    assert frames[0]["data"]["type"] == "run.opened"
    assert frames[0]["data"]["payload"]["goal"] == "验证任务事件恢复"
    assert frames[-1]["data"]["payload"] == {"signal": "cancel", "response": {}}

    resumed = stream_client.get(f"{path}?after={opened['cursor']}")
    assert resumed.status_code == 200
    assert _sse_frames(resumed.text) == [frames[-1]]

    detail = stream_client.get(f"/api/v1/evidence-runs/{opened['run_id']}").json()["data"]
    assert detail["last_event_cursor"] == cancelled["cursor"]
    caught_up = stream_client.get(f"{path}?after={detail['last_event_cursor']}")
    assert caught_up.status_code == 200
    assert caught_up.headers["content-type"].startswith("text/event-stream")
    assert caught_up.text == ""


@pytest.mark.parametrize("header_is_last_cursor", [False, True])
def test_last_event_id_takes_precedence_over_after_for_cancelled_run(
    stream_client: TestClient,
    cancelled_run: tuple[dict, dict],
    header_is_last_cursor: bool,
) -> None:
    opened, cancelled = cancelled_run
    header_cursor = cancelled["cursor"] if header_is_last_cursor else opened["cursor"]
    query_cursor = opened["cursor"] if header_is_last_cursor else cancelled["cursor"]
    response = stream_client.get(
        f"/api/v1/evidence-runs/{opened['run_id']}/stream?after={query_cursor}",
        headers={"Last-Event-ID": str(header_cursor)},
    )

    assert response.status_code == 200
    if header_is_last_cursor:
        assert response.text == ""
    else:
        assert [(frame["id"], frame["event"]) for frame in _sse_frames(response.text)] == [
            (cancelled["cursor"], "run.cancelled"),
        ]


@pytest.mark.parametrize("query", ["", "?after=999999"])
def test_bootstrap_and_unknown_future_cursor_send_sync_then_complete_public_history(
    stream_client: TestClient,
    cancelled_run: tuple[dict, dict],
    query: str,
) -> None:
    opened, cancelled = cancelled_run
    response = stream_client.get(f"/api/v1/evidence-runs/{opened['run_id']}/stream{query}")

    assert response.status_code == 200
    frames = _sse_frames(response.text)
    assert [(frame["id"], frame["event"]) for frame in frames] == [
        (0, "sync"),
        (opened["cursor"], "run.opened"),
        (cancelled["cursor"], "run.cancelled"),
    ]
    snapshot = frames[0]["data"]["payload"]["run"]
    assert snapshot["id"] == opened["run_id"]
    assert snapshot["status"] == "cancelled"
    assert snapshot["last_event_cursor"] == cancelled["cursor"]


def test_negative_after_is_a_structured_validation_error_even_with_valid_last_event_id(
    stream_client: TestClient,
    cancelled_run: tuple[dict, dict],
) -> None:
    opened, _cancelled = cancelled_run
    response = stream_client.get(
        f"/api/v1/evidence-runs/{opened['run_id']}/stream?after=-1",
        headers={"Last-Event-ID": "0", "X-Request-ID": "v512-negative-after"},
    )

    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/json")
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert response.json()["request_id"] == "v512-negative-after"
    assert response.json()["error"]["request_id"] == "v512-negative-after"
    assert response.headers["x-request-id"] == "v512-negative-after"
