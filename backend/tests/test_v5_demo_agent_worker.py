from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base
from app.models.outbox import OutboxMessage
from app.services.task_broker import TaskEnvelope
from scripts.run_demo_agent_worker import InlineAgentTaskBroker, build_demo_dispatcher


class RecordingRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int, int]] = []

    def advance_one(self, run_id: str, *, expected_version: int, execution_epoch: int) -> SimpleNamespace:
        self.calls.append((run_id, expected_version, execution_epoch))
        return SimpleNamespace(applied=True)


class FailingRunner:
    def __init__(self) -> None:
        self.calls = 0

    def advance_one(self, run_id: str, *, expected_version: int, execution_epoch: int) -> SimpleNamespace:
        self.calls += 1
        raise RuntimeError("simulated durable slice failure")


def test_inline_demo_broker_advances_exactly_one_fenced_agent_slice() -> None:
    runner = RecordingRunner()
    broker = InlineAgentTaskBroker(lambda: runner)
    envelope = TaskEnvelope(
        task_id="agent:run-live:4:2",
        topic="agent.advance",
        payload={"run_id": "run-live", "version": 4, "execution_epoch": 2},
    )

    assert broker.publish(envelope) == envelope.task_id
    assert runner.calls == [("run-live", 4, 2)]


def test_inline_demo_broker_rejects_non_agent_topics() -> None:
    broker = InlineAgentTaskBroker(RecordingRunner)

    with pytest.raises(ValueError, match="demo worker only accepts agent.advance"):
        broker.publish(
            TaskEnvelope(
                task_id="unexpected",
                topic="evidence_index.reconcile",
                payload={},
            )
        )


def test_demo_dispatcher_defers_a_failed_slice_instead_of_busy_retrying() -> None:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    runner = FailingRunner()
    try:
        with factory.begin() as session:
            session.add(
                OutboxMessage(
                    id="demo-outbox-failure",
                    topic="agent.advance",
                    aggregate_type="agent_run",
                    aggregate_id="run-demo",
                    dedupe_key="agent.advance:run-demo:2:0",
                    payload_json='{"execution_epoch":0,"run_id":"run-demo","version":2}',
                    status="pending",
                )
            )

        dispatcher = build_demo_dispatcher(
            session_factory=factory,
            runner_factory=lambda: runner,
            worker_id="demo-test",
        )
        first = dispatcher.dispatch_once()
        immediate_retry = dispatcher.dispatch_once()

        assert first.failed == 1
        assert immediate_retry.claimed == 0
        assert runner.calls == 1
        with factory() as session:
            message = session.get(OutboxMessage, "demo-outbox-failure")
            assert message is not None
            assert message.status == "pending"
            assert message.attempt == 1
    finally:
        engine.dispose()
