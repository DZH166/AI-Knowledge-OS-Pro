from __future__ import annotations

from collections.abc import AsyncIterator
from threading import Barrier, Thread, local

from fastapi.testclient import TestClient
from sqlalchemy import event as sqlalchemy_event, func, select
from sqlalchemy.orm import sessionmaker

from app.db.session import Base, create_database_engine
from app.main import app
from app.models.agent_event import AgentCommand
from app.models.agent_run import AgentRun
from app.models.knowledge_space import KnowledgeSpace
from app.modules.evidence_agent.contracts import (
    GetRun,
    GetArtifact,
    GetEvidence,
    ArtifactClaimView,
    ArtifactCatalog,
    ArtifactSummary,
    ArtifactView,
    EvidenceView,
    ListArtifacts,
    RunFrame,
    RunMode,
    RunPhase,
    RunStatus,
    RunView,
    ScopeSnapshot,
    Submission,
)
from app.modules.evidence_agent import wiring as agent_wiring
from app.modules.evidence_agent.service import SqlEvidenceAgent
from app.modules.evidence_agent.wiring import get_evidence_agent


class RecordingAgent:
    def __init__(self) -> None:
        self.commands = []
        self.queries = []

    def submit(self, command):
        self.commands.append(command)
        return Submission(
            command_id="command-api",
            run_id="run-api",
            run_version=1,
            status=RunStatus.QUEUED,
            cursor=4,
        )

    def inspect(self, query: GetRun) -> RunView:
        self.queries.append(query)
        if isinstance(query, ListArtifacts):
            return ArtifactCatalog(
                items=(
                    ArtifactSummary(
                        id="artifact-api",
                        producing_run_id="run-api",
                        kind="answer",
                        title="API artifact",
                        status="final",
                    ),
                )
            )
        if isinstance(query, GetArtifact):
            return ArtifactView(
                id=query.artifact_id,
                producing_run_id="run-api",
                kind="answer",
                title="API artifact",
                body_markdown="A supported claim [1]",
                status="final",
                schema_version=1,
                claims=(
                    ArtifactClaimView(
                        id="claim-api",
                        ordinal=1,
                        text="A supported claim",
                        kind="factual",
                        verification_status="supported",
                        evidence_ids=("evidence-api",),
                    ),
                ),
            )
        if isinstance(query, GetEvidence):
            return EvidenceView(
                id=query.evidence_id,
                run_id="run-api",
                source_id=2,
                revision_id=3,
                index_revision_id=4,
                chunk_id=5,
                source_type="document",
                locator={"kind": "pdf_page", "page": 6},
                revision_content_hash="a" * 64,
                content_hash="b" * 64,
                excerpt_preview="supporting excerpt",
                claim_ids=("claim-api",),
            )
        return RunView(
            id=query.run_id,
            space_id=1,
            goal="核验 API 契约",
            requested_mode=RunMode.FORCE_QUICK,
            effective_mode=None,
            status=RunStatus.QUEUED,
            phase=RunPhase.ROUTE,
            version=1,
            execution_epoch=0,
            scope_snapshot=ScopeSnapshot(space_id=1),
            budget_limits={"max_steps": 4},
            budget_usage={"steps": 0},
            provider_mode="recording",
            last_event_cursor=4,
        )

    async def follow(self, run_id: str, cursor: int | None = None) -> AsyncIterator[RunFrame]:
        yield RunFrame(
            cursor=4,
            event_type="run.opened",
            run_version=1,
            payload={"goal": "核验 API 契约"},
        )


def test_agent_command_and_query_routes_map_only_to_three_entry_seam() -> None:
    fake = RecordingAgent()
    app.dependency_overrides[get_evidence_agent] = lambda: fake
    try:
        client = TestClient(app)
        opened = client.post(
            "/api/v1/evidence-runs",
            json={
                "schema_version": 1,
                "request_id": "request-api",
                "space_id": 1,
                "goal": "核验 API 契约",
                "scope": {"source_ids": []},
                "deliverable": {"kind": "answer"},
                "mode": "force_quick",
                "budget": {"max_steps": 4, "max_tool_calls": 3, "max_model_calls": 2},
                "permissions": {"read_only": True},
                "provider_mode": "recording",
            },
        )
        assert opened.status_code == 201
        data = opened.json()["data"]
        assert data == {
            "schema_version": 1,
            "command_id": "command-api",
            "run_id": "run-api",
            "run_version": 1,
            "status": "queued",
            "cursor": 4,
            "replayed": False,
        }

        inspected = client.get("/api/v1/evidence-runs/run-api")
        assert inspected.status_code == 200
        assert inspected.json()["data"]["outcome"] is None
        assert inspected.json()["data"]["scope_snapshot"]["space_id"] == 1
        assert inspected.json()["data"]["cost_measurement"] == "unknown"
        assert len(fake.commands) == 1

        modified = client.post(
            "/api/v1/evidence-runs/run-api/commands",
            json={
                "schema_version": 1,
                "request_id": "modify-api",
                "expected_version": 1,
                "signal": "modify",
                "response": {"title": "人工复核后的 API 报告"},
                "proposal_digest": "a" * 64,
            },
        )
        assert modified.status_code == 200
        assert fake.commands[-1].signal.value == "modify"
        assert fake.commands[-1].response == {"title": "人工复核后的 API 报告"}
    finally:
        app.dependency_overrides.pop(get_evidence_agent, None)


def test_concurrent_open_payload_conflict_is_a_stable_409_without_database_details(tmp_path) -> None:
    database_path = tmp_path / "concurrent-open-api-conflict.db"
    engine = create_database_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory.begin() as session:
        session.add(KnowledgeSpace(id=1, name="Concurrent API open"))

    first_lookup_barrier = Barrier(2)
    thread_state = local()

    def synchronize_idempotency_lookups(
        _connection,
        _cursor,
        statement,
        _parameters,
        _context,
        _executemany,
    ) -> None:
        normalized = " ".join(statement.lower().split())
        if (
            not getattr(thread_state, "synchronized", False)
            and normalized.startswith("select")
            and "from agent_commands" in normalized
            and "agent_commands.request_id" in normalized
        ):
            thread_state.synchronized = True
            first_lookup_barrier.wait(timeout=5)

    sqlalchemy_event.listen(engine, "before_cursor_execute", synchronize_idempotency_lookups)
    agent = SqlEvidenceAgent(factory)
    app.dependency_overrides[get_evidence_agent] = lambda: agent
    responses = []

    def open_run(goal: str) -> None:
        responses.append(
            TestClient(app, raise_server_exceptions=False).post(
                "/api/v1/evidence-runs",
                json={
                    "schema_version": 1,
                    "request_id": "concurrent-api-conflict",
                    "space_id": 1,
                    "goal": goal,
                    "scope": {"source_ids": []},
                    "deliverable": {"kind": "answer"},
                    "mode": "force_quick",
                    "budget": {"max_steps": 4, "max_tool_calls": 3, "max_model_calls": 2},
                    "permissions": {"read_only": True},
                    "provider_mode": "recording",
                },
            )
        )

    workers = [
        Thread(target=open_run, args=("first payload",)),
        Thread(target=open_run, args=("different payload",)),
    ]
    try:
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(timeout=10)
        assert all(not worker.is_alive() for worker in workers)
    finally:
        sqlalchemy_event.remove(engine, "before_cursor_execute", synchronize_idempotency_lookups)
        app.dependency_overrides.pop(get_evidence_agent, None)

    try:
        assert sorted(response.status_code for response in responses) == [201, 409]
        conflict = next(response for response in responses if response.status_code == 409)
        error = conflict.json()["error"]
        assert error["code"] == "IDEMPOTENCY_CONFLICT"
        serialized_error = conflict.text.lower()
        assert "integrityerror" not in serialized_error
        assert "unique constraint" not in serialized_error
        assert "agent_commands" not in serialized_error
        with factory() as session:
            assert session.scalar(select(func.count()).select_from(AgentRun)) == 1
            assert session.scalar(select(func.count()).select_from(AgentCommand)) == 1
    finally:
        engine.dispose()


def test_real_agent_run_refuses_when_llm_provider_is_not_configured(monkeypatch) -> None:
    fake = RecordingAgent()
    app.dependency_overrides[get_evidence_agent] = lambda: fake
    monkeypatch.setattr(agent_wiring, "_agent_model", None)
    try:
        response = TestClient(app).post(
            "/api/v1/evidence-runs",
            json={
                "schema_version": 1,
                "request_id": "request-real-without-provider",
                "space_id": 1,
                "goal": "执行真实 Agent 研究",
                "provider_mode": "real",
            },
        )

        assert response.status_code == 503
        assert response.json()["error"]["code"] == "LLM_NOT_CONFIGURED"
        assert fake.commands == []
    finally:
        app.dependency_overrides.pop(get_evidence_agent, None)


def test_agent_sse_is_not_json_enveloped_and_uses_durable_cursor() -> None:
    fake = RecordingAgent()
    app.dependency_overrides[get_evidence_agent] = lambda: fake
    try:
        client = TestClient(app)
        response = client.get(
            "/api/v1/evidence-runs/run-api/stream",
            headers={"Last-Event-ID": "3"},
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        assert response.headers["cache-control"] == "no-cache"
        assert response.headers["x-accel-buffering"] == "no"
        assert "id: 4" in response.text
        assert "event: run.opened" in response.text
        assert '"schema_version":1' in response.text
        assert not response.text.startswith('{"success"')
    finally:
        app.dependency_overrides.pop(get_evidence_agent, None)


def test_artifact_and_evidence_routes_keep_revision_complete_provenance() -> None:
    fake = RecordingAgent()
    app.dependency_overrides[get_evidence_agent] = lambda: fake
    try:
        client = TestClient(app)
        artifact = client.get("/api/v1/artifacts/artifact-api").json()["data"]
        evidence = client.get("/api/v1/evidence/evidence-api").json()["data"]

        assert artifact["claims"][0]["evidence_ids"] == ["evidence-api"]
        assert evidence["revision_id"] == 3
        assert evidence["index_revision_id"] == 4
        assert evidence["content_hash"] == "b" * 64
        assert evidence["locator"] == {"kind": "pdf_page", "page": 6}
    finally:
        app.dependency_overrides.pop(get_evidence_agent, None)


def test_artifact_catalog_maps_source_filter_to_the_domain_query() -> None:
    fake = RecordingAgent()
    app.dependency_overrides[get_evidence_agent] = lambda: fake
    try:
        response = TestClient(app).get(
            "/api/v1/artifacts?space_id=1&source_id=2&run_id=run-api&limit=7"
        )

        assert response.status_code == 200
        assert response.json()["data"]["items"][0]["id"] == "artifact-api"
        assert fake.queries[-1] == ListArtifacts(
            space_id=1,
            source_id=2,
            run_id="run-api",
            limit=7,
        )
    finally:
        app.dependency_overrides.pop(get_evidence_agent, None)


def test_catalog_query_parameters_reject_invalid_status_and_limits_before_domain_dispatch() -> None:
    fake = RecordingAgent()
    app.dependency_overrides[get_evidence_agent] = lambda: fake
    try:
        client = TestClient(app)

        assert client.get("/api/v1/evidence-runs?status=made_up").status_code == 422
        assert client.get("/api/v1/evidence-runs?limit=101").status_code == 422
        assert client.get("/api/v1/artifacts?space_id=0").status_code == 422
        assert client.get("/api/v1/artifacts?source_id=0").status_code == 422
        assert client.get("/api/v1/artifacts?limit=101").status_code == 422
    finally:
        app.dependency_overrides.pop(get_evidence_agent, None)
