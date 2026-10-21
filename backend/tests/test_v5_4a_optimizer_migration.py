from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import inspect, text

from app.core.config import settings
from app.db.session import create_database_engine
from app.models.optimizer import OptimizationStudy, OptimizationTrial
from app.modules.agent_policy.config import RetrievalPolicyConfig, canonical_policy_json, policy_fingerprint


ROOT = Path(__file__).resolve().parents[2]
V5_3_REVISION = "0010_v5_3_agent_policy"
V5_4_REVISION = "0011_v5_4_retrieval_optimizer"
DEFAULT_POLICY_ID = "00000000-0000-0000-0000-000000000001"


def _migrate(database_url: str, revision: str, monkeypatch: pytest.MonkeyPatch, *, downgrade: bool = False) -> None:
    monkeypatch.setattr(settings, "database_url", database_url)
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    (command.downgrade if downgrade else command.upgrade)(config, revision)


def test_single_migration_head() -> None:
    from alembic.config import Config as AlembicConfig
    from alembic.script import ScriptDirectory

    script = ScriptDirectory.from_config(AlembicConfig(str(ROOT / "alembic.ini")))
    assert script.get_heads() == ["0015_v5_7_integration"]


def test_v5_4_upgrade_downgrade_upgrade_preserves_v5_3_rows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_path = tmp_path / "v5-4-optimizer.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    _migrate(database_url, V5_3_REVISION, monkeypatch)
    engine = create_database_engine(database_url)
    try:
        with engine.begin() as session:
            session.execute(
                text(
                    """
                    INSERT INTO agent_evaluations (
                        id, request_id, request_payload_hash, label, mode, status,
                        policy_fingerprint, case_count, failure_case_count,
                        category_counts_json, metrics_json, hard_gates_json,
                        failure_case_ids_json, provider_boundary, attempt
                    ) VALUES (
                        'eval-v53', 'req-v53', 'h', 'V5.3 evaluation', 'deterministic_recording', 'passed',
                        'f', 60, 0, '{}', '{}', '{}', '[]',
                        'not a real-model quality benchmark', 1
                    )
                    """
                )
            )
    finally:
        engine.dispose()

    _migrate(database_url, V5_4_REVISION, monkeypatch)
    engine = create_database_engine(database_url)
    try:
        inspector = inspect(engine)
        study_columns = {column["name"] for column in inspector.get_columns("optimization_studies")}
        trial_columns = {column["name"] for column in inspector.get_columns("optimization_trials")}
        assert {
            "id", "request_id", "request_payload_hash", "label", "objective", "status",
            "base_policy_id", "search_space_json", "weights_json", "budget_json",
            "budget_usage_json", "seed", "algorithm_version", "base_policy_fingerprint",
            "lease_owner", "lease_expires_at", "created_at", "started_at", "finished_at",
            "cancelled_at",
        } <= study_columns
        assert {
            "id", "study_id", "ordinal", "policy_id", "evaluation_id", "status",
            "config_sha256", "config_json", "metrics_json", "normalized_metrics_json",
            "score_millis", "dominated", "recommendation_rank", "failure_code",
            "created_at", "started_at", "finished_at",
        } <= trial_columns

        with engine.begin() as session:
            session.execute(
                text(
                    """
                    INSERT INTO optimization_studies (
                        id, request_id, request_payload_hash, label, objective, status,
                        base_policy_id, search_space_json, weights_json, budget_json,
                        budget_usage_json, seed, algorithm_version, base_policy_fingerprint
                    ) VALUES (
                        'study-1', 'req-1', 'h', 'Study', 'balanced', 'pending',
                        :policy_id, '{}', '{}', '{}', '{}', 1, 'v5_4a_1', 'f'
                    )
                    """
                ),
                {"policy_id": DEFAULT_POLICY_ID},
            )
            session.execute(
                text(
                    """
                    INSERT INTO optimization_trials (
                        id, study_id, ordinal, status, config_sha256, config_json,
                        is_baseline, dominated, attempt
                    ) VALUES (
                        'trial-1', 'study-1', 1, 'pending', 'f', '{}', 1, 0, 0
                    )
                    """
                )
            )
    finally:
        engine.dispose()

    # Downgrade keeps optimizer tables removable and V5.3 rows intact.
    _migrate(database_url, V5_3_REVISION, monkeypatch, downgrade=True)
    engine = create_database_engine(database_url)
    try:
        with engine.begin() as session:
            v53 = session.execute(
                text("SELECT id FROM agent_evaluations WHERE id = 'eval-v53'")
            ).scalar()
            assert v53 == "eval-v53"
            remaining = session.execute(text("SELECT COUNT(*) FROM agent_policy_versions")).scalar()
            assert remaining >= 1
    finally:
        engine.dispose()

    _migrate(database_url, V5_4_REVISION, monkeypatch)


def test_database_constraints_block_invalid_states(db_session) -> None:
    from sqlalchemy.exc import IntegrityError

    config = RetrievalPolicyConfig()
    db_session.add(
        OptimizationStudy(
            id="study-1",
            request_id="req-1",
            request_payload_hash="h",
            label="Study",
            objective="balanced",
            status="pending",
            base_policy_id=DEFAULT_POLICY_ID,
            search_space_json="{}",
            weights_json="{}",
            budget_json="{}",
            budget_usage_json="{}",
            seed=1,
            algorithm_version="v5_4a_1",
            base_policy_fingerprint=policy_fingerprint(config),
        )
    )
    db_session.commit()

    db_session.add(
        OptimizationTrial(
            id="trial-bad-status",
            study_id="study-1",
            ordinal=1,
            status="invented",
            config_sha256=policy_fingerprint(config),
            config_json=canonical_policy_json(config),
            is_baseline=0,
            dominated=0,
            attempt=0,
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    db_session.add(
        OptimizationTrial(
            id="trial-bad-score",
            study_id="study-1",
            ordinal=2,
            status="completed",
            config_sha256=policy_fingerprint(config),
            config_json=canonical_policy_json(config),
            is_baseline=0,
            dominated=0,
            attempt=0,
            score_millis=1500,
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    valid = OptimizationTrial(
        id="trial-valid-1",
        study_id="study-1",
        ordinal=1,
        status="pending",
        config_sha256=policy_fingerprint(config),
        config_json=canonical_policy_json(config),
        is_baseline=1,
        dominated=0,
        attempt=0,
    )
    db_session.add(valid)
    db_session.commit()

    duplicate = OptimizationTrial(
        id="trial-duplicate-ordinal",
        study_id="study-1",
        ordinal=1,
        status="pending",
        config_sha256=policy_fingerprint(config),
        config_json=canonical_policy_json(config),
        is_baseline=0,
        dominated=0,
        attempt=0,
    )
    db_session.add(duplicate)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
