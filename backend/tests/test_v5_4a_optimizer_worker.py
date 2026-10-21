from __future__ import annotations

from pathlib import Path

import pytest

from app.modules.agent_control.executor import EvaluationExecutionError
from app.modules.agent_policy_optimizer.executor import (
    FixedSubprocessTrialAdapter,
    TrialPolicySnapshot,
)
from app.modules.agent_policy.config import RetrievalPolicyConfig, canonical_policy_json, policy_fingerprint


def _snapshot(config: RetrievalPolicyConfig | None = None) -> TrialPolicySnapshot:
    config = config or RetrievalPolicyConfig()
    return TrialPolicySnapshot(
        trial_id="trial-1",
        config_sha256=policy_fingerprint(config),
        config_json=canonical_policy_json(config),
    )


def _fake_root(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "scripts").mkdir(parents=True)
    (root / "evaluation" / "v5").mkdir(parents=True)
    (root / "scripts" / "evaluate_agentic_rag.py").write_text("# fixed evaluator\n", encoding="utf-8")
    (root / "evaluation" / "v5" / "cases.jsonl").write_text("{}\n", encoding="utf-8")
    return root


def test_trial_snapshot_rejects_fingerprint_mismatch() -> None:
    with pytest.raises(ValueError):
        TrialPolicySnapshot(
            trial_id="trial-1",
            config_sha256="f" * 64,
            config_json=canonical_policy_json(RetrievalPolicyConfig()),
        )


def test_fixed_trial_adapter_requires_snapshot_and_binds_fingerprint(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_adapter_run(self, evaluation_id, policy_snapshot=None):
        captured["evaluation_id"] = evaluation_id
        captured["snapshot"] = policy_snapshot
        return {"fixed": True}

    monkeypatch.setattr(
        "app.modules.agent_control.executor.FixedSubprocessEvaluationAdapter.run",
        fake_adapter_run,
    )
    adapter = FixedSubprocessTrialAdapter()
    # without a snapshot the trial must be rejected outright
    with pytest.raises(EvaluationExecutionError) as missing:
        adapter.run("trial-1", None)
    assert missing.value.code == "OPTIMIZER_TRIAL_SNAPSHOT_MISSING"

    result = adapter.run("trial-1", _snapshot())
    assert result == {"fixed": True}
    assert captured["evaluation_id"] == "trial-1"
    assert captured["snapshot"].config_sha256 == policy_fingerprint(RetrievalPolicyConfig())


def test_rq_task_function_and_broker_topic_are_wired() -> None:
    import app.tasks.optimizer_tasks as optimizer_tasks
    from app.services.task_broker import RedisRQTaskBroker
    from app.modules.agent_policy_optimizer.service import TRIAL_TOPIC

    assert hasattr(optimizer_tasks, "run_optimization_trial")
    broker = RedisRQTaskBroker()
    envelope = _envelope_for(TRIAL_TOPIC)
    # Unsupported topics raise before touching Redis; the optimizer topic must be supported.
    try:
        broker.publish(envelope)
    except ValueError as exc:
        raise AssertionError("agent.optimize.trial must be mapped in RedisRQTaskBroker.publish") from exc
    except Exception:
        pass  # Redis unreachable in unit tests is acceptable; mapping is what we assert.


def _envelope_for(topic: str):
    from app.services.task_broker import TaskEnvelope

    return TaskEnvelope(
        task_id=f"wire-check-{topic.replace(chr(46), chr(45))}",
        topic=topic,
        payload={"trial_id": "trial-wire-check"},
        queue_name="default",
    )
