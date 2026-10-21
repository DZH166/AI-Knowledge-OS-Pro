from __future__ import annotations

import argparse
from pathlib import Path
import signal
import sys
from threading import Event
from typing import Callable, Protocol

from sqlalchemy.orm import Session


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.config import settings  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.modules.evidence_agent.wiring import get_agent_runner  # noqa: E402
from app.services.outbox_dispatcher import OutboxDispatcher  # noqa: E402
from app.services.task_broker import TaskEnvelope  # noqa: E402


class AgentRunnerPort(Protocol):
    def advance_one(self, run_id: str, *, expected_version: int, execution_epoch: int) -> object: ...


class InlineAgentTaskBroker:
    """Explicit demo-only broker used to exercise the durable Agent loop without Redis."""

    def __init__(self, runner_factory: Callable[[], AgentRunnerPort] = get_agent_runner) -> None:
        self._runner_factory = runner_factory

    def publish(self, envelope: TaskEnvelope) -> str:
        if envelope.topic != "agent.advance":
            raise ValueError("The demo worker only accepts agent.advance tasks.")
        self._runner_factory().advance_one(
            str(envelope.payload["run_id"]),
            expected_version=int(envelope.payload["version"]),
            execution_epoch=int(envelope.payload["execution_epoch"]),
        )
        return envelope.task_id


def build_demo_dispatcher(
    *,
    session_factory: Callable[[], Session] = SessionLocal,
    runner_factory: Callable[[], AgentRunnerPort] = get_agent_runner,
    worker_id: str = "demo-inline-agent-worker",
) -> OutboxDispatcher:
    return OutboxDispatcher(
        session_factory,
        InlineAgentTaskBroker(runner_factory),
        worker_id=worker_id,
        lease_seconds=settings.outbox_lease_seconds,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the explicit DEMO_MODE durable Agent worker without Redis/RQ."
    )
    parser.add_argument("--poll-seconds", type=float, default=0.05)
    args = parser.parse_args()
    if not settings.demo_mode:
        raise SystemExit("run_demo_agent_worker.py requires DEMO_MODE=true")

    stop = Event()

    def request_stop(_signum: int, _frame: object) -> None:
        stop.set()

    signal.signal(signal.SIGINT, request_stop)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, request_stop)

    dispatcher = build_demo_dispatcher()
    print("demo_agent_worker=ready mode=inline_demo", flush=True)
    while not stop.is_set():
        result = dispatcher.dispatch_once(limit=settings.outbox_batch_size)
        if result.claimed == 0:
            stop.wait(max(0.01, args.poll_seconds))


if __name__ == "__main__":
    main()
