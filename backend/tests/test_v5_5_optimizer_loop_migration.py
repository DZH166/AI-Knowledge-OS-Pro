from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import inspect, text

from app.core.config import settings
from app.db.session import create_database_engine


ROOT = Path(__file__).resolve().parents[2]
V5_4_REVISION = "0011_v5_4_retrieval_optimizer"
V5_5_REVISION = "0012_v5_5_optimizer_closed_loop"
HEAD_REVISION = "0017_reviewed_feedback"


def _migrate(database_url: str, revision: str, monkeypatch: pytest.MonkeyPatch, *, downgrade: bool = False) -> None:
    monkeypatch.setattr(settings, "database_url", database_url)
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    (command.downgrade if downgrade else command.upgrade)(config, revision)


def test_single_migration_head_v5_5() -> None:
    from alembic.config import Config as AlembicConfig
    from alembic.script import ScriptDirectory

    script = ScriptDirectory.from_config(AlembicConfig(str(ROOT / "alembic.ini")))
    assert script.get_heads() == [HEAD_REVISION]


def test_v5_5_upgrade_downgrade_upgrade_preserves_v5_4_rows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_path = tmp_path / "v5-5-loop.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    _migrate(database_url, V5_4_REVISION, monkeypatch)
    engine = create_database_engine(database_url)
    try:
        with engine.begin() as session:
            session.execute(
                text(
                    """
                    INSERT INTO optimization_studies (
                        id, request_id, request_payload_hash, label, objective, status,
                        base_policy_id, search_space_json, weights_json, budget_json,
                        budget_usage_json, seed, algorithm_version, base_policy_fingerprint
                    ) VALUES (
                        'study-v54', 'req-v54', 'h', 'V5.4 study', 'balanced', 'pending',
                        '00000000-0000-0000-0000-000000000001', '{}', '{}', '{}', '{}',
                        1, 'v5_4a_1', 'f'
                    )
                    """
                )
            )
            session.execute(
                text(
                    """
                    INSERT INTO optimization_trials (
                        id, study_id, ordinal, status, config_sha256, config_json,
                        is_baseline, dominated, attempt
                    ) VALUES (
                        'trial-v54', 'study-v54', 1, 'pending', 'f', '{}', 1, 0, 0
                    )
                    """
                )
            )
    finally:
        engine.dispose()

    _migrate(database_url, V5_5_REVISION, monkeypatch)
    engine = create_database_engine(database_url)
    try:
        inspector = inspect(engine)
        columns = {column["name"] for column in inspector.get_columns("optimization_trials")}
        assert {"draft_policy_id", "request_id"} <= columns
        with engine.begin() as session:
            kept = session.execute(
                text("SELECT id FROM optimization_trials WHERE id = 'trial-v54'")
            ).scalar()
            assert kept == "trial-v54"
    finally:
        engine.dispose()

    _migrate(database_url, V5_4_REVISION, monkeypatch, downgrade=True)
    engine = create_database_engine(database_url)
    try:
        inspector = inspect(engine)
        columns = {column["name"] for column in inspector.get_columns("optimization_trials")}
        assert "draft_policy_id" not in columns and "request_id" not in columns
        with engine.begin() as session:
            kept = session.execute(
                text("SELECT id FROM optimization_studies WHERE id = 'study-v54'")
            ).scalar()
            assert kept == "study-v54"
    finally:
        engine.dispose()

    _migrate(database_url, V5_5_REVISION, monkeypatch)
