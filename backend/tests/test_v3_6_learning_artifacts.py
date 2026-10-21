import json

import pytest

from app.models.learning_artifact import LearningArtifact
from app.models.learning_note import LearningNote
from app.models.learning_system import KnowledgePoint, LearningCard, QuizQuestion
from app.models.source import MultimodalChunk, Source, SourceRevision
from app.schemas.learning_schema import LearningArtifactCreate
from app.services.learning_artifact_service import learning_artifact_service


def create_source_with_chunk(db_session, knowledge_space):
    source = Source(
        space_id=knowledge_space.id,
        source_type="video",
        title="RAG lesson clip",
        original_filename="lesson.mp4",
        mime_type="video/mp4",
        file_size=128,
        status="ready",
        metadata_json="{}",
    )
    db_session.add(source)
    db_session.flush()
    revision = SourceRevision(
        source_id=source.id,
        revision_number=1,
        status="active",
        parser_name="pytest",
        parser_version="v3.6",
        chunk_count=1,
        vector_count=1,
        validation_status="valid",
        metadata_json="{}",
    )
    db_session.add(revision)
    db_session.flush()
    chunk = MultimodalChunk(
        source_id=source.id,
        revision_id=revision.id,
        chunk_index=0,
        modality="video_transcript",
        source_type="video",
        content_text="RAG retrieves project knowledge first, then the answer cites exact source timestamps.",
        search_text="RAG retrieves project knowledge first, then the answer cites exact source timestamps.",
        locator_json=json.dumps({"type": "video", "source_id": source.id, "start_ms": 1500, "end_ms": 3000}),
        start_ms=1500,
        end_ms=3000,
        status="active",
    )
    db_session.add(chunk)
    db_session.flush()
    source.active_revision_id = revision.id
    source.latest_revision_id = revision.id
    db_session.commit()
    return source, chunk


def test_learning_artifacts_are_created_from_real_multimodal_chunk(db_session, knowledge_space) -> None:
    source, chunk = create_source_with_chunk(db_session, knowledge_space)

    result = learning_artifact_service.create_from_source(
        db_session,
        LearningArtifactCreate(
            source_id=source.id,
            chunk_id=chunk.id,
            artifact_types=["knowledge_point", "card", "quiz", "note", "interview_expression"],
            title="Citation-grounded RAG",
        ),
    )

    assert len(result.artifacts) == 5
    assert db_session.query(LearningArtifact).count() == 5
    assert db_session.query(KnowledgePoint).count() == 1
    assert db_session.query(LearningCard).count() == 1
    assert db_session.query(QuizQuestion).count() == 1
    assert db_session.query(LearningNote).count() == 1
    contents = {artifact.artifact_type: artifact.content for artifact in result.artifacts}
    assert "RAG retrieves project knowledge first" in contents["knowledge_point"]
    assert "01" in contents["interview_expression"] or "00:01" in contents["interview_expression"]
    assert result.artifacts[0].source_id == source.id
    assert result.artifacts[0].chunk_id == chunk.id


def test_learning_artifacts_refuse_media_without_real_text(db_session, knowledge_space) -> None:
    source = Source(
        space_id=knowledge_space.id,
        source_type="image",
        title="Empty image",
        original_filename="empty.png",
        mime_type="image/png",
        file_size=1,
        status="ready",
        metadata_json="{}",
    )
    db_session.add(source)
    db_session.commit()

    with pytest.raises(ValueError):
        learning_artifact_service.create_from_source(
            db_session,
            LearningArtifactCreate(source_id=source.id, artifact_types=["knowledge_point"]),
        )
