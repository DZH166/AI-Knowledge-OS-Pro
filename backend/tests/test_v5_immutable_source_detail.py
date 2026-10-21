from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app
from app.models.source import IndexRevision, MultimodalChunk, Source, SourceRevision


def test_source_detail_keeps_retired_revision_chunks_hash_addressable(db_session, knowledge_space) -> None:
    source = Source(
        space_id=knowledge_space.id,
        document_id=None,
        source_type="code_repository",
        title="Immutable source",
        original_filename="immutable-source",
        mime_type="application/x-git",
        file_size=0,
        content_hash="f" * 64,
        status="ready",
    )
    db_session.add(source)
    db_session.flush()
    retired = SourceRevision(
        source_id=source.id,
        revision_number=1,
        status="retired",
        content_hash="a" * 64,
        chunk_count=1,
        vector_count=1,
        validation_status="passed",
    )
    active = SourceRevision(
        source_id=source.id,
        revision_number=2,
        status="active",
        content_hash="c" * 64,
        chunk_count=1,
        vector_count=1,
        validation_status="passed",
    )
    db_session.add_all([retired, active])
    db_session.flush()
    retired_index = IndexRevision(
        source_id=source.id,
        revision_id=retired.id,
        status="retired",
        index_version="immutable-v1",
        point_count=1,
        validation_status="passed",
    )
    active_index = IndexRevision(
        source_id=source.id,
        revision_id=active.id,
        status="active",
        index_version="immutable-v1",
        point_count=1,
        validation_status="passed",
    )
    db_session.add_all([retired_index, active_index])
    db_session.flush()
    retired_chunk = MultimodalChunk(
        source_id=source.id,
        revision_id=retired.id,
        chunk_index=0,
        modality="code_file",
        source_type="code_repository",
        content_text="retired canonical evidence",
        content_hash="b" * 64,
        search_text="retired canonical evidence",
        locator_json='{"kind":"code_range","file_path":"app.py","line_start":1,"line_end":1}',
        status="retired",
    )
    active_chunk = MultimodalChunk(
        source_id=source.id,
        revision_id=active.id,
        chunk_index=0,
        modality="code_file",
        source_type="code_repository",
        content_text="new active content",
        content_hash="d" * 64,
        search_text="new active content",
        locator_json='{"kind":"code_range","file_path":"app.py","line_start":1,"line_end":1}',
        status="active",
    )
    db_session.add_all([retired_chunk, active_chunk])
    db_session.flush()
    source.active_revision_id = active.id
    source.latest_revision_id = active.id
    source.active_index_revision_id = active_index.id
    db_session.commit()

    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    try:
        response = TestClient(app).get(f"/api/media/sources/{source.id}")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["active_index_revision_id"] == active_index.id
    revisions = {item["id"]: item for item in payload["revisions"]}
    assert revisions[retired.id]["content_hash"] == "a" * 64
    assert revisions[retired.id]["status"] == "retired"
    assert revisions[retired.id]["index_revisions"] == [
        {
            "id": retired_index.id,
            "source_id": source.id,
            "revision_id": retired.id,
            "status": "retired",
            "index_version": "immutable-v1",
        }
    ]
    chunks = {item["id"]: item for item in revisions[retired.id]["chunks"]}
    assert chunks[retired_chunk.id]["content_hash"] == "b" * 64
    assert chunks[retired_chunk.id]["content_text"] == "retired canonical evidence"
    assert chunks[retired_chunk.id]["status"] == "retired"
