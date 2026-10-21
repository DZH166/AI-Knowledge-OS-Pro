from __future__ import annotations

import os
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base
from app.models.agent_evaluation import AgentEvaluation
from app.models.outbox import OutboxMessage
from app.modules.agent_control.executor import (
    EvaluationExecutionError,
    FixedSubprocessEvaluationAdapter,
)
from app.modules.agent_control.report import validate_evaluation_report
from app.services.outbox_dispatcher import OutboxDispatcher
from app.services.task_broker import RedisRQTaskBroker, TaskEnvelope


CHILD_OPENAI_SECRET = "sk-" + "should-not-reach-child"
CHILD_GITHUB_SECRET = "ghp_" + "should_not_reach_child_123456"
CHILD_AWS_SECRET = "aws-" + "should-not-reach-child"
CHILD_GOOGLE_CREDENTIALS = "C:\\Users\\private\\google-credentials.json"
DEAD_LETTER_SECRET = "api_key=" + "sk-" + "dead-letter-secret"


def _memory_factory():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine, expire_on_commit=False)


def _fake_root(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "scripts").mkdir(parents=True)
    (root / "evaluation" / "v5").mkdir(parents=True)
    (root / "scripts" / "evaluate_agentic_rag.py").write_text("# fixed evaluator\n", encoding="utf-8")
    (root / "evaluation" / "v5" / "cases.jsonl").write_text("{}\n", encoding="utf-8")
    return root


def test_fixed_executor_uses_only_fixed_arguments_scrubs_secrets_and_cleans_temp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _fake_root(tmp_path)
    temporary_root = tmp_path / "evaluation-work"
    captured: dict[str, object] = {}
    monkeypatch.setenv("OPENAI_API_KEY", CHILD_OPENAI_SECRET)
    monkeypatch.setenv("GITHUB_TOKEN", CHILD_GITHUB_SECRET)
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", CHILD_AWS_SECRET)
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", CHILD_GOOGLE_CREDENTIALS)
    monkeypatch.setenv("PRIVATE_DATABASE_PASSWORD", "database-should-not-reach-child")

    def fake_run(command, **options):
        captured.update(command=command, **options)
        report_path = Path(command[command.index("--output") + 1])
        database_path = Path(command[command.index("--database-path") + 1])
        report_path.write_text('{"fixed":true}', encoding="utf-8")
        database_path.write_text("isolated", encoding="utf-8")
        captured["workspace"] = report_path.parent
        return subprocess.CompletedProcess(command, 0, stdout="ignored", stderr="")

    payload = FixedSubprocessEvaluationAdapter(
        root=root,
        timeout_seconds=30,
        temporary_root=temporary_root,
        run_process=fake_run,
    ).run("evaluation:unsafe/id")

    assert payload == {"fixed": True}
    command = captured["command"]
    assert isinstance(command, list)
    assert command[1] == str(root / "scripts" / "evaluate_agentic_rag.py")
    assert command[command.index("--dataset") + 1] == str(root / "evaluation" / "v5" / "cases.jsonl")
    assert command[command.index("--mode") + 1] == "demo"
    environment = captured["env"]
    assert isinstance(environment, dict)
    assert environment["OPENAI_API_KEY"] == ""
    assert "GITHUB_TOKEN" not in environment
    assert "AWS_SECRET_ACCESS_KEY" not in environment
    assert "GOOGLE_APPLICATION_CREDENTIALS" not in environment
    assert "PRIVATE_DATABASE_PASSWORD" not in environment
    assert environment.get("PATH") == os.environ.get("PATH")
    assert environment["DEMO_MODE"] == "true"
    assert not Path(captured["workspace"]).exists()
    assert list(temporary_root.iterdir()) == []


@pytest.mark.parametrize(
    ("behavior", "expected_code"),
    [
        ("timeout", "EVALUATION_TIMEOUT"),
        ("nonzero", "EVALUATION_EXECUTOR_FAILED"),
        ("missing", "EVALUATION_REPORT_INVALID"),
        ("invalid", "EVALUATION_REPORT_INVALID"),
    ],
)
def test_fixed_executor_converts_failures_to_bounded_codes_and_cleans(
    tmp_path: Path,
    behavior: str,
    expected_code: str,
) -> None:
    root = _fake_root(tmp_path)
    temporary_root = tmp_path / f"work-{behavior}"
    captured_workspace: list[Path] = []

    def fake_run(command, **_options):
        report_path = Path(command[command.index("--output") + 1])
        captured_workspace.append(report_path.parent)
        if behavior == "timeout":
            raise subprocess.TimeoutExpired(command, 1)
        if behavior == "nonzero":
            return subprocess.CompletedProcess(command, 7, stdout="secret stdout", stderr="secret stderr")
        if behavior == "invalid":
            report_path.write_text("not-json", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    adapter = FixedSubprocessEvaluationAdapter(
        root=root,
        timeout_seconds=1,
        temporary_root=temporary_root,
        run_process=fake_run,
    )
    with pytest.raises(EvaluationExecutionError) as exc_info:
        adapter.run("evaluation-failure")
    assert exc_info.value.code == expected_code
    assert "secret stdout" not in str(exc_info.value)
    assert "secret stderr" not in str(exc_info.value)
    assert captured_workspace and not captured_workspace[0].exists()
    assert list(temporary_root.iterdir()) == []


def test_fixed_executor_rejects_a_report_symlink_before_reading(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _fake_root(tmp_path)

    def fake_run(command, **_options):
        report_path = Path(command[command.index("--output") + 1])
        report_path.write_text('{"fixed":true}', encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    original_is_symlink = Path.is_symlink
    monkeypatch.setattr(
        Path,
        "is_symlink",
        lambda path: path.name == "report.json" or original_is_symlink(path),
    )
    with pytest.raises(EvaluationExecutionError) as exc_info:
        FixedSubprocessEvaluationAdapter(root=root, run_process=fake_run).run("symlink-report")
    assert exc_info.value.code == "EVALUATION_REPORT_INVALID"


def test_real_fixed_executor_produces_a_valid_zero_provider_60_case_report() -> None:
    report = FixedSubprocessEvaluationAdapter(timeout_seconds=180).run("real-fixed-regression")
    validated = validate_evaluation_report(report)
    assert validated.case_count == 60
    assert validated.external_provider_calls == 0
    assert validated.status == "passed"


def test_task_broker_maps_agent_evaluate_to_fixed_worker_without_model_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class CapturingQueue:
        def __init__(self, name: str, *, connection: object) -> None:
            captured.update(queue_name=name, connection=connection)

        def enqueue(self, function: str, *arguments: object, **options: object):
            captured.update(function=function, arguments=arguments, options=options)
            return SimpleNamespace(id="evaluation-eval-1")

    monkeypatch.setattr("redis.Redis.from_url", lambda _url: object())
    monkeypatch.setattr("rq.Queue", CapturingQueue)
    published = RedisRQTaskBroker().publish(
        TaskEnvelope(
            task_id="evaluation-eval-1",
            topic="agent.evaluate",
            payload={"evaluation_id": "eval-1"},
        )
    )
    assert published == "evaluation-eval-1"
    assert captured["function"] == "app.tasks.evaluation_tasks.run_agent_evaluation"
    assert captured["arguments"] == ("eval-1",)
    options = captured["options"]
    assert isinstance(options, dict)
    assert "retry" not in options
    assert options["job_timeout"] > 0


def test_evaluation_outbox_dead_letter_marks_snapshot_failed_and_redacts_broker_error(caplog) -> None:
    engine, factory = _memory_factory()

    class FailingBroker:
        def publish(self, _envelope):
            raise RuntimeError(DEAD_LETTER_SECRET)

    try:
        with factory.begin() as session:
            session.add(
                AgentEvaluation(
                    id="evaluation-dead",
                    request_id="request-dead",
                    request_payload_hash="a" * 64,
                    label="Dead letter",
                    mode="deterministic_recording",
                    status="queued",
                    policy_fingerprint="b" * 64,
                    case_count=0,
                    failure_case_count=0,
                    attempt=0,
                )
            )
            session.add(
                OutboxMessage(
                    id="outbox-evaluation-dead",
                    topic="agent.evaluate",
                    aggregate_type="agent_evaluation",
                    aggregate_id="evaluation-dead",
                    dedupe_key="agent.evaluate:evaluation-dead",
                    payload_json='{"evaluation_id":"evaluation-dead"}',
                    status="pending",
                )
            )
        result = OutboxDispatcher(
            factory,
            FailingBroker(),
            worker_id="failing-dispatcher",
            max_attempts=1,
        ).dispatch_once()
        assert result.dead_lettered == 1
        with factory() as session:
            evaluation = session.get(AgentEvaluation, "evaluation-dead")
            message = session.get(OutboxMessage, "outbox-evaluation-dead")
            assert evaluation.status == "failed"
            assert evaluation.error_code == "EVALUATION_DISPATCH_DEAD_LETTER"
            assert evaluation.error_message == "[redacted]"
            assert evaluation.finished_at is not None
            assert message.status == "dead_letter"
            assert message.last_error == "[redacted]"
            assert DEAD_LETTER_SECRET not in message.last_error
        assert DEAD_LETTER_SECRET not in caplog.text
    finally:
        engine.dispose()


def test_evaluation_outbox_uses_stable_rq_safe_task_id() -> None:
    message = OutboxMessage(
        id="outbox-eval",
        topic="agent.evaluate",
        aggregate_type="agent_evaluation",
        aggregate_id="eval-uuid",
        dedupe_key="agent.evaluate:eval-uuid",
        payload_json='{"evaluation_id":"eval-uuid"}',
        status="pending",
    )
    envelope = OutboxDispatcher._envelope(message)
    assert envelope.task_id == "evaluation-eval-uuid"
    assert envelope.topic == "agent.evaluate"


def test_worker_task_returns_only_bounded_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.tasks import evaluation_tasks

    captured: dict[str, object] = {}

    class FakeControl:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def execute(self, command, executor):
            captured.update(command=command, executor=executor)
            return SimpleNamespace(
                summary=SimpleNamespace(
                    status=SimpleNamespace(value="passed"),
                    case_count=60,
                    case_pass_rate=1.0,
                    external_provider_calls=0,
                    failure_case_count=0,
                ),
                error_code=None,
            )

    monkeypatch.setattr(evaluation_tasks, "SqlAgentControl", FakeControl)
    monkeypatch.setattr(evaluation_tasks, "FixedSubprocessEvaluationAdapter", lambda **_kwargs: object())
    result = evaluation_tasks.run_agent_evaluation("evaluation-task")
    assert result == {
        "evaluation_id": "evaluation-task",
        "status": "passed",
        "case_count": 60,
        "case_pass_rate": 1.0,
        "external_provider_calls": 0,
        "failure_case_count": 0,
        "error_code": None,
    }
    assert captured["command"].evaluation_id == "evaluation-task"


def test_evaluation_lease_outlives_executor_and_rq_timeout_buffer() -> None:
    from app.core.config import settings

    assert settings.evaluation_lease_seconds > settings.evaluation_timeout_seconds + 60
