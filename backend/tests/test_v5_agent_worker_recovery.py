from __future__ import annotations

from datetime import UTC, datetime, timedelta
from threading import Barrier, Event, Thread
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base
from app.core.config import settings
from app.models.agent_event import AgentCheckpoint, AgentEvent
from app.models.agent_run import AgentModelCall, AgentRun, AgentToolCall
from app.models.knowledge_space import KnowledgeSpace
from app.models.outbox import OutboxMessage
from app.modules.evidence_agent.contracts import (
    BudgetLimits,
    DeliverableSpec,
    GetRun,
    OpenRun,
    PermissionPolicy,
    RunMode,
    RunStatus,
    ScopeSelector,
)
from app.modules.evidence_agent.controller import AgentRunner
from app.modules.evidence_agent.recovery import AgentInvocationRecovery
from app.modules.evidence_agent.service import SqlEvidenceAgent
from app.modules.evidence_index import EvidenceSearchResult
from app.services.agent_model import (
    AgentModelResult,
    AgentModelUsage,
    RecordingAgentModel,
    RouteDecision,
)
from app.services.outbox_dispatcher import OutboxDispatcher
from app.services.task_broker import RedisRQTaskBroker, TaskEnvelope
from app.tasks import agent_tasks


class RecordingBroker:
    def __init__(self, *, fail_first: bool = False) -> None:
        self.fail_first = fail_first
        self.envelopes: list[TaskEnvelope] = []

    def publish(self, envelope: TaskEnvelope) -> str:
        if self.fail_first:
            self.fail_first = False
            raise RuntimeError("redis temporarily unavailable")
        self.envelopes.append(envelope)
        return envelope.task_id


def _factory():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine, expire_on_commit=False)


def _message(message_id: str = "outbox-1") -> OutboxMessage:
    return OutboxMessage(
        id=message_id,
        topic="agent.advance",
        aggregate_type="agent_run",
        aggregate_id="run-1",
        dedupe_key="agent.advance:run-1:1:0",
        payload_json='{"execution_epoch":0,"run_id":"run-1","version":1}',
        status="pending",
    )


def _open(request_id: str, *, mode: RunMode = RunMode.FORCE_QUICK) -> OpenRun:
    return OpenRun(
        request_id=request_id,
        space_id=1,
        goal="recover the missing fact",
        scope=ScopeSelector(),
        deliverable=DeliverableSpec(kind="answer"),
        mode=mode,
        budget=BudgetLimits(max_steps=4, max_tool_calls=3, max_model_calls=2),
        permissions=PermissionPolicy(read_only=True),
        provider_mode="recording",
    )


class SimulatedProcessDeath(BaseException):
    pass


class DyingAgentModel:
    provider_name = "dying-provider"
    model_name = "dying-model"

    def route(self, _request, *, allow_repair: bool = True):
        del allow_repair
        raise SimulatedProcessDeath


def test_expired_claim_before_external_call_requeues_from_safe_checkpoint() -> None:
    engine, factory = _factory()
    try:
        with factory.begin() as session:
            session.add(KnowledgeSpace(id=1, name="Recovery", description="test"))
        agent = SqlEvidenceAgent(factory)
        opened = agent.submit(_open("recover-before-external"))
        now = datetime.now(UTC)
        with factory.begin() as session:
            run = session.get(AgentRun, opened.run_id)
            wakeup = session.scalar(
                select(OutboxMessage).where(OutboxMessage.aggregate_id == opened.run_id)
            )
            assert run is not None and wakeup is not None
            run.lease_owner = "dead-runner"
            run.lease_expires_at = now - timedelta(seconds=1)
            wakeup.status = "published"
            wakeup.published_at = now - timedelta(seconds=1)

        recovered = AgentInvocationRecovery(factory).recover_once(
            stale_after_seconds=1_800
        )

        assert recovered.requeued == 1
        assert recovered.failed == 0
        view = agent.inspect(GetRun(opened.run_id))
        assert view.status is RunStatus.QUEUED
        assert view.version == opened.run_version
        assert view.execution_epoch == 1
        with factory() as session:
            wakeups = session.scalars(
                select(OutboxMessage)
                .where(OutboxMessage.aggregate_id == opened.run_id)
            ).all()
            assert sorted(item.status for item in wakeups) == ["pending", "published"]
            recovered_wakeup = next(item for item in wakeups if item.dedupe_key.endswith(":1"))
            assert recovered_wakeup.status == "pending"

        resumed = AgentRunner(
            factory,
            lambda _request: EvidenceSearchResult(hits=()),
        ).advance_one(
            opened.run_id,
            expected_version=view.version,
            execution_epoch=view.execution_epoch,
        )
        assert resumed.applied is True
        assert resumed.status is RunStatus.ROUTING
    finally:
        engine.dispose()


def test_failed_slice_keeps_an_expired_claim_until_recovery_requeues_one_wakeup() -> None:
    """A consumed wake-up must survive a slice failure without replaying its effect."""

    engine, factory = _factory()
    try:
        with factory.begin() as session:
            session.add(KnowledgeSpace(id=1, name="Failed slice", description="test"))
        agent = SqlEvidenceAgent(factory)
        opened = agent.submit(_open("failed-slice-recovery"))
        with factory.begin() as session:
            delivered = session.scalar(
                select(OutboxMessage).where(OutboxMessage.aggregate_id == opened.run_id)
            )
            assert delivered is not None
            delivered.status = "published"
            delivered.published_at = datetime.now(UTC)

        should_fail = True

        def fail_the_committing_slice(session: Session) -> None:
            nonlocal should_fail
            if should_fail and any(
                isinstance(item, AgentEvent) and item.event_type == "run.status_changed"
                for item in session.identity_map.values()
            ):
                should_fail = False
                raise RuntimeError("simulated slice transaction failure")

        event.listen(factory.class_, "before_commit", fail_the_committing_slice)
        runner = AgentRunner(factory, lambda _request: EvidenceSearchResult(hits=()))
        try:
            with pytest.raises(RuntimeError, match="simulated slice transaction failure"):
                runner.advance_one(
                    opened.run_id,
                    expected_version=opened.run_version,
                    execution_epoch=0,
                )
        finally:
            event.remove(factory.class_, "before_commit", fail_the_committing_slice)

        with factory() as session:
            interrupted = session.get(AgentRun, opened.run_id)
            assert interrupted is not None
            assert interrupted.version == opened.run_version
            assert interrupted.status == RunStatus.QUEUED.value
            assert interrupted.lease_owner is not None
            assert interrupted.lease_expires_at is not None
            lease_expires_at = interrupted.lease_expires_at
            if lease_expires_at.tzinfo is None:
                lease_expires_at = lease_expires_at.replace(tzinfo=UTC)
            assert lease_expires_at <= datetime.now(UTC)

        recovered = AgentInvocationRecovery(factory).recover_once(stale_after_seconds=1_800)
        recovered_again = AgentInvocationRecovery(factory).recover_once(stale_after_seconds=1_800)

        assert recovered.requeued == 1
        assert recovered.failed == 0
        assert recovered_again.requeued == 0
        with factory() as session:
            run = session.get(AgentRun, opened.run_id)
            assert run is not None
            assert run.execution_epoch == 1
            assert run.lease_owner is None
            wakeups = list(
                session.scalars(
                    select(OutboxMessage)
                    .where(OutboxMessage.aggregate_id == opened.run_id)
                    .order_by(OutboxMessage.created_at, OutboxMessage.id)
                )
            )
            assert len(wakeups) == 2
            assert sorted(wakeup.status for wakeup in wakeups) == ["pending", "published"]
            recovered_wakeup = next(wakeup for wakeup in wakeups if wakeup.status == "pending")
            assert recovered_wakeup.dedupe_key == (
                f"agent.advance:{opened.run_id}:{opened.run_version}:1"
            )
    finally:
        engine.dispose()


def test_claim_transaction_failure_at_task_seam_is_safe_to_retry_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine, factory = _factory()
    try:
        with factory.begin() as session:
            session.add(KnowledgeSpace(id=1, name="Claim retry", description="test"))
        agent = SqlEvidenceAgent(factory)
        opened = agent.submit(_open("claim-transaction-retry"))
        with factory.begin() as session:
            delivered = session.scalar(
                select(OutboxMessage).where(OutboxMessage.aggregate_id == opened.run_id)
            )
            assert delivered is not None
            delivered.status = "published"
            delivered.published_at = datetime.now(UTC)

        fail_claim = True

        def fail_the_claim(execute_state) -> None:
            nonlocal fail_claim
            statement = str(execute_state.statement).lower()
            if (
                fail_claim
                and execute_state.is_update
                and "update agent_runs" in statement
                and "lease_owner" in statement
            ):
                fail_claim = False
                raise RuntimeError("simulated claim database failure")

        event.listen(factory.class_, "do_orm_execute", fail_the_claim)
        runner = AgentRunner(factory, lambda _request: EvidenceSearchResult(hits=()))
        monkeypatch.setattr(agent_tasks, "get_agent_runner", lambda: runner)

        class NoopDispatcher:
            def __init__(self, *_args, **_kwargs) -> None:
                pass

            def dispatch_once(self, *, limit: int):
                del limit
                return None

        monkeypatch.setattr(agent_tasks, "OutboxDispatcher", NoopDispatcher)
        try:
            with pytest.raises(RuntimeError, match="simulated claim database failure"):
                agent_tasks.advance_agent_run(
                    opened.run_id,
                    opened.run_version,
                    0,
                )
        finally:
            event.remove(factory.class_, "do_orm_execute", fail_the_claim)

        retried = agent_tasks.advance_agent_run(opened.run_id, opened.run_version, 0)

        assert retried["applied"] is True
        assert retried["version"] == opened.run_version + 1
        with factory() as session:
            run = session.get(AgentRun, opened.run_id)
            assert run is not None
            assert run.version == opened.run_version + 1
            assert run.lease_owner is None
            assert session.scalar(
                select(func.count())
                .select_from(AgentEvent)
                .where(
                    AgentEvent.run_id == opened.run_id,
                    AgentEvent.event_type == "run.status_changed",
                )
            ) == 1
    finally:
        engine.dispose()


def test_unknown_claim_commit_is_fenced_until_lease_recovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A retry cannot duplicate a claim whose commit succeeded before its exception."""

    engine, factory = _factory()
    try:
        with factory.begin() as session:
            session.add(KnowledgeSpace(id=1, name="Claim outcome", description="test"))
        agent = SqlEvidenceAgent(factory)
        opened = agent.submit(_open("unknown-claim-commit"))
        with factory.begin() as session:
            delivered = session.scalar(
                select(OutboxMessage).where(OutboxMessage.aggregate_id == opened.run_id)
            )
            assert delivered is not None
            delivered.status = "published"
            delivered.published_at = datetime.now(UTC)

        claimed_at = datetime(2026, 1, 1, tzinfo=UTC)
        runner = AgentRunner(
            factory,
            lambda _request: EvidenceSearchResult(hits=()),
            claim_lease_seconds=30,
            utcnow=lambda: claimed_at,
        )
        monkeypatch.setattr(agent_tasks, "get_agent_runner", lambda: runner)

        class NoopDispatcher:
            def __init__(self, *_args, **_kwargs) -> None:
                pass

            def dispatch_once(self, *, limit: int):
                del limit
                return None

        monkeypatch.setattr(agent_tasks, "OutboxDispatcher", NoopDispatcher)

        def identify_claim(execute_state) -> None:
            statement = str(execute_state.statement).lower()
            if (
                execute_state.is_update
                and "update agent_runs" in statement
                and "lease_owner" in statement
            ):
                execute_state.session.info["raise_after_claim_commit"] = True

        def fail_after_claim_commit(session: Session) -> None:
            if session.info.pop("raise_after_claim_commit", False):
                raise RuntimeError("claim commit outcome was unknown to the task")

        event.listen(factory.class_, "do_orm_execute", identify_claim)
        event.listen(factory.class_, "after_commit", fail_after_claim_commit)
        try:
            with pytest.raises(RuntimeError, match="claim commit outcome was unknown"):
                agent_tasks.advance_agent_run(opened.run_id, opened.run_version, 0)
        finally:
            event.remove(factory.class_, "do_orm_execute", identify_claim)
            event.remove(factory.class_, "after_commit", fail_after_claim_commit)

        retried = agent_tasks.advance_agent_run(opened.run_id, opened.run_version, 0)
        assert retried["applied"] is False
        assert retried["reason"] == "lease_busy"

        recovered = AgentInvocationRecovery(
            factory,
            utcnow=lambda: claimed_at + timedelta(seconds=31),
        ).recover_once(stale_after_seconds=1_800)

        assert recovered.requeued == 1
        with factory() as session:
            run = session.get(AgentRun, opened.run_id)
            assert run is not None
            assert run.version == opened.run_version
            assert run.execution_epoch == 1
            assert run.lease_owner is None
            assert session.scalar(
                select(func.count())
                .select_from(AgentEvent)
                .where(
                    AgentEvent.run_id == opened.run_id,
                    AgentEvent.event_type == "run.status_changed",
                )
            ) == 0
            assert session.scalar(
                select(func.count())
                .select_from(OutboxMessage)
                .where(OutboxMessage.aggregate_id == opened.run_id)
            ) == 2
    finally:
        engine.dispose()


def test_agent_wakeup_rq_job_has_bounded_positive_retry_backoff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class CapturingQueue:
        def __init__(self, name: str, *, connection: object) -> None:
            captured["queue_name"] = name
            captured["connection"] = connection

        def enqueue(self, function: str, *arguments: object, **options: object):
            captured["function"] = function
            captured["arguments"] = arguments
            captured["options"] = options
            return SimpleNamespace(id="agent:run-claim:1:0")

    monkeypatch.setattr("redis.Redis.from_url", lambda _url: object())
    monkeypatch.setattr("rq.Queue", CapturingQueue)

    published_id = RedisRQTaskBroker().publish(
        TaskEnvelope(
            task_id="agent:run-claim:1:0",
            topic="agent.advance",
            payload={"run_id": "run-claim", "version": 1, "execution_epoch": 0},
        )
    )

    assert published_id == "agent:run-claim:1:0"
    options = captured["options"]
    assert isinstance(options, dict)
    retry = options["retry"]
    assert retry.max == settings.task_max_attempts
    assert retry.intervals
    assert all(interval > 0 for interval in retry.intervals)


@pytest.mark.parametrize(
    "replayable_tool",
    ["search_evidence", "open_evidence", "read_neighbors"],
)
def test_stale_read_only_call_is_fenced_requeued_and_resumed_from_checkpoint(
    replayable_tool: str,
) -> None:
    engine, factory = _factory()
    try:
        with factory.begin() as session:
            session.add(KnowledgeSpace(id=1, name="Recovery", description="test"))
        agent = SqlEvidenceAgent(factory)

        def die_after_prepare(_request):
            raise SimulatedProcessDeath

        runner = AgentRunner(factory, die_after_prepare)
        opened = agent.submit(_open("recover-read-only-search"))
        dispatched = runner.advance_one(
            opened.run_id,
            expected_version=opened.run_version,
            execution_epoch=0,
        )
        routed = runner.advance_one(
            opened.run_id,
            expected_version=dispatched.version,
            execution_epoch=0,
        )

        with pytest.raises(SimulatedProcessDeath):
            runner.advance_one(
                opened.run_id,
                expected_version=routed.version,
                execution_epoch=0,
            )

        with factory() as session:
            crashed_run = session.get(AgentRun, opened.run_id)
            crashed_call = session.scalar(
                select(AgentToolCall).where(AgentToolCall.run_id == opened.run_id)
            )
            prepared_checkpoint = session.scalar(
                select(AgentCheckpoint)
                .where(AgentCheckpoint.run_id == opened.run_id)
                .order_by(AgentCheckpoint.run_version.desc())
            )
            assert crashed_run is not None
            assert crashed_call is not None and crashed_call.status == "running"
            assert prepared_checkpoint is not None
            assert prepared_checkpoint.run_version == crashed_run.version
            crashed_call.tool_name = replayable_tool
            session.commit()

        recovery = AgentInvocationRecovery(factory)
        recovered = recovery.recover_once(stale_after_seconds=0)

        assert recovered.requeued == 1
        assert recovered.failed == 0
        with factory() as session:
            run = session.get(AgentRun, opened.run_id)
            tool = session.scalar(
                select(AgentToolCall).where(AgentToolCall.run_id == opened.run_id)
            )
            checkpoint = session.scalar(
                select(AgentCheckpoint)
                .where(AgentCheckpoint.run_id == opened.run_id)
                .order_by(AgentCheckpoint.run_version.desc())
            )
            latest_event = session.scalar(
                select(AgentEvent)
                .where(AgentEvent.run_id == opened.run_id)
                .order_by(AgentEvent.id.desc())
            )
            assert run is not None
            assert run.status == RunStatus.RUNNING.value
            assert run.execution_epoch == 1
            assert run.lease_owner is None
            assert tool is not None
            assert tool.status == "abandoned"
            assert tool.error_code == "worker_interrupted"
            assert checkpoint is not None and latest_event is not None
            assert checkpoint.execution_epoch == run.execution_epoch
            assert checkpoint.last_event_cursor == latest_event.id
            assert latest_event.event_type == "run.recovered"
            pending = session.scalar(
                select(OutboxMessage).where(
                    OutboxMessage.dedupe_key
                    == f"agent.advance:{run.id}:{run.version}:{run.execution_epoch}"
                )
            )
            assert pending is not None and pending.status == "pending"

        replacement = AgentRunner(factory, lambda _request: EvidenceSearchResult(hits=()))
        resumed_view = agent.inspect(GetRun(opened.run_id))
        resumed = replacement.advance_one(
            opened.run_id,
            expected_version=resumed_view.version,
            execution_epoch=resumed_view.execution_epoch,
        )

        assert resumed.status is RunStatus.INSUFFICIENT_EVIDENCE
        with factory() as session:
            assert session.scalar(
                select(AgentToolCall.id).where(AgentToolCall.status == "running")
            ) is None
    finally:
        engine.dispose()


def test_concurrent_recovery_passes_emit_one_wakeup(tmp_path, request) -> None:
    database_path = tmp_path / "agent-recovery-cas.db"
    engine = create_engine(
        f"sqlite:///{database_path.as_posix()}",
        connect_args={"check_same_thread": False, "timeout": 10},
    )
    request.addfinalizer(engine.dispose)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory.begin() as session:
        session.add(KnowledgeSpace(id=1, name="Recovery", description="test"))
    agent = SqlEvidenceAgent(factory)

    def die_after_prepare(_request):
        raise SimulatedProcessDeath

    runner = AgentRunner(factory, die_after_prepare)
    opened = agent.submit(_open("concurrent-recovery-pass"))
    dispatched = runner.advance_one(
        opened.run_id,
        expected_version=opened.run_version,
        execution_epoch=0,
    )
    routed = runner.advance_one(
        opened.run_id,
        expected_version=dispatched.version,
        execution_epoch=0,
    )
    with pytest.raises(SimulatedProcessDeath):
        runner.advance_one(
            opened.run_id,
            expected_version=routed.version,
            execution_epoch=0,
        )

    start_barrier = Barrier(2)
    results = []
    errors: list[BaseException] = []

    def recover() -> None:
        try:
            start_barrier.wait(timeout=5)
            results.append(
                AgentInvocationRecovery(factory).recover_once(stale_after_seconds=0)
            )
        except BaseException as exc:  # pragma: no cover - assertion reports details
            errors.append(exc)

    first = Thread(target=recover)
    second = Thread(target=recover)
    first.start()
    second.start()
    first.join(timeout=10)
    second.join(timeout=10)

    assert not first.is_alive() and not second.is_alive()
    assert errors == []
    assert sum(result.requeued for result in results) == 1
    with factory() as session:
        run = session.get(AgentRun, opened.run_id)
        assert run is not None and run.execution_epoch == 1
        assert session.scalar(
            select(func.count())
            .select_from(OutboxMessage)
            .where(
                OutboxMessage.dedupe_key
                == f"agent.advance:{run.id}:{run.version}:{run.execution_epoch}"
            )
        ) == 1
        assert session.scalar(
            select(AgentToolCall.id).where(AgentToolCall.status == "running")
        ) is None


def test_unknown_model_outcome_fails_closed_without_replaying_provider_call() -> None:
    engine, factory = _factory()
    try:
        with factory.begin() as session:
            session.add(KnowledgeSpace(id=1, name="Recovery", description="test"))
        agent = SqlEvidenceAgent(factory)
        runner = AgentRunner(
            factory,
            lambda _request: EvidenceSearchResult(hits=()),
            agent_model=DyingAgentModel(),
        )
        opened = agent.submit(_open("recover-model-call", mode=RunMode.AUTO))
        dispatched = runner.advance_one(
            opened.run_id,
            expected_version=opened.run_version,
            execution_epoch=0,
        )

        with pytest.raises(SimulatedProcessDeath):
            runner.advance_one(
                opened.run_id,
                expected_version=dispatched.version,
                execution_epoch=0,
            )

        recovered = AgentInvocationRecovery(factory).recover_once(stale_after_seconds=0)

        assert recovered.requeued == 0
        assert recovered.failed == 1
        with factory() as session:
            run = session.get(AgentRun, opened.run_id)
            model_call = session.scalar(
                select(AgentModelCall).where(AgentModelCall.run_id == opened.run_id)
            )
            checkpoint = session.scalar(
                select(AgentCheckpoint)
                .where(AgentCheckpoint.run_id == opened.run_id)
                .order_by(AgentCheckpoint.run_version.desc())
            )
            latest_event = session.scalar(
                select(AgentEvent)
                .where(AgentEvent.run_id == opened.run_id)
                .order_by(AgentEvent.id.desc())
            )
            assert run is not None
            assert run.status == RunStatus.FAILED.value
            assert run.termination_reason == "worker_interrupted_during_model_call"
            assert run.execution_epoch == 1
            assert model_call is not None
            assert model_call.status == "abandoned"
            assert model_call.error_code == "worker_interrupted_unknown_outcome"
            assert checkpoint is not None and latest_event is not None
            assert checkpoint.last_event_cursor == latest_event.id
            assert checkpoint.execution_epoch == run.execution_epoch
            assert latest_event.event_type == "run.failed"
            assert session.scalar(
                select(OutboxMessage.id).where(
                    OutboxMessage.dedupe_key
                    == f"agent.advance:{run.id}:{run.version}:{run.execution_epoch}"
                )
            ) is None
    finally:
        engine.dispose()


def test_crash_after_model_finish_checkpoint_fails_closed_without_replay() -> None:
    engine, factory = _factory()
    try:
        with factory.begin() as session:
            session.add(KnowledgeSpace(id=1, name="Recovery", description="test"))
        agent = SqlEvidenceAgent(factory)
        model = RecordingAgentModel(
            routes=(
                AgentModelResult(
                    value=RouteDecision(mode=RunMode.FORCE_QUICK.value),
                    usage=AgentModelUsage(input_tokens=5, output_tokens=2),
                    provider="recording",
                    model="recording-agent-v1",
                ),
            )
        )
        runner = AgentRunner(
            factory,
            lambda _request: EvidenceSearchResult(hits=()),
            agent_model=model,
        )
        opened = agent.submit(_open("recover-after-model-finish", mode=RunMode.AUTO))
        dispatched = runner.advance_one(
            opened.run_id,
            expected_version=opened.run_version,
            execution_epoch=0,
        )
        crashed = False

        def die_after_completed_model_commit(session) -> None:
            nonlocal crashed
            if crashed:
                return
            if any(
                isinstance(item, AgentModelCall) and item.status == "completed"
                for item in session.identity_map.values()
            ):
                crashed = True
                raise SimulatedProcessDeath

        event.listen(factory.class_, "after_commit", die_after_completed_model_commit)
        try:
            with pytest.raises(SimulatedProcessDeath):
                runner.advance_one(
                    opened.run_id,
                    expected_version=dispatched.version,
                    execution_epoch=0,
                )
        finally:
            event.remove(factory.class_, "after_commit", die_after_completed_model_commit)

        now = datetime.now(UTC)
        with factory.begin() as session:
            run = session.get(AgentRun, opened.run_id)
            assert run is not None
            assert run.status == RunStatus.ROUTING.value
            run.lease_owner = "dead-runner"
            run.lease_expires_at = now - timedelta(seconds=1)
            for wakeup in session.scalars(
                select(OutboxMessage).where(OutboxMessage.aggregate_id == opened.run_id)
            ):
                wakeup.status = "published"
                wakeup.published_at = now - timedelta(seconds=1)

        recovered = AgentInvocationRecovery(factory).recover_once(stale_after_seconds=1_800)

        assert recovered.requeued == 0
        assert recovered.failed == 1
        with factory() as session:
            run = session.get(AgentRun, opened.run_id)
            model_call = session.scalar(
                select(AgentModelCall).where(AgentModelCall.run_id == opened.run_id)
            )
            checkpoint = session.scalar(
                select(AgentCheckpoint)
                .where(AgentCheckpoint.run_id == opened.run_id)
                .order_by(AgentCheckpoint.run_version.desc())
            )
            latest_event = session.scalar(
                select(AgentEvent)
                .where(AgentEvent.run_id == opened.run_id)
                .order_by(AgentEvent.id.desc())
            )
            assert run is not None
            assert run.status == RunStatus.FAILED.value
            assert run.termination_reason == "worker_interrupted_after_model_call"
            assert model_call is not None and model_call.status == "completed"
            assert checkpoint is not None and latest_event is not None
            assert checkpoint.last_event_cursor == latest_event.id
            assert latest_event.event_type == "run.failed"
            assert session.scalar(
                select(AgentModelCall.id).where(AgentModelCall.status == "running")
            ) is None
    finally:
        engine.dispose()


def test_completed_model_call_advances_its_durable_checkpoint_cursor() -> None:
    engine, factory = _factory()
    try:
        with factory.begin() as session:
            session.add(KnowledgeSpace(id=1, name="Recovery", description="test"))
        agent = SqlEvidenceAgent(factory)
        model = RecordingAgentModel(
            routes=(
                AgentModelResult(
                    value=RouteDecision(mode=RunMode.FORCE_QUICK.value),
                    usage=AgentModelUsage(input_tokens=5, output_tokens=2),
                    provider="recording",
                    model="recording-agent-v1",
                ),
            )
        )
        runner = AgentRunner(
            factory,
            lambda _request: EvidenceSearchResult(hits=()),
            agent_model=model,
        )
        opened = agent.submit(_open("checkpoint-model-completion", mode=RunMode.AUTO))
        dispatched = runner.advance_one(
            opened.run_id,
            expected_version=opened.run_version,
            execution_epoch=0,
        )
        routed = runner.advance_one(
            opened.run_id,
            expected_version=dispatched.version,
            execution_epoch=0,
        )

        assert routed.applied is True
        with factory() as session:
            completed_event = session.scalar(
                select(AgentEvent)
                .where(
                    AgentEvent.run_id == opened.run_id,
                    AgentEvent.event_type == "model.completed",
                )
                .order_by(AgentEvent.id.desc())
            )
            assert completed_event is not None
            checkpoint = session.scalar(
                select(AgentCheckpoint).where(
                    AgentCheckpoint.run_id == opened.run_id,
                    AgentCheckpoint.run_version == completed_event.run_version,
                )
            )
            assert checkpoint is not None
            assert checkpoint.last_event_cursor == completed_event.id
    finally:
        engine.dispose()


def test_failed_model_call_advances_its_durable_checkpoint_cursor() -> None:
    engine, factory = _factory()
    try:
        with factory.begin() as session:
            session.add(KnowledgeSpace(id=1, name="Recovery", description="test"))
        agent = SqlEvidenceAgent(factory)
        model = RecordingAgentModel(routes=(RuntimeError("provider unavailable"),))
        runner = AgentRunner(
            factory,
            lambda _request: EvidenceSearchResult(hits=()),
            agent_model=model,
        )
        opened = agent.submit(_open("checkpoint-model-failure", mode=RunMode.AUTO))
        dispatched = runner.advance_one(
            opened.run_id,
            expected_version=opened.run_version,
            execution_epoch=0,
        )
        routed = runner.advance_one(
            opened.run_id,
            expected_version=dispatched.version,
            execution_epoch=0,
        )

        assert routed.applied is True
        with factory() as session:
            failed_event = session.scalar(
                select(AgentEvent)
                .where(
                    AgentEvent.run_id == opened.run_id,
                    AgentEvent.event_type == "model.failed",
                )
                .order_by(AgentEvent.id.desc())
            )
            assert failed_event is not None
            checkpoint = session.scalar(
                select(AgentCheckpoint).where(
                    AgentCheckpoint.run_id == opened.run_id,
                    AgentCheckpoint.run_version == failed_event.run_version,
                )
            )
            assert checkpoint is not None
            assert checkpoint.last_event_cursor == failed_event.id
    finally:
        engine.dispose()


def test_concurrent_worker_wakeups_atomically_claim_one_run_version(tmp_path, request) -> None:
    database_path = tmp_path / "agent-wakeup-cas.db"
    engine = create_engine(
        f"sqlite:///{database_path.as_posix()}",
        connect_args={"check_same_thread": False, "timeout": 10},
    )
    request.addfinalizer(engine.dispose)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory.begin() as session:
        session.add(KnowledgeSpace(id=1, name="Recovery", description="test"))
    agent = SqlEvidenceAgent(factory)
    runner = AgentRunner(factory, lambda _request: EvidenceSearchResult(hits=()))
    opened = agent.submit(_open("concurrent-worker-wakeup"))

    start_barrier = Barrier(2)
    results = []
    errors: list[BaseException] = []

    def advance() -> None:
        try:
            start_barrier.wait(timeout=5)
            results.append(
                runner.advance_one(
                    opened.run_id,
                    expected_version=opened.run_version,
                    execution_epoch=0,
                )
            )
        except BaseException as exc:  # pragma: no cover - assertion reports details
            errors.append(exc)

    first = Thread(target=advance)
    second = Thread(target=advance)
    first.start()
    second.start()
    first.join(timeout=10)
    second.join(timeout=10)

    assert not first.is_alive() and not second.is_alive()
    assert errors == []
    assert len(results) == 2
    assert sorted(result.applied for result in results) == [False, True]
    with factory() as session:
        assert session.scalar(
            select(func.count())
            .select_from(AgentEvent)
            .where(
                AgentEvent.run_id == opened.run_id,
                AgentEvent.event_type == "run.status_changed",
            )
        ) == 1
        assert session.scalar(
            select(func.count())
            .select_from(OutboxMessage)
            .where(OutboxMessage.aggregate_id == opened.run_id)
        ) == 2


def test_next_version_wakeup_crosses_the_previous_worker_release_barrier(tmp_path) -> None:
    """A committed next slice must be claimable before the old call unwinds."""

    database_path = tmp_path / "agent-cross-version-handoff.db"
    engine = create_engine(
        f"sqlite:///{database_path.as_posix()}",
        connect_args={"check_same_thread": False, "timeout": 10},
    )

    class BarrierSession(Session):
        pass

    factory = sessionmaker(
        bind=engine,
        class_=BarrierSession,
        expire_on_commit=False,
    )
    Base.metadata.create_all(engine)
    with factory.begin() as session:
        session.add(KnowledgeSpace(id=1, name="Cross-version handoff", description="test"))

    agent = SqlEvidenceAgent(factory)
    opened = agent.submit(_open("cross-version-handoff"))
    with factory.begin() as session:
        delivered = session.scalar(
            select(OutboxMessage).where(
                OutboxMessage.dedupe_key
                == f"agent.advance:{opened.run_id}:{opened.run_version}:0"
            )
        )
        assert delivered is not None
        delivered.status = "published"
        delivered.published_at = datetime.now(UTC)
    next_wakeup_committed = Event()
    release_previous_worker = Event()
    expected_next_key = f"agent.advance:{opened.run_id}:2:0"

    @event.listens_for(BarrierSession, "before_commit")
    def mark_next_wakeup(session: Session) -> None:
        if any(
            isinstance(item, OutboxMessage) and item.dedupe_key == expected_next_key
            for item in session.new
        ):
            session.info["block_after_next_wakeup"] = True

    @event.listens_for(BarrierSession, "after_commit")
    def block_previous_worker_after_commit(session: Session) -> None:
        if session.info.pop("block_after_next_wakeup", False):
            next_wakeup_committed.set()
            assert release_previous_worker.wait(timeout=5), "test did not release the previous worker"

    first_runner = AgentRunner(factory, lambda _request: EvidenceSearchResult(hits=()))
    next_runner = AgentRunner(factory, lambda _request: EvidenceSearchResult(hits=()))
    next_results = []

    class AdvancingBroker:
        def publish(self, envelope: TaskEnvelope) -> str:
            next_results.append(
                next_runner.advance_one(
                    str(envelope.payload["run_id"]),
                    expected_version=int(envelope.payload["version"]),
                    execution_epoch=int(envelope.payload["execution_epoch"]),
                )
            )
            return envelope.task_id

    first_results = []
    first_errors: list[BaseException] = []

    def advance_first_version() -> None:
        try:
            first_results.append(
                first_runner.advance_one(
                    opened.run_id,
                    expected_version=opened.run_version,
                    execution_epoch=0,
                )
            )
        except BaseException as exc:  # pragma: no cover - assertion reports the worker error
            first_errors.append(exc)

    previous_worker = Thread(target=advance_first_version)
    previous_worker.start()
    try:
        assert next_wakeup_committed.wait(timeout=5)
        dispatch_result = OutboxDispatcher(
            factory,
            AdvancingBroker(),
            worker_id="next-version-dispatcher",
        ).dispatch_once(
            limit=1,
        )
        next_result = next_results[0]
    finally:
        release_previous_worker.set()
        previous_worker.join(timeout=5)
        event.remove(BarrierSession, "before_commit", mark_next_wakeup)
        event.remove(BarrierSession, "after_commit", block_previous_worker_after_commit)

    try:
        assert not previous_worker.is_alive()
        assert first_errors == []
        assert len(first_results) == 1
        assert first_results[0].applied is True
        assert dispatch_result.published == 1
        assert next_result.applied is True
        assert next_result.version == 3
        with factory() as session:
            run = session.get(AgentRun, opened.run_id)
            assert run is not None
            assert run.version == 3
            assert run.status == RunStatus.RUNNING.value
            delivered_next = session.scalar(
                select(OutboxMessage).where(
                    OutboxMessage.dedupe_key
                    == f"agent.advance:{opened.run_id}:2:0"
                )
            )
            assert delivered_next is not None
            assert delivered_next.status == "published"
            assert session.scalar(
                select(func.count())
                .select_from(OutboxMessage)
                .where(
                    OutboxMessage.dedupe_key
                    == f"agent.advance:{opened.run_id}:3:0"
                )
            ) == 1
    finally:
        engine.dispose()


def test_matching_run_fence_with_an_active_lease_reports_lease_busy() -> None:
    engine, factory = _factory()
    try:
        with factory.begin() as session:
            session.add(KnowledgeSpace(id=1, name="Lease result", description="test"))
        agent = SqlEvidenceAgent(factory)
        opened = agent.submit(_open("lease-busy-result"))
        with factory.begin() as session:
            run = session.get(AgentRun, opened.run_id)
            assert run is not None
            run.lease_owner = "worker-still-running"
            run.lease_expires_at = datetime.now(UTC) + timedelta(minutes=5)

        result = AgentRunner(
            factory,
            lambda _request: EvidenceSearchResult(hits=()),
        ).advance_one(
            opened.run_id,
            expected_version=opened.run_version,
            execution_epoch=0,
        )

        assert result.applied is False
        assert result.reason == "lease_busy"
        assert result.version == opened.run_version
    finally:
        engine.dispose()



def test_outbox_publish_is_at_least_once_but_domain_task_id_is_deterministic() -> None:
    engine, factory = _factory()
    try:
        with factory.begin() as session:
            session.add(_message())
        broker = RecordingBroker()
        dispatcher = OutboxDispatcher(factory, broker, worker_id="dispatcher-test", retry_delay_seconds=0)

        first = dispatcher.dispatch_once()
        second = dispatcher.dispatch_once()

        assert first.published == 1
        assert second.claimed == 0
        assert len(broker.envelopes) == 1
        envelope = broker.envelopes[0]
        assert envelope.task_id == "agent:run-1:1:0"
        assert envelope.topic == "agent.advance"
        with factory() as session:
            message = session.get(OutboxMessage, "outbox-1")
            assert message is not None
            assert message.status == "published"
            assert message.published_at is not None
    finally:
        engine.dispose()


def test_failed_and_expired_outbox_leases_are_recoverable() -> None:
    engine, factory = _factory()
    try:
        with factory.begin() as session:
            failed = _message("outbox-retry")
            failed.dedupe_key = "agent.advance:run-1:2:0"
            failed.payload_json = '{"execution_epoch":0,"run_id":"run-1","version":2}'
            expired = _message("outbox-expired")
            expired.dedupe_key = "agent.advance:run-1:3:0"
            expired.payload_json = '{"execution_epoch":0,"run_id":"run-1","version":3}'
            expired.status = "publishing"
            expired.lease_owner = "dead-worker"
            expired.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
            session.add_all([failed, expired])

        broker = RecordingBroker(fail_first=True)
        dispatcher = OutboxDispatcher(factory, broker, worker_id="replacement", retry_delay_seconds=0)
        failed_attempt = dispatcher.dispatch_once(limit=1)
        recovered = dispatcher.dispatch_once(limit=5)

        assert failed_attempt.failed == 1
        assert recovered.published == 2
        assert {item.task_id for item in broker.envelopes} == {
            "agent:run-1:2:0",
            "agent:run-1:3:0",
        }
        with factory() as session:
            statuses = dict(session.execute(select(OutboxMessage.id, OutboxMessage.status)).all())
            assert statuses == {"outbox-retry": "published", "outbox-expired": "published"}
    finally:
        engine.dispose()
