from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Barrier, Event, Lock, Thread
import time

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base
from app.models.outbox import OutboxMessage
from app.services.outbox_dispatcher import OutboxDispatcher, new_dispatcher_worker_id
from app.services.task_broker import TaskEnvelope


class RecordingBroker:
    def __init__(self) -> None:
        self._lock = Lock()
        self.envelopes: list[TaskEnvelope] = []

    def publish(self, envelope: TaskEnvelope) -> str:
        with self._lock:
            self.envelopes.append(envelope)
        return envelope.task_id


class BlockingBroker(RecordingBroker):
    def __init__(self) -> None:
        super().__init__()
        self.entered = Event()
        self.release = Event()

    def publish(self, envelope: TaskEnvelope) -> str:
        super().publish(envelope)
        self.entered.set()
        assert self.release.wait(timeout=5), "test did not release the blocked publish"
        return envelope.task_id


def _memory_factory():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine, expire_on_commit=False)


def _file_factory(path: Path):
    engine = create_engine(
        f"sqlite:///{path.as_posix()}",
        connect_args={"check_same_thread": False, "timeout": 5},
    )
    Base.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine, expire_on_commit=False)


def _message(message_id: str = "outbox-1") -> OutboxMessage:
    return OutboxMessage(
        id=message_id,
        topic="agent.advance",
        aggregate_type="agent_run",
        aggregate_id="run-1",
        dedupe_key=f"agent.advance:{message_id}",
        payload_json='{"execution_epoch":0,"run_id":"run-1","version":1}',
        status="pending",
    )


@pytest.mark.parametrize("owners", [("dispatcher-a", "dispatcher-b"), ("shared-owner", "shared-owner")])
def test_two_dispatchers_atomically_claim_a_pending_message_once(
    tmp_path: Path,
    owners: tuple[str, str],
) -> None:
    engine, factory = _file_factory(tmp_path / f"atomic-outbox-{owners[0]}-{owners[1]}.db")
    select_barrier = Barrier(2)

    @event.listens_for(engine, "before_cursor_execute")
    def synchronize_candidate_reads(_conn, _cursor, statement, _parameters, _context, _executemany):
        normalized = " ".join(statement.lower().split())
        if normalized.startswith("select") and "order by outbox_messages.available_at" in normalized:
            select_barrier.wait(timeout=5)

    try:
        with factory.begin() as session:
            session.add(_message())
        broker = RecordingBroker()
        dispatchers = [
            OutboxDispatcher(factory, broker, worker_id=owners[0]),
            OutboxDispatcher(factory, broker, worker_id=owners[1]),
        ]
        start = Barrier(3)
        results = []
        errors: list[BaseException] = []

        def dispatch(dispatcher: OutboxDispatcher) -> None:
            start.wait(timeout=5)
            try:
                results.append(dispatcher.dispatch_once())
            except BaseException as exc:  # pragma: no cover - assertion reports the worker error
                errors.append(exc)

        threads = [Thread(target=dispatch, args=(dispatcher,)) for dispatcher in dispatchers]
        for thread in threads:
            thread.start()
        start.wait(timeout=5)
        for thread in threads:
            thread.join(timeout=10)

        assert not errors
        assert all(not thread.is_alive() for thread in threads)
        assert sum(result.published for result in results) == 1
        assert [envelope.task_id for envelope in broker.envelopes] == ["agent:run-1:1:0"]
    finally:
        event.remove(engine, "before_cursor_execute", synchronize_candidate_reads)
        engine.dispose()


def test_publish_renews_ownership_past_the_original_lease(tmp_path: Path) -> None:
    engine, factory = _file_factory(tmp_path / "lease-heartbeat.db")
    broker = BlockingBroker()
    try:
        with factory.begin() as session:
            session.add(_message())
        first = OutboxDispatcher(factory, broker, worker_id="slow-publisher", lease_seconds=1)
        replacement = OutboxDispatcher(factory, broker, worker_id="replacement", lease_seconds=1)
        first_result = []
        first_thread = Thread(target=lambda: first_result.append(first.dispatch_once()))
        first_thread.start()

        assert broker.entered.wait(timeout=5)
        time.sleep(1.35)
        replacement_result = replacement.dispatch_once()
        broker.release.set()
        first_thread.join(timeout=5)

        assert not first_thread.is_alive()
        assert replacement_result.claimed == 0
        assert first_result[0].published == 1
        assert [envelope.task_id for envelope in broker.envelopes] == ["agent:run-1:1:0"]
    finally:
        broker.release.set()
        engine.dispose()


def test_poison_message_isolated_with_bounded_backoff_and_dead_letter() -> None:
    engine, factory = _memory_factory()
    try:
        with factory.begin() as session:
            poison = _message("outbox-poison")
            poison.payload_json = "{}"
            valid = _message("outbox-valid")
            valid.payload_json = '{"execution_epoch":0,"run_id":"run-1","version":2}'
            session.add_all([poison, valid])

        broker = RecordingBroker()
        dispatcher = OutboxDispatcher(
            factory,
            broker,
            worker_id="poison-safe",
            retry_delay_seconds=2,
            max_retry_delay_seconds=3,
            max_attempts=3,
        )

        first_started = datetime.now(UTC).replace(tzinfo=None)
        first = dispatcher.dispatch_once(limit=2)
        assert first.published == 1
        assert first.failed == 1
        assert [envelope.task_id for envelope in broker.envelopes] == ["agent:run-1:2:0"]
        with factory.begin() as session:
            poison = session.get(OutboxMessage, "outbox-poison")
            assert poison is not None
            assert poison.status == "pending"
            assert poison.attempt == 1
            assert "KeyError" in (poison.last_error or "")
            assert timedelta(seconds=1.5) <= poison.available_at - first_started <= timedelta(seconds=2.5)
            poison.available_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=1)

        second_started = datetime.now(UTC).replace(tzinfo=None)
        second = dispatcher.dispatch_once()
        assert second.failed == 1
        with factory.begin() as session:
            poison = session.get(OutboxMessage, "outbox-poison")
            assert poison is not None
            assert poison.status == "pending"
            assert poison.attempt == 2
            assert timedelta(seconds=2.5) <= poison.available_at - second_started <= timedelta(seconds=3.5)
            poison.available_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=1)

        third = dispatcher.dispatch_once()
        exhausted = dispatcher.dispatch_once()
        assert third.failed == 1
        assert third.dead_lettered == 1
        assert exhausted.claimed == 0
        with factory() as session:
            poison = session.get(OutboxMessage, "outbox-poison")
            assert poison is not None
            assert poison.status == "dead_letter"
            assert poison.attempt == 3
            assert "KeyError" in (poison.last_error or "")

        assert dispatcher.retry_dead_letter("outbox-poison") is True
        with factory.begin() as session:
            poison = session.get(OutboxMessage, "outbox-poison")
            assert poison is not None
            assert poison.status == "pending"
            assert poison.attempt == 0
            assert "KeyError" in (poison.last_error or "")
            poison.payload_json = '{"execution_epoch":0,"run_id":"run-1","version":3}'

        retried = dispatcher.dispatch_once()
        assert retried.published == 1
        assert broker.envelopes[-1].task_id == "agent:run-1:3:0"
    finally:
        engine.dispose()


def test_dispatcher_worker_ids_include_host_process_and_unique_instance() -> None:
    first = new_dispatcher_worker_id("agent-task")
    second = new_dispatcher_worker_id("agent-task")

    first_parts = first.split(":")
    second_parts = second.split(":")
    assert first_parts[:3] == second_parts[:3]
    assert first_parts[0] == "agent-task"
    assert first_parts[1]
    assert first_parts[2].isdigit()
    assert len(first_parts[3]) == 32
    assert first_parts[3] != second_parts[3]
