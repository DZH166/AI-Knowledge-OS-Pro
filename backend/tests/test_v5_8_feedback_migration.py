from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.session import create_database_engine
from app.models.agent_evidence import AgentArtifact
from app.models.agent_run import AgentRun
from app.models.knowledge_space import KnowledgeSpace
from app.modules.feedback.contracts import ListFeedback, ReviewFeedback, SubmitFeedback
from app.modules.feedback.service import SqlFeedback


def test_feedback_migration_preserves_old_research_and_roundtrips_new_tables(tmp_path, monkeypatch):
    url = f"sqlite:///{(tmp_path / 'feedback-migration.db').as_posix()}"
    monkeypatch.setattr(settings, "database_url", url)
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    command.upgrade(config, "0016_optimizer_audit")
    engine = create_database_engine(url)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        with factory.begin() as session:
            session.add(KnowledgeSpace(id=99, name="Migration source", description="Synthetic"))
        with factory.begin() as session:
            session.add(AgentRun(id="migration-run", space_id=99, goal="Keep this original question", requested_mode="force_quick",
                                 status="completed", phase="done", provider_mode="demo", scope_snapshot_json="{}", scope_digest="a"*64,
                                 final_artifact_id="migration-artifact"))
        with factory.begin() as session:
            session.add(AgentArtifact(id="migration-artifact", producing_run_id="migration-run", kind="answer",
                                      title="Original", body_markdown="Original immutable answer", status="final"))
        command.upgrade(config, "head")
        feedback = SqlFeedback(factory)
        saved = feedback.submit(SubmitFeedback(request_id="migration-submit", artifact_id="migration-artifact",
                                                issue="incomplete_answer", comment="Needs a measured example"))
        accepted = feedback.review(saved.feedback.id, ReviewFeedback(request_id="migration-review", expected_version=1,
                                    decision="accepted", reason="Reviewed", expected_answer="A measured example",
                                    acceptance_criteria="Includes the source", split="tuning"))
        command.upgrade(config, "head")
        assert feedback.get(saved.feedback.id) == accepted.feedback
        command.downgrade(config, "0016_optimizer_audit")
        assert "research_feedback" not in inspect(engine).get_table_names()
        with factory() as session:
            assert session.get(AgentArtifact, "migration-artifact").body_markdown == "Original immutable answer"
            assert session.get(AgentRun, "migration-run").goal == "Keep this original question"
        command.upgrade(config, "head")
        assert feedback.list(ListFeedback()).items == []
        assert {"research_feedback", "feedback_samples"}.issubset(inspect(engine).get_table_names())
    finally:
        engine.dispose()
