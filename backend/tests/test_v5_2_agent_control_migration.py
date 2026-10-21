from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.db.session import create_database_engine
from app.models.agent_evaluation import AgentEvaluation


ROOT = Path(__file__).resolve().parents[2]
V5_1_REVISION = "0008_v5_agent_runtime"
V5_2_REVISION = "0009_v5_2_agent_control"


def _migrate(database_url: str, revision: str, monkeypatch: pytest.MonkeyPatch, *, downgrade: bool = False) -> None:
    monkeypatch.setattr(settings, "database_url", database_url)
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    (command.downgrade if downgrade else command.upgrade)(config, revision)


def test_agent_evaluation_model_enforces_status_and_numeric_constraints(db_session) -> None:
    db_session.add(
        AgentEvaluation(
            id="evaluation-invalid",
            request_id="request-invalid",
            request_payload_hash="d" * 64,
            label="invalid",
            mode="deterministic_recording",
            status="pretend_success",
            policy_fingerprint="a" * 64,
            case_count=0,
            failure_case_count=0,
            attempt=0,
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    db_session.add(
        AgentEvaluation(
            id="evaluation-invalid-rate",
            request_id="request-invalid-rate",
            request_payload_hash="d" * 64,
            label="invalid rate",
            mode="deterministic_recording",
            status="queued",
            policy_fingerprint="a" * 64,
            case_count=0,
            case_pass_rate_millis=1001,
            failure_case_count=0,
            attempt=0,
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_v5_2_upgrade_downgrade_upgrade_preserves_v5_1_agent_data(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_path = tmp_path / "v5-2-agent-control.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    _migrate(database_url, V5_1_REVISION, monkeypatch)
    engine = create_database_engine(database_url)
    try:
        assert "agent_evaluations" not in inspect(engine).get_table_names()
        with engine.begin() as connection:
            space_id = connection.execute(
                text("INSERT INTO knowledge_spaces (name, description) VALUES ('V5.2', 'migration')")
            ).lastrowid
            connection.execute(
                text(
                    """
                    INSERT INTO agent_runs (
                        id, space_id, goal, requested_mode, effective_mode, status, phase,
                        version, execution_epoch, scope_snapshot_json, scope_digest,
                        deliverable_json, policy_snapshot_json, budget_limits_json,
                        budget_usage_json, provider_mode, trace_id, active_elapsed_ms
                    ) VALUES (
                        'run-before-v52', :space_id, 'preserve me', 'force_quick', 'force_quick',
                        'completed', 'persist_artifact', 3, 0, '{}', :digest,
                        '{}', '{}', '{}', '{}', 'demo', 'trace-before-v52', 10
                    )
                    """
                ),
                {"space_id": space_id, "digest": "b" * 64},
            )

        _migrate(database_url, V5_2_REVISION, monkeypatch)
        assert "agent_evaluations" in inspect(engine).get_table_names()
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO agent_evaluations (
                        id, request_id, request_payload_hash, label, mode, status, policy_fingerprint,
                        case_count, failure_case_count, category_counts_json, metrics_json,
                        hard_gates_json, failure_case_ids_json, provider_boundary, attempt
                    ) VALUES (
                        'evaluation-v52', 'request-v52', :payload_hash, 'migration snapshot',
                        'deterministic_recording', 'queued', :fingerprint,
                        0, 0, '{}', '{}', '{}', '[]', 'zero external calls pending', 0
                    )
                    """
                ),
                {"fingerprint": "c" * 64, "payload_hash": "d" * 64},
            )

        _migrate(database_url, V5_1_REVISION, monkeypatch, downgrade=True)
        assert "agent_evaluations" not in inspect(engine).get_table_names()
        with engine.connect() as connection:
            assert connection.execute(
                text("SELECT goal FROM agent_runs WHERE id='run-before-v52'")
            ).scalar_one() == "preserve me"

        _migrate(database_url, V5_2_REVISION, monkeypatch)
        assert "agent_evaluations" in inspect(engine).get_table_names()
        with engine.connect() as connection:
            assert connection.execute(text("SELECT COUNT(*) FROM agent_evaluations")).scalar_one() == 0
            assert connection.execute(text("SELECT COUNT(*) FROM agent_runs")).scalar_one() == 1
            assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == V5_2_REVISION
    finally:
        engine.dispose()


def test_v5_2_migration_columns_constraints_and_indexes_match_the_orm_model(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_path = tmp_path / "v5-2-schema-parity.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    _migrate(database_url, V5_2_REVISION, monkeypatch)
    engine = create_database_engine(database_url)
    try:
        inspector = inspect(engine)
        migrated_columns = {item["name"] for item in inspector.get_columns("agent_evaluations")}
        model_columns = set(AgentEvaluation.__table__.columns.keys()) - {
            "policy_version_id",
            "policy_snapshot_json",
        }
        assert migrated_columns == model_columns

        constraint_names = {
            item["name"] for item in inspector.get_check_constraints("agent_evaluations")
        }
        assert constraint_names == {
            "ck_agent_evaluations_attempt_non_negative",
            "ck_agent_evaluations_case_count_non_negative",
            "ck_agent_evaluations_pass_rate_millis",
            "ck_agent_evaluations_provider_calls_non_negative",
            "ck_agent_evaluations_status",
        }
        index_names = {item["name"] for item in inspector.get_indexes("agent_evaluations")}
        assert index_names == {
            "ix_agent_evaluations_created_at",
            "ix_agent_evaluations_dataset_sha256",
            "ix_agent_evaluations_lease_expires_at",
            "ix_agent_evaluations_policy_fingerprint",
            "ix_agent_evaluations_request_id",
            "ix_agent_evaluations_status",
        }
        unique_names = {
            item["name"] for item in inspector.get_unique_constraints("agent_evaluations")
        }
        assert unique_names == {"uq_agent_evaluations_request_id"}
    finally:
        engine.dispose()
