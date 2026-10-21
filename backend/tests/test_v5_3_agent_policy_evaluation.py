from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import subprocess

import pytest
from sqlalchemy.orm import sessionmaker

from app.core.errors import ServiceError
from app.db.session import Base, create_database_engine
from app.models.agent_policy import AgentPolicyVersion
from app.modules.agent_control.contracts import ExecuteEvaluation, StartEvaluation
from app.modules.agent_control.executor import (
    EvaluationPolicySnapshot,
    FixedSubprocessEvaluationAdapter,
)
from app.modules.agent_control.report import validate_evaluation_report
from app.modules.agent_control.service import SqlAgentControl
from app.modules.agent_policy.config import RetrievalPolicyConfig, canonical_policy_json, policy_fingerprint
from app.modules.agent_policy.contracts import (
    ActivatePolicy,
    CreatePolicy,
    GetActivePolicy,
    GetPolicy,
    PolicyDetail,
)
from app.modules.agent_policy.service import SqlAgentPolicy
from tests.test_v5_2_agent_control_sql import evaluation_report


DEFAULT_POLICY_ID = "00000000-0000-0000-0000-000000000001"


@pytest.fixture()
def policy_evaluation_factory(tmp_path: Path):
    engine = create_database_engine(f"sqlite:///{(tmp_path / 'policy-evaluation.db').as_posix()}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    config = RetrievalPolicyConfig()
    with factory.begin() as session:
        session.add(
            AgentPolicyVersion(
                id=DEFAULT_POLICY_ID,
                policy_key="default-research",
                version=1,
                label="Balanced evidence retrieval",
                status="active",
                config_schema_version=1,
                config_json=canonical_policy_json(config),
                config_sha256=policy_fingerprint(config),
                base_policy_id=None,
                created_by="system:test",
                has_been_active=1,
            )
        )
    try:
        yield factory
    finally:
        engine.dispose()


def _resolver(policy: SqlAgentPolicy):
    def resolve(policy_id: str | None) -> PolicyDetail:
        result = policy.inspect(GetPolicy(policy_id)) if policy_id else policy.inspect(GetActivePolicy())
        assert isinstance(result, PolicyDetail)
        return result

    return resolve


class RecordingPolicyExecutor:
    def __init__(self, *, reported_fingerprint: str | None = None) -> None:
        self.reported_fingerprint = reported_fingerprint
        self.snapshots: list[EvaluationPolicySnapshot | None] = []

    def run(
        self,
        _evaluation_id: str,
        policy_snapshot: EvaluationPolicySnapshot | None = None,
    ):
        self.snapshots.append(policy_snapshot)
        report = evaluation_report()
        if policy_snapshot is not None or self.reported_fingerprint is not None:
            report["provenance"]["retrieval_policy_sha256"] = (
                self.reported_fingerprint
                if self.reported_fingerprint is not None
                else policy_snapshot.config_sha256
            )
        return report


def test_candidate_evaluation_binds_exact_snapshot_and_authorizes_activation(
    policy_evaluation_factory,
) -> None:
    policy = SqlAgentPolicy(policy_evaluation_factory)
    candidate = policy.submit(
        CreatePolicy(
            request_id="create-evaluated-policy",
            label="Evaluated policy",
            base_policy_id=DEFAULT_POLICY_ID,
            config=replace(RetrievalPolicyConfig(), comparative_top_k=18),
        )
    )
    candidate_detail = policy.inspect(GetPolicy(candidate.policy_id))
    control = SqlAgentControl(
        policy_evaluation_factory,
        policy_resolver=_resolver(policy),
    )
    receipt = control.submit(
        StartEvaluation(
            request_id="evaluate-candidate-policy",
            label="Candidate fixed evaluation",
            policy_id=candidate.policy_id,
        )
    )
    executor = RecordingPolicyExecutor()

    result = control.execute(
        ExecuteEvaluation(evaluation_id=receipt.evaluation_id, worker_id="policy-worker"),
        executor,
    )

    assert result.summary.status.value == "passed"
    assert result.summary.policy_version_id == candidate.policy_id
    assert result.summary.policy_fingerprint == candidate_detail.config_sha256
    assert executor.snapshots == [
        EvaluationPolicySnapshot(
            policy_id=candidate.policy_id,
            policy_version=2,
            config_sha256=candidate_detail.config_sha256,
            config_json=canonical_policy_json(candidate_detail.config),
        )
    ]
    activated = policy.submit(
        ActivatePolicy(
            request_id="activate-evaluated-policy",
            policy_id=candidate.policy_id,
            expected_active_policy_id=DEFAULT_POLICY_ID,
            evaluation_id=receipt.evaluation_id,
        )
    )
    assert activated.policy_id == candidate.policy_id


def test_candidate_evaluation_rejects_reported_policy_mismatch(policy_evaluation_factory) -> None:
    policy = SqlAgentPolicy(policy_evaluation_factory)
    candidate = policy.submit(
        CreatePolicy(
            request_id="create-mismatch-policy",
            label="Mismatch policy",
            base_policy_id=DEFAULT_POLICY_ID,
            config=replace(RetrievalPolicyConfig(), factual_top_k=9),
        )
    )
    control = SqlAgentControl(policy_evaluation_factory, policy_resolver=_resolver(policy))
    receipt = control.submit(
        StartEvaluation(
            request_id="evaluate-mismatch-policy",
            label="Mismatch fixed evaluation",
            policy_id=candidate.policy_id,
        )
    )

    result = control.execute(
        ExecuteEvaluation(evaluation_id=receipt.evaluation_id, worker_id="mismatch-worker"),
        RecordingPolicyExecutor(reported_fingerprint="f" * 64),
    )

    assert result.summary.status.value == "failed"
    assert result.error_code == "EVALUATION_POLICY_MISMATCH"
    with pytest.raises(ServiceError) as activation_error:
        policy.submit(
            ActivatePolicy(
                request_id="activate-mismatch-policy",
                policy_id=candidate.policy_id,
                expected_active_policy_id=DEFAULT_POLICY_ID,
                evaluation_id=receipt.evaluation_id,
            )
        )
    assert activation_error.value.code == "POLICY_EVALUATION_REQUIRED"


def test_fixed_executor_passes_only_internal_bounded_policy_file_and_cleans_it(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    (root / "scripts").mkdir(parents=True)
    (root / "evaluation" / "v5").mkdir(parents=True)
    (root / "scripts" / "evaluate_agentic_rag.py").write_text("# fixed\n", encoding="utf-8")
    (root / "evaluation" / "v5" / "cases.jsonl").write_text("{}\n", encoding="utf-8")
    temporary_root = tmp_path / "work"
    config = replace(RetrievalPolicyConfig(), temporal_top_k=16)
    snapshot = EvaluationPolicySnapshot(
        policy_id="candidate-policy",
        policy_version=3,
        config_sha256=policy_fingerprint(config),
        config_json=canonical_policy_json(config),
    )
    captured: dict[str, object] = {}

    def fake_run(command, **_options):
        policy_path = Path(command[command.index("--policy-config") + 1])
        captured["policy_path"] = policy_path
        captured["policy_text"] = policy_path.read_text(encoding="utf-8")
        report_path = Path(command[command.index("--output") + 1])
        report = evaluation_report()
        report["provenance"]["retrieval_policy_sha256"] = snapshot.config_sha256
        from hashlib import sha256
        report["provenance"]["evaluator_sha256"] = sha256(b"# fixed\n").hexdigest()
        report["dataset"]["sha256"] = sha256(b"{}\n").hexdigest()
        import json

        report_path.write_text(json.dumps(report), encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    payload = FixedSubprocessEvaluationAdapter(
        root=root,
        temporary_root=temporary_root,
        run_process=fake_run,
    ).run("evaluation-policy", snapshot)

    assert validate_evaluation_report(payload).policy_fingerprint == snapshot.config_sha256
    assert '"policy_id":"candidate-policy"' in str(captured["policy_text"])
    assert not Path(captured["policy_path"]).exists()
    assert list(temporary_root.iterdir()) == []


def test_real_fixed_evaluator_executes_a_candidate_policy_with_zero_provider_calls() -> None:
    config = replace(RetrievalPolicyConfig(), factual_top_k=9, comparative_top_k=16)
    snapshot = EvaluationPolicySnapshot(
        policy_id="real-candidate-policy",
        policy_version=2,
        config_sha256=policy_fingerprint(config),
        config_json=canonical_policy_json(config),
    )
    report = FixedSubprocessEvaluationAdapter(timeout_seconds=180).run(
        "real-candidate-policy",
        snapshot,
    )
    validated = validate_evaluation_report(report)
    assert validated.status == "passed"
    assert validated.case_count == 60
    assert validated.external_provider_calls == 0
    assert validated.policy_fingerprint == snapshot.config_sha256
