from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import inspect, text

from app.core.config import settings
from app.db.session import create_database_engine


ROOT = Path(__file__).resolve().parents[2]
V5_7_BACKEND = "0014_v5_7_workbench_backend"
V5_7_INTEGRATION = "0015_v5_7_integration"


def _migrate(database_url: str, revision: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "database_url", database_url)
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, revision)


def test_round_command_migration_is_single_head_and_round_trips(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = f"sqlite:///{(tmp_path / 'v57-integration.db').as_posix()}"
    _migrate(database_url, V5_7_BACKEND, monkeypatch)
    engine = create_database_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO optimization_studies (
                        id, request_id, request_payload_hash, label, objective, status,
                        base_policy_id, search_space_json, weights_json, budget_json,
                        budget_usage_json, seed, algorithm_version, base_policy_fingerprint,
                        round_no, next_round_request_id
                    ) VALUES (
                        'study-v57', 'study-v57-request', 'hash', 'V5.7 study', 'balanced',
                        'completed', '00000000-0000-0000-0000-000000000001', '{}', '{}',
                        '{}', '{}', 1, 'v5_4a_1', 'fingerprint', 2, 'historical-round-request'
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO optimization_trials (
                        id, study_id, ordinal, round_no, status, config_sha256,
                        config_json, is_baseline, dominated, attempt
                    ) VALUES (
                        'historical-trial', 'study-v57', 2, 2, 'completed',
                        'fingerprint', '{}', 0, 0, 1
                    )
                    """
                )
            )
    finally:
        engine.dispose()

    _migrate(database_url, V5_7_INTEGRATION, monkeypatch)
    engine = create_database_engine(database_url)
    try:
        assert "optimization_round_commands" in inspect(engine).get_table_names()
        with engine.begin() as connection:
            backfilled = connection.execute(
                text(
                    """
                    SELECT request_id, round_no, created_count, receipt_json
                    FROM optimization_round_commands
                    WHERE study_id='study-v57'
                    """
                )
            ).mappings().one()
            assert backfilled["request_id"] == "historical-round-request"
            assert backfilled["round_no"] == 2
            assert backfilled["created_count"] == 1
            assert '"created":1' in backfilled["receipt_json"]
            connection.execute(
                text(
                    """
                    INSERT INTO optimization_round_commands (
                        id, study_id, request_id, round_no, created_count, receipt_json
                    ) VALUES (
                        'round-command-v57', 'study-v57', 'round-request-v57', 2, 3,
                        :receipt
                    )
                    """
                ),
                {
                    "receipt": (
                        '{"study_id":"study-v57","round_no":2,'
                        '"created":3,"replayed":false}'
                    )
                },
            )
        config = Config(str(ROOT / "alembic.ini"))
        config.set_main_option("sqlalchemy.url", database_url)
        command.downgrade(config, V5_7_BACKEND)
        assert "optimization_round_commands" not in inspect(engine).get_table_names()
        with engine.connect() as connection:
            assert connection.execute(
                text("SELECT id FROM optimization_studies WHERE id='study-v57'")
            ).scalar_one() == "study-v57"
        command.upgrade(config, V5_7_INTEGRATION)
        assert "optimization_round_commands" in inspect(engine).get_table_names()
    finally:
        engine.dispose()
