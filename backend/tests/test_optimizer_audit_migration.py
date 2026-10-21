import json

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text

from app.core.config import settings
from app.db.session import create_database_engine
from tests.test_v5_7_integration_migration import ROOT


def test_populated_warm_start_snapshot_survives_upgrade_and_roundtrip(tmp_path, monkeypatch):
    database_url = f"sqlite:///{(tmp_path / 'audit-migration.db').as_posix()}"
    monkeypatch.setattr(settings, "database_url", database_url)
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "0015_v5_7_integration")
    engine = create_database_engine(database_url)
    try:
        with engine.begin() as connection:
            for study_id, parent_id in (("parent", None), ("child", "parent")):
                connection.execute(text("""
                    INSERT INTO optimization_studies (
                        id, request_id, request_payload_hash, label, objective, status,
                        base_policy_id, search_space_json, weights_json, budget_json,
                        budget_usage_json, seed, algorithm_version, base_policy_fingerprint,
                        round_no, warm_start_study_id
                    ) VALUES (
                        :id, :id, 'hash', 'study', 'balanced', 'pending',
                        '00000000-0000-0000-0000-000000000001', '{}', '{}', '{}',
                        '{}', 42, 'v5_6_bayesian_1', 'fingerprint', 2, :parent
                    )
                """), {"id": study_id, "parent": parent_id})
            connection.execute(text("""
                INSERT INTO optimization_trials (
                    id, study_id, ordinal, round_no, status, config_sha256, config_json,
                    is_baseline, dominated, attempt, score_millis
                ) VALUES ('trial-parent', 'parent', 1, 1, 'completed', 'fingerprint', '{}', 1, 0, 1, 500)
            """))
        command.upgrade(config, "head")
        with engine.connect() as connection:
            value = connection.execute(text(
                "SELECT warm_start_observations_json FROM optimization_studies WHERE id='child'"
            )).scalar_one()
            snapshot = json.loads(value)
            assert snapshot["captured_at"] == "migration"
            assert snapshot["observations"][0]["score_millis"] == 500
        command.downgrade(config, "0015_v5_7_integration")
        assert "warm_start_observations_json" not in {item["name"] for item in inspect(engine).get_columns("optimization_studies")}
        command.upgrade(config, "head")
        with engine.connect() as connection:
            assert connection.execute(text("SELECT count(*) FROM optimization_studies")).scalar_one() == 2
    finally:
        engine.dispose()
