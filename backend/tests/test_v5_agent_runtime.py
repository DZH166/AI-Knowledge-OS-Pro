from __future__ import annotations

import asyncio
from hashlib import sha256
from threading import Barrier, Event, Thread, local

import pytest
from sqlalchemy import create_engine, event as sqlalchemy_event, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.errors import ServiceError
from app.db.session import Base, create_database_engine
from app.models.agent_event import AgentCommand, AgentEvent
from app.models.agent_evidence import (
    AgentArtifact,
    AgentClaim,
    AgentEvidence,
    ClaimEvidence,
    RequirementEvidence,
)
from app.models.agent_run import AgentPlan, AgentRequirement, AgentRun, AgentToolCall
from app.models.knowledge_space import KnowledgeSpace
from app.models.outbox import OutboxMessage
from app.models.source import Source
from app.modules.evidence_agent.contracts import (
    BudgetLimits,
    DeliverableSpec,
    GetArtifact,
    GetEvidence,
    GetRun,
    ListArtifacts,
    OpenRun,
    PermissionPolicy,
    RunMode,
    RunStatus,
    ScopeSelector,
    SignalKind,
    SignalRun,
)
from app.modules.evidence_agent.service import SqlEvidenceAgent
from app.modules.evidence_agent.controller import AgentRunner
from app.modules.evidence_agent.sql_store import SqlAgentJournal
from app.modules.evidence_index import (
    ActivateRevision,
    ChunkDraft,
    GetRevision,
    RevisionDraft,
    SqlEvidenceIndex,
    StageRevision,
    VerifiedPoint,
)


@pytest.fixture()
def agent_session_factory():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory.begin() as session:
        session.add(KnowledgeSpace(id=1, name="Agent evidence", description="test"))
    try:
        yield factory
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


def _open(
    request_id: str = "req-open",
    *,
    goal: str = "总结当前资料",
    mode: RunMode = RunMode.FORCE_QUICK,
    budget: BudgetLimits | None = None,
    provider_mode: str = "recording",
) -> OpenRun:
    return OpenRun(
        request_id=request_id,
        space_id=1,
        goal=goal,
        scope=ScopeSelector(),
        deliverable=DeliverableSpec(kind="answer"),
        mode=mode,
        budget=budget or BudgetLimits(max_steps=4, max_tool_calls=3, max_model_calls=2),
        permissions=PermissionPolicy(read_only=True),
        provider_mode=provider_mode,
    )


def test_submit_persists_open_event_when_sqlite_foreign_keys_are_enforced(
    tmp_path,
) -> None:
    database_path = tmp_path / "agent-runtime.db"
    engine = create_database_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
        expire_on_commit=False,
    )
    try:
        with engine.connect() as connection:
            assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
        with factory.begin() as session:
            session.add(KnowledgeSpace(id=1, name="Agent evidence", description="test"))

        agent = SqlEvidenceAgent(factory)
        submission = agent.submit(_open(request_id="sqlite-fk-open"))

        view = agent.inspect(GetRun(submission.run_id))
        assert view.status is RunStatus.QUEUED
        assert view.last_event_cursor == submission.cursor
        assert view.last_event_cursor > 0
    finally:
        engine.dispose()


def test_runner_persists_monotonic_events_when_session_autoflush_is_disabled(
    tmp_path,
) -> None:
    database_path = tmp_path / "agent-runner-events.db"
    engine = create_database_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
        expire_on_commit=False,
    )
    try:
        with factory.begin() as session:
            session.add(KnowledgeSpace(id=1, name="Agent evidence", description="test"))

        agent = SqlEvidenceAgent(factory)
        runner = _runner(factory)
        submission = agent.submit(_open(request_id="sqlite-no-autoflush-route"))

        dispatched = runner.advance_one(
            submission.run_id,
            expected_version=submission.run_version,
            execution_epoch=0,
        )
        routed = runner.advance_one(
            submission.run_id,
            expected_version=dispatched.version,
            execution_epoch=0,
        )

        assert routed.status is RunStatus.RUNNING
        with factory() as session:
            events = session.scalars(
                select(AgentEvent)
                .where(AgentEvent.run_id == submission.run_id)
                .order_by(AgentEvent.run_sequence)
            ).all()
        assert [event.run_sequence for event in events] == [1, 2, 3, 4]
        assert [event.event_type for event in events] == [
            "run.opened",
            "run.status_changed",
            "run.mode_selected",
            "step.started",
        ]
    finally:
        engine.dispose()


def test_submit_is_idempotent_and_persists_run_event_checkpoint_and_outbox(
    agent_session_factory,
) -> None:
    agent = SqlEvidenceAgent(agent_session_factory)

    first = agent.submit(_open())
    replay = agent.submit(_open())

    assert first.run_id == replay.run_id
    assert first.replayed is False
    assert replay.replayed is True
    assert first.status is RunStatus.QUEUED
    with agent_session_factory() as session:
        assert session.scalar(select(func.count()).select_from(AgentRun)) == 1
        assert session.scalar(select(func.count()).select_from(AgentCommand)) == 1
        assert session.scalar(select(func.count()).select_from(AgentEvent)) == 1
        assert session.scalar(select(func.count()).select_from(OutboxMessage)) == 1


def test_same_request_id_with_different_payload_is_rejected(agent_session_factory) -> None:
    agent = SqlEvidenceAgent(agent_session_factory)
    agent.submit(_open(goal="第一版目标"))

    with pytest.raises(ServiceError) as raised:
        agent.submit(_open(goal="被篡改的目标"))

    assert raised.value.code == "IDEMPOTENCY_CONFLICT"


def test_concurrent_open_with_the_same_request_id_and_payload_replays_the_winner(tmp_path) -> None:
    database_path = tmp_path / "concurrent-open-replay.db"
    engine = create_database_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory.begin() as session:
        session.add(KnowledgeSpace(id=1, name="Concurrent open"))

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
    outcomes: list[object] = []

    def submit_open() -> None:
        try:
            outcomes.append(
                agent.submit(
                    _open(
                        request_id="concurrent-open-same-payload",
                        goal="return one durable receipt",
                    )
                )
            )
        except Exception as exc:  # noqa: BLE001 - regression forbids raw DB errors.
            outcomes.append(exc)

    workers = [Thread(target=submit_open), Thread(target=submit_open)]
    try:
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(timeout=10)
        assert all(not worker.is_alive() for worker in workers)
    finally:
        sqlalchemy_event.remove(engine, "before_cursor_execute", synchronize_idempotency_lookups)

    try:
        assert len(outcomes) == 2
        assert all(not isinstance(item, Exception) for item in outcomes), outcomes
        receipts = outcomes
        assert len({item.run_id for item in receipts}) == 1
        assert len({item.command_id for item in receipts}) == 1
        assert sorted(item.replayed for item in receipts) == [False, True]
        with factory() as session:
            assert session.scalar(select(func.count()).select_from(AgentRun)) == 1
            assert session.scalar(select(func.count()).select_from(AgentCommand)) == 1
            assert session.scalar(select(func.count()).select_from(AgentEvent)) == 1
            assert session.scalar(select(func.count()).select_from(OutboxMessage)) == 1
    finally:
        engine.dispose()


def test_inspect_and_follow_use_durable_monotonic_cursor(agent_session_factory) -> None:
    agent = SqlEvidenceAgent(agent_session_factory)
    receipt = agent.submit(_open())

    view = agent.inspect(GetRun(receipt.run_id))
    assert view.id == receipt.run_id
    assert view.status is RunStatus.QUEUED
    assert view.scope_snapshot.space_id == 1
    assert view.last_event_cursor > 0

    async def replay_events():
        frames = []
        stream = agent.follow(receipt.run_id, cursor=0)
        frames.append(await stream.__anext__())
        await stream.aclose()
        return frames

    frames = asyncio.run(replay_events())
    assert [frame.event_type for frame in frames] == ["run.opened"]
    assert frames[0].cursor == view.last_event_cursor


def test_follow_resets_and_replays_public_history_for_bootstrap_or_invalid_future_cursor(
    agent_session_factory,
) -> None:
    agent = SqlEvidenceAgent(agent_session_factory)
    opened = agent.submit(_open(request_id="sse-bootstrap-history"))
    with agent_session_factory.begin() as session:
        run = session.get(AgentRun, opened.run_id)
        assert run is not None
        run.status = RunStatus.AWAITING_INPUT.value
        run.version = 2
        journal = SqlAgentJournal(session)
        journal.append_event(
            run,
            event_type="model.started",
            payload={"secret": "never public"},
            visibility="internal",
        )
        evidence = journal.append_event(
            run,
            event_type="evidence.added",
            payload={"evidence_id": "evidence-bootstrap"},
        )
        interaction = journal.append_event(
            run,
            event_type="interaction.required",
            payload={"kind": "clarification", "gate_id": "gate-bootstrap"},
        )
        journal.append_event(
            run,
            event_type="model.finished",
            payload={"secret": "still never public"},
            visibility="internal",
        )
        session.flush()
        evidence_cursor = evidence.id
        interaction_cursor = interaction.id

    async def take(cursor: int | None, count: int):
        stream = agent.follow(opened.run_id, cursor=cursor)
        try:
            return [await stream.__anext__() for _ in range(count)]
        finally:
            await stream.aclose()

    bootstrap = asyncio.run(take(None, 4))
    future_reset = asyncio.run(take(interaction_cursor + 10_000, 4))
    reconnect = asyncio.run(take(opened.cursor, 2))

    assert [(frame.event_type, frame.cursor) for frame in bootstrap] == [
        ("sync", 0),
        ("run.opened", opened.cursor),
        ("evidence.added", evidence_cursor),
        ("interaction.required", interaction_cursor),
    ]
    assert [(frame.event_type, frame.cursor) for frame in future_reset] == [
        ("sync", 0),
        ("run.opened", opened.cursor),
        ("evidence.added", evidence_cursor),
        ("interaction.required", interaction_cursor),
    ]
    assert [(frame.event_type, frame.cursor) for frame in reconnect] == [
        ("evidence.added", evidence_cursor),
        ("interaction.required", interaction_cursor),
    ]
    assert agent.inspect(GetRun(opened.run_id)).last_event_cursor == interaction_cursor


def test_idle_non_terminal_follow_emits_heartbeat_without_advancing_cursor(
    agent_session_factory,
) -> None:
    ticks = 0

    def clock() -> float:
        nonlocal ticks
        ticks += 1
        return float(ticks)

    agent = SqlEvidenceAgent(
        agent_session_factory,
        follow_poll_seconds=0,
        heartbeat_interval_seconds=0.5,
        follow_clock=clock,
    )
    opened = agent.submit(_open(request_id="sse-heartbeat"))
    with agent_session_factory() as session:
        before = session.scalar(select(func.count()).select_from(AgentEvent))

    async def next_frame():
        stream = agent.follow(opened.run_id, cursor=opened.cursor)
        try:
            return await stream.__anext__()
        finally:
            await stream.aclose()

    heartbeat = asyncio.run(next_frame())
    with agent_session_factory() as session:
        after = session.scalar(select(func.count()).select_from(AgentEvent))

    assert heartbeat.event_type == "heartbeat"
    assert heartbeat.cursor == opened.cursor
    assert before == after == 1


def test_cancel_uses_expected_version_and_execution_fence(agent_session_factory) -> None:
    agent = SqlEvidenceAgent(agent_session_factory)
    opened = agent.submit(_open())

    cancelled = agent.submit(
        SignalRun(
            request_id="req-cancel",
            run_id=opened.run_id,
            expected_version=opened.run_version,
            signal=SignalKind.CANCEL,
        )
    )

    assert cancelled.status is RunStatus.CANCELLED
    assert cancelled.run_version == 2
    view = agent.inspect(GetRun(opened.run_id))
    assert view.execution_epoch == 1

    with pytest.raises(ServiceError) as raised:
        agent.submit(
            SignalRun(
                request_id="req-stale",
                run_id=opened.run_id,
                expected_version=1,
                signal=SignalKind.PAUSE,
            )
        )
    assert raised.value.code == "STALE_RUN_VERSION"


def test_concurrent_pause_and_cancel_use_atomic_expected_version(tmp_path) -> None:
    database_path = tmp_path / "concurrent-signal.db"
    engine = create_database_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory.begin() as session:
        session.add(KnowledgeSpace(id=1, name="Concurrent signals"))

    agent = SqlEvidenceAgent(factory)
    runner = AgentRunner(factory, lambda _request: pytest.fail("search must not run"))
    opened = agent.submit(_open(request_id="concurrent-signal-open"))
    routing = runner.advance_one(
        opened.run_id,
        expected_version=opened.run_version,
        execution_epoch=0,
    )
    running = runner.advance_one(
        opened.run_id,
        expected_version=routing.version,
        execution_epoch=0,
    )
    assert running.status is RunStatus.RUNNING

    update_barrier = Barrier(2)
    thread_state = local()

    def synchronize_run_updates(
        _connection,
        _cursor,
        statement,
        _parameters,
        _context,
        _executemany,
    ) -> None:
        if (
            not getattr(thread_state, "synchronized", False)
            and statement.lstrip().startswith("UPDATE agent_runs")
        ):
            thread_state.synchronized = True
            update_barrier.wait(timeout=5)

    sqlalchemy_event.listen(engine, "before_cursor_execute", synchronize_run_updates)
    outcomes: list[object] = []

    def submit(signal: SignalKind, request_id: str) -> None:
        try:
            outcomes.append(
                agent.submit(
                    SignalRun(
                        request_id=request_id,
                        run_id=opened.run_id,
                        expected_version=running.version,
                        signal=signal,
                    )
                )
            )
        except Exception as exc:  # noqa: BLE001 - the regression rejects raw DB failures.
            outcomes.append(exc)

    threads = [
        Thread(target=submit, args=(SignalKind.PAUSE, "concurrent-pause")),
        Thread(target=submit, args=(SignalKind.CANCEL, "concurrent-cancel")),
    ]
    try:
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
        assert all(not thread.is_alive() for thread in threads)
    finally:
        sqlalchemy_event.remove(engine, "before_cursor_execute", synchronize_run_updates)

    successes = [item for item in outcomes if not isinstance(item, Exception)]
    failures = [item for item in outcomes if isinstance(item, Exception)]
    assert len(successes) == 1
    assert len(failures) == 1
    assert isinstance(failures[0], ServiceError)
    assert failures[0].code == "STALE_RUN_VERSION"
    assert failures[0].status_code == 409

    Base.metadata.drop_all(engine)
    engine.dispose()


def _index_source(agent_session_factory, *, title: str, content: str) -> Source:
    with agent_session_factory() as session:
        source = Source(
            space_id=1,
            source_type="document",
            title=title,
            file_size=len(content),
            status="uploaded",
        )
        session.add(source)
        session.commit()
        session.refresh(source)
        evidence_index = SqlEvidenceIndex(session)
        staged = evidence_index.command(
            StageRevision(
                command_id=f"stage-{title}",
                draft=RevisionDraft(
                    source_id=source.id,
                    content_hash=sha256(content.encode()).hexdigest(),
                    index_version="v5-test",
                    collection_name="v5-test",
                    chunks=(
                        ChunkDraft(
                            chunk_index=0,
                            modality="text",
                            content=content,
                            locator={"kind": "text", "heading": title},
                        ),
                    ),
                ),
            )
        )
        revision = evidence_index.query(GetRevision(staged.revision_id))
        evidence_index.command(
            ActivateRevision(
                command_id=f"activate-{title}",
                revision_id=staged.revision_id,
                verified_points=tuple(
                    VerifiedPoint(point_id=point.point_id, payload_digest=point.payload_digest)
                    for point in revision.points
                ),
            )
        )
        session.refresh(source)
        session.expunge(source)
        return source


def _index_source_chunks(
    agent_session_factory,
    *,
    title: str,
    contents: tuple[str, ...],
) -> Source:
    with agent_session_factory() as session:
        source = Source(
            space_id=1,
            source_type="document",
            title=title,
            file_size=sum(len(item) for item in contents),
            status="uploaded",
        )
        session.add(source)
        session.commit()
        session.refresh(source)
        evidence_index = SqlEvidenceIndex(session)
        staged = evidence_index.command(
            StageRevision(
                command_id=f"stage-{title}",
                draft=RevisionDraft(
                    source_id=source.id,
                    content_hash=sha256("\n".join(contents).encode()).hexdigest(),
                    index_version="v5-test",
                    collection_name="v5-test",
                    chunks=tuple(
                        ChunkDraft(
                            chunk_index=index,
                            modality="text",
                            content=content,
                            locator={"kind": "pdf_page", "page": index + 1},
                        )
                        for index, content in enumerate(contents)
                    ),
                ),
            )
        )
        revision = evidence_index.query(GetRevision(staged.revision_id))
        evidence_index.command(
            ActivateRevision(
                command_id=f"activate-{title}",
                revision_id=staged.revision_id,
                verified_points=tuple(
                    VerifiedPoint(point_id=point.point_id, payload_digest=point.payload_digest)
                    for point in revision.points
                ),
            )
        )
        session.refresh(source)
        session.expunge(source)
        return source


def _runner(agent_session_factory) -> AgentRunner:
    def search(request):
        with agent_session_factory() as session:
            return SqlEvidenceIndex(session).search(request)

    return AgentRunner(agent_session_factory, search)


def _drain(agent: SqlEvidenceAgent, runner: AgentRunner, run_id: str, *, max_slices: int = 20):
    terminal = {
        RunStatus.COMPLETED,
        RunStatus.INSUFFICIENT_EVIDENCE,
        RunStatus.CANCELLED,
        RunStatus.FAILED,
    }
    for _ in range(max_slices):
        view = agent.inspect(GetRun(run_id))
        if view.status in terminal:
            return view
        result = runner.advance_one(
            run_id,
            expected_version=view.version,
            execution_epoch=view.execution_epoch,
        )
        assert result.applied is True
    raise AssertionError("Agent run did not terminate within the bounded test slices.")


def test_quick_run_has_zero_plan_and_produces_claim_level_provenance(agent_session_factory) -> None:
    _index_source(
        agent_session_factory,
        title="quick-source",
        content="alpha evidence establishes the measured latency is 42 ms",
    )
    agent = SqlEvidenceAgent(agent_session_factory)
    runner = _runner(agent_session_factory)
    opened = agent.submit(_open(goal="alpha evidence"))

    completed = _drain(agent, runner, opened.run_id)

    assert completed.status is RunStatus.COMPLETED
    artifact = agent.inspect(GetArtifact(completed.final_artifact_id or ""))
    assert artifact.status == "final"
    assert artifact.claims
    assert all(claim.kind != "factual" or claim.evidence_ids for claim in artifact.claims)
    evidence = agent.inspect(GetEvidence(artifact.claims[0].evidence_ids[0]))
    assert evidence.revision_id > 0
    assert evidence.index_revision_id > 0
    assert evidence.content_hash
    with agent_session_factory() as session:
        assert session.scalar(select(func.count()).select_from(AgentPlan)) == 0
        assert session.scalar(select(func.count()).select_from(AgentArtifact)) == 1
        assert session.scalar(select(func.count()).select_from(AgentClaim)) >= 1
        assert session.scalar(select(func.count()).select_from(ClaimEvidence)) >= 1
        event_types = session.scalars(
            select(AgentEvent.event_type).where(AgentEvent.run_id == opened.run_id)
        ).all()
        assert "plan.created" not in event_types
        assert "artifact.finalized" in event_types


def test_artifact_catalog_filters_distinct_artifacts_by_claim_evidence_source(
    agent_session_factory,
) -> None:
    alpha = _index_source(
        agent_session_factory,
        title="alpha-source-artifacts",
        content="orion latency datum is 42 ms and orion cost datum is 7 yuan",
    )
    beta = _index_source(
        agent_session_factory,
        title="beta-source-artifacts",
        content="zephyr cost record is 18 yuan",
    )
    agent = SqlEvidenceAgent(agent_session_factory)
    runner = _runner(agent_session_factory)
    alpha_run = agent.submit(
        _open(
            request_id="source-artifact-alpha",
            goal="orion latency datum; orion cost datum",
            mode=RunMode.FORCE_AGENT,
        )
    )
    beta_run = agent.submit(
        _open(
            request_id="source-artifact-beta",
            goal="zephyr cost record",
        )
    )

    alpha_completed = _drain(agent, runner, alpha_run.run_id)
    beta_completed = _drain(agent, runner, beta_run.run_id)
    alpha_artifact = agent.inspect(GetArtifact(alpha_completed.final_artifact_id or ""))
    alpha_catalog = agent.inspect(ListArtifacts(source_id=alpha.id))
    beta_catalog = agent.inspect(ListArtifacts(source_id=beta.id))

    assert len(alpha_artifact.claims) == 2
    assert [item.id for item in alpha_catalog.items] == [alpha_completed.final_artifact_id]
    assert [item.id for item in beta_catalog.items] == [beta_completed.final_artifact_id]
    assert alpha_catalog.items[0].id != beta_catalog.items[0].id


def test_direct_real_run_without_model_fails_instead_of_using_recording_fallback(
    agent_session_factory,
) -> None:
    agent = SqlEvidenceAgent(agent_session_factory)
    runner = _runner(agent_session_factory)
    opened = agent.submit(
        _open(
            request_id="req-real-no-model",
            goal="跨来源真实研究",
            mode=RunMode.FORCE_AGENT,
            provider_mode="real",
        )
    )

    dispatched = runner.advance_one(
        opened.run_id,
        expected_version=opened.run_version,
        execution_epoch=0,
    )
    failed = runner.advance_one(
        opened.run_id,
        expected_version=dispatched.version,
        execution_epoch=0,
    )

    assert failed.status is RunStatus.FAILED
    assert failed.reason == "llm_not_configured"
    view = agent.inspect(GetRun(opened.run_id))
    assert view.final_artifact_id is None
    assert view.termination_reason == "llm_not_configured"


def test_agent_mode_plans_multiple_requirements_and_retrieves_each(agent_session_factory) -> None:
    _index_source(agent_session_factory, title="alpha", content="alpha 成本事实是每月 10 元")
    _index_source(agent_session_factory, title="beta", content="beta 性能事实是延迟 20 毫秒")
    agent = SqlEvidenceAgent(agent_session_factory)
    runner = _runner(agent_session_factory)
    opened = agent.submit(
        _open(
            request_id="req-agent",
            goal="alpha 成本事实；beta 性能事实",
            mode=RunMode.FORCE_AGENT,
            budget=BudgetLimits(max_steps=6, max_tool_calls=6, max_model_calls=2),
        )
    )

    completed = _drain(agent, runner, opened.run_id)

    assert completed.status is RunStatus.COMPLETED
    with agent_session_factory() as session:
        assert session.scalar(select(func.count()).select_from(AgentPlan)) == 1
        assert session.scalar(select(func.count()).select_from(AgentEvidence)) == 2
        event_types = session.scalars(
            select(AgentEvent.event_type).where(AgentEvent.run_id == opened.run_id)
        ).all()
        assert "plan.created" in event_types
        assert event_types.count("tool.completed") == 2


def test_agent_opens_retrieved_evidence_and_reads_bounded_neighbors(
    agent_session_factory,
) -> None:
    _index_source_chunks(
        agent_session_factory,
        title="context-window-source",
        contents=(
            "background before the measured result",
            "orion measured latency is exactly 42 ms",
            "background after the measured result",
        ),
    )
    agent = SqlEvidenceAgent(agent_session_factory)

    def search(request):
        with agent_session_factory() as session:
            return SqlEvidenceIndex(session).search(request)

    def query_evidence(request):
        with agent_session_factory() as session:
            return SqlEvidenceIndex(session).query(request)

    runner = AgentRunner(
        agent_session_factory,
        search,
        evidence_query=query_evidence,
    )
    opened = agent.submit(
        _open(
            request_id="agent-bounded-neighbor-tools",
            goal="orion measured latency is exactly 42 ms",
            mode=RunMode.FORCE_AGENT,
            budget=BudgetLimits(max_steps=12, max_tool_calls=8, max_model_calls=3),
        )
    )

    completed = _drain(agent, runner, opened.run_id, max_slices=30)

    assert completed.status is RunStatus.COMPLETED
    with agent_session_factory() as session:
        started_tool_ids = list(
            session.scalars(
                select(AgentEvent.tool_call_id)
                .where(
                    AgentEvent.run_id == opened.run_id,
                    AgentEvent.event_type == "tool.started",
                )
                .order_by(AgentEvent.run_sequence)
            )
        )
        tool_names = [
            session.get(AgentToolCall, tool_call_id).tool_name
            for tool_call_id in started_tool_ids
            if tool_call_id is not None
        ]
        relations = set(
            session.scalars(
                select(RequirementEvidence.relation)
                .join(AgentRequirement, AgentRequirement.id == RequirementEvidence.requirement_id)
                .where(AgentRequirement.run_id == opened.run_id)
            )
        )
    assert tool_names[:3] == ["search_evidence", "open_evidence", "read_neighbors"]
    assert "supports" in relations
    assert "contextual" in relations


def test_missing_evidence_is_a_normal_insufficient_outcome(agent_session_factory) -> None:
    agent = SqlEvidenceAgent(agent_session_factory)
    runner = _runner(agent_session_factory)
    opened = agent.submit(_open(request_id="req-empty", goal="不存在的精确事实"))

    outcome = _drain(agent, runner, opened.run_id)

    assert outcome.status is RunStatus.INSUFFICIENT_EVIDENCE
    assert outcome.termination_reason == "required_evidence_missing"
    with agent_session_factory() as session:
        assert session.scalar(select(func.count()).select_from(AgentArtifact)) == 1


def test_conflicting_quantitative_evidence_is_surfaced_as_contested(agent_session_factory) -> None:
    _index_source(agent_session_factory, title="cost-a", content="该方案的成本是 10 元")
    _index_source(agent_session_factory, title="cost-b", content="该方案的成本是 20 元")
    agent = SqlEvidenceAgent(agent_session_factory)
    runner = _runner(agent_session_factory)
    opened = agent.submit(_open(request_id="req-conflict", goal="该方案的成本"))

    completed = _drain(agent, runner, opened.run_id)
    artifact = agent.inspect(GetArtifact(completed.final_artifact_id or ""))

    assert completed.status is RunStatus.COMPLETED
    assert len(artifact.claims) == 1
    assert artifact.claims[0].verification_status == "contested"
    assert len(artifact.claims[0].evidence_ids) == 2
    assert "冲突" in artifact.body_markdown
    with agent_session_factory() as session:
        relations = set(session.scalars(select(ClaimEvidence.relation)).all())
        assert relations == {"supports", "contradicts"}


def test_duplicate_worker_wakeup_is_absorbed_by_run_version(agent_session_factory) -> None:
    agent = SqlEvidenceAgent(agent_session_factory)
    runner = _runner(agent_session_factory)
    opened = agent.submit(_open(request_id="req-duplicate-wakeup"))

    first = runner.advance_one(
        opened.run_id,
        expected_version=opened.run_version,
        execution_epoch=0,
    )
    replay = runner.advance_one(
        opened.run_id,
        expected_version=opened.run_version,
        execution_epoch=0,
    )

    assert first.applied is True
    assert replay.applied is False
    assert replay.reason == "stale_wakeup"


def test_cancel_during_blocking_search_discards_returned_work(agent_session_factory) -> None:
    _index_source(agent_session_factory, title="cancel-source", content="cancel fence evidence")
    agent = SqlEvidenceAgent(agent_session_factory)
    opened = agent.submit(_open(request_id="req-cancel-fence", goal="cancel fence evidence"))

    def real_search(request):
        with agent_session_factory() as session:
            return SqlEvidenceIndex(session).search(request)

    entered = Event()
    release = Event()

    def blocking_search(request):
        entered.set()
        assert release.wait(timeout=5)
        return real_search(request)

    runner = AgentRunner(agent_session_factory, blocking_search)
    for _ in range(2):
        view = agent.inspect(GetRun(opened.run_id))
        runner.advance_one(
            opened.run_id,
            expected_version=view.version,
            execution_epoch=view.execution_epoch,
        )
    running = agent.inspect(GetRun(opened.run_id))
    assert running.status is RunStatus.RUNNING

    returned: list = []
    worker = Thread(
        target=lambda: returned.append(
            runner.advance_one(
                opened.run_id,
                expected_version=running.version,
                execution_epoch=running.execution_epoch,
            )
        )
    )
    worker.start()
    assert entered.wait(timeout=5)
    reserved = agent.inspect(GetRun(opened.run_id))
    cancelled = agent.submit(
        SignalRun(
            request_id="req-cancel-in-flight",
            run_id=opened.run_id,
            expected_version=reserved.version,
            signal=SignalKind.CANCEL,
        )
    )
    release.set()
    worker.join(timeout=5)

    assert not worker.is_alive()
    assert cancelled.status is RunStatus.CANCELLED
    assert returned and returned[0].applied is False
    with agent_session_factory() as session:
        assert session.scalar(select(func.count()).select_from(AgentEvidence)) == 0
        assert session.scalar(select(func.count()).select_from(AgentArtifact)) == 0
        tool = session.scalar(select(AgentToolCall).where(AgentToolCall.run_id == opened.run_id))
        assert tool is not None
        assert tool.status == "abandoned"
