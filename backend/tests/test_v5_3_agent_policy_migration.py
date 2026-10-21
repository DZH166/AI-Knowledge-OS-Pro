from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.db.session import create_database_engine
from app.models.agent_policy import AgentPolicyActivation, AgentPolicyCommand, AgentPolicyVersion
from app.modules.agent_policy.config import RetrievalPolicyConfig, canonical_policy_json, policy_fingerprint


ROOT = Path(__file__).resolve().parents[2]
V5_2_REVISION = "0009_v5_2_agent_control"
V5_3_REVISION = "0010_v5_3_agent_policy"
DEFAULT_POLICY_ID = "00000000-0000-0000-0000-000000000001"


def _migrate(database_url: str, revision: str, monkeypatch: pytest.MonkeyPatch, *, downgrade: bool = False) -> None:
    monkeypatch.setattr(settings, "database_url", database_url)
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    (command.downgrade if downgrade else command.upgrade)(config, revision)


def _policy(identifier: str, version: int, *, status: str) -> AgentPolicyVersion:
    config = RetrievalPolicyConfig()
    return AgentPolicyVersion(
        id=identifier,
        policy_key="default-research",
        version=version,
        label=f"Policy {version}",
        status=status,
        config_schema_version=1,
        config_json=canonical_policy_json(config),
        config_sha256=policy_fingerprint(config),
        base_policy_id=None,
        created_by="test",
        has_been_active=1 if status == "active" else 0,
    )


def test_policy_models_enforce_single_active_version_and_bounded_lifecycle(db_session) -> None:
    db_session.add(_policy("policy-active-1", 1, status="active"))
    db_session.commit()

    db_session.add(_policy("policy-active-2", 2, status="active"))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    invalid = _policy("policy-invalid", 3, status="invented")
    db_session.add(invalid)
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_v5_3_upgrade_downgrade_upgrade_preserves_v5_2_rows_and_seeds_default(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_path = tmp_path / "v5-3-policy.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    _migrate(database_url, V5_2_REVISION, monkeypatch)
    engine = create_database_engine(database_url)
    try:
        with engine.begin() as connection:
            space_id = connection.execute(
                text("INSERT INTO knowledge_spaces (name, description) VALUES ('V5.3', 'migration')")
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
                        'run-before-v53', :space_id, 'preserve run', 'force_quick', 'force_quick',
                        'completed', 'persist_artifact', 2, 0, '{}', :digest,
                        '{}', '{}', '{}', '{}', 'demo', 'trace-before-v53', 1
                    )
                    """
                ),
                {"space_id": space_id, "digest": "a" * 64},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO agent_evaluations (
                        id, request_id, request_payload_hash, label, mode, status, policy_fingerprint,
                        case_count, failure_case_count, category_counts_json, metrics_json,
                        hard_gates_json, failure_case_ids_json, provider_boundary, attempt
                    ) VALUES (
                        'evaluation-before-v53', 'request-before-v53', :payload_hash, 'preserve eval',
                        'deterministic_recording', 'queued', :fingerprint,
                        0, 0, '{}', '{}', '{}', '[]', 'zero external calls pending', 0
                    )
                    """
                ),
                {"payload_hash": "b" * 64, "fingerprint": "c" * 64},
            )

        _migrate(database_url, V5_3_REVISION, monkeypatch)
        inspector = inspect(engine)
        assert {
            "agent_policy_versions",
            "agent_policy_commands",
            "agent_policy_activations",
        }.issubset(inspector.get_table_names())
        with engine.connect() as connection:
            active = connection.execute(
                text(
                    "SELECT id, version, status, config_json, config_sha256 "
                    "FROM agent_policy_versions WHERE status='active'"
                )
            ).mappings().one()
            assert active == {
                "id": DEFAULT_POLICY_ID,
                "version": 1,
                "status": "active",
                "config_json": canonical_policy_json(RetrievalPolicyConfig()),
                "config_sha256": policy_fingerprint(RetrievalPolicyConfig()),
            }
            legacy_run = connection.execute(
                text(
                    "SELECT goal, decision_policy_id, decision_policy_snapshot_json "
                    "FROM agent_runs WHERE id='run-before-v53'"
                )
            ).mappings().one()
            assert legacy_run["goal"] == "preserve run"
            assert legacy_run["decision_policy_id"] is None
            assert legacy_run["decision_policy_snapshot_json"] is None

        _migrate(database_url, V5_2_REVISION, monkeypatch, downgrade=True)
        inspector = inspect(engine)
        assert "agent_policy_versions" not in inspector.get_table_names()
        assert "decision_policy_id" not in {item["name"] for item in inspector.get_columns("agent_runs")}
        with engine.connect() as connection:
            assert connection.execute(
                text("SELECT goal FROM agent_runs WHERE id='run-before-v53'")
            ).scalar_one() == "preserve run"
            assert connection.execute(
                text("SELECT label FROM agent_evaluations WHERE id='evaluation-before-v53'")
            ).scalar_one() == "preserve eval"

        _migrate(database_url, V5_3_REVISION, monkeypatch)
        with engine.connect() as connection:
            assert connection.execute(text("SELECT COUNT(*) FROM agent_policy_versions")).scalar_one() == 1
            assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == V5_3_REVISION
    finally:
        engine.dispose()


def test_v5_3_migration_columns_constraints_and_indexes_match_models(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_path = tmp_path / "v5-3-policy-parity.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    _migrate(database_url, V5_3_REVISION, monkeypatch)
    engine = create_database_engine(database_url)
    try:
        inspector = inspect(engine)
        for model in (AgentPolicyVersion, AgentPolicyCommand, AgentPolicyActivation):
            assert {item["name"] for item in inspector.get_columns(model.__tablename__)} == set(
                model.__table__.columns.keys()
            )
        run_columns = {item["name"] for item in inspector.get_columns("agent_runs")}
        assert {
            "decision_policy_id",
            "decision_policy_version",
            "decision_policy_fingerprint",
            "decision_policy_snapshot_json",
        }.issubset(run_columns)
        evaluation_columns = {item["name"] for item in inspector.get_columns("agent_evaluations")}
        assert {"policy_version_id", "policy_snapshot_json"}.issubset(evaluation_columns)

        version_constraints = {
            item["name"] for item in inspector.get_check_constraints("agent_policy_versions")
        }
        assert version_constraints == {
            "ck_agent_policy_versions_active_flag",
            "ck_agent_policy_versions_config_schema",
            "ck_agent_policy_versions_status",
            "ck_agent_policy_versions_version_positive",
        }
        version_indexes = {item["name"] for item in inspector.get_indexes("agent_policy_versions")}
        assert {
            "ix_agent_policy_versions_config_sha256",
            "ix_agent_policy_versions_created_at",
            "ix_agent_policy_versions_policy_key",
            "ix_agent_policy_versions_status",
            "uq_agent_policy_versions_single_active",
        }.issubset(version_indexes)
    finally:
        engine.dispose()
