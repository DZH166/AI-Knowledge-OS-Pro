from __future__ import annotations

from copy import deepcopy
import json

import pytest
from sqlalchemy import event

from app.core.config import settings
from app.models.evidence_index import IndexOperation, VectorPointManifest
from app.models.source import (
    CitationLocator,
    IndexRevision,
    MultimodalChunk,
    Source,
    SourceRevision,
    VisualFrame,
)
from app.modules.evidence_index import (
    ActiveScope,
    SearchEvidence,
    SqlEvidenceIndex,
    VectorWriteError,
)
from app.services.media_service import MediaService
from app.services.ocr_service import OCRResult, VisionDescriptionResult
from tests.conftest import FakeEmbeddingService, FakeVectorStore
from tests.test_v3_audio_transcription import FakeTranscriptionProvider, make_wav_upload
from tests.test_v3_image_ocr import FakeOCRProvider
from tests.test_v3_image_upload import make_png_upload
from tests.test_v3_5_video_transcription import (
    FakeVideoTranscriptionProvider,
    make_video_upload,
)


class _ImageEnhancementProvider(FakeOCRProvider):
    def describe_image(self, image_path, mime_type=None) -> VisionDescriptionResult:
        assert image_path.exists()
        return VisionDescriptionResult(
            description="新的架构图视觉描述",
            content_type="chart",
            learning_points=["先检索，再生成"],
            provider=self.name,
            model=self.model,
        )


class _MediaEnhancementProvider(FakeOCRProvider):
    def __init__(self) -> None:
        self.extract_calls = 0
        self.describe_calls = 0
        self.fail_extract_on: int | None = None
        self.fail_describe_on: int | None = None

    def extract_text(self, image_path, mime_type=None) -> OCRResult:
        self.extract_calls += 1
        if self.extract_calls == self.fail_extract_on:
            raise RuntimeError("simulated enhancement provider failure")
        assert image_path.exists()
        return OCRResult(
            text=f"关键帧 OCR 第 {self.extract_calls} 轮：Evidence Agent",
            provider=self.name,
            model=self.model,
        )

    def describe_image(self, image_path, mime_type=None) -> VisionDescriptionResult:
        self.describe_calls += 1
        if self.describe_calls == self.fail_describe_on:
            raise RuntimeError("simulated enhancement provider failure")
        assert image_path.exists()
        return VisionDescriptionResult(
            description=f"视觉描述第 {self.describe_calls} 轮：RAG 证据架构图",
            content_type="chart",
            learning_points=["证据先于回答"],
            provider=self.name,
            model=self.model,
        )


def _prepare_enhancement_source(
    db_session,
    knowledge_space,
    tmp_path,
    monkeypatch,
    entrypoint: str,
):
    monkeypatch.setattr(settings, "upload_dir", tmp_path / "uploads")
    provider = _MediaEnhancementProvider()
    embedding = FakeEmbeddingService()
    vector_store = FakeVectorStore()
    service = MediaService(
        ocr_provider=provider,
        transcription_provider=FakeVideoTranscriptionProvider(),
        embedding_service=embedding,
        vector_store=vector_store,
    )
    if entrypoint == "image_visual_description":
        source = service.upload_image(
            db_session,
            knowledge_space.id,
            make_png_upload(name="enhancement-visual.png"),
        )
        source = service.process_image_ocr(db_session, source.id)
        source = service.process_image_visual_description(db_session, source.id)
        return service, provider, embedding, vector_store, source

    source = service.upload_video(
        db_session,
        knowledge_space.id,
        make_video_upload(tmp_path),
    )
    source = service.process_audio_transcription(db_session, source.id)
    active_revision = next(
        revision
        for revision in source.revisions
        if revision.id == source.active_revision_id
    )
    first_frame = active_revision.visual_frames[0]
    db_session.add(
        VisualFrame(
            source_id=source.id,
            revision_id=active_revision.id,
            frame_index=1,
            timestamp_ms=750,
            storage_path=first_frame.storage_path,
            metadata_json=json.dumps(
                {"asset_type": "keyframe", "superseded": False},
                ensure_ascii=False,
            ),
        )
    )
    db_session.commit()
    source = service.process_video_keyframe_ocr(db_session, source.id)
    source = service.process_video_visual_description(db_session, source.id)
    return service, provider, embedding, vector_store, source


def _process_enhancement(service: MediaService, entrypoint: str, db_session, source_id: int):
    return getattr(service, f"process_{entrypoint}")(db_session, source_id)


def _active_media_snapshot(db_session, source: Source, vector_store: FakeVectorStore) -> dict:
    revision_id = source.active_revision_id
    index_revision_id = source.active_index_revision_id
    chunks = list(
        db_session.query(MultimodalChunk)
        .filter_by(revision_id=revision_id)
        .order_by(MultimodalChunk.id)
    )
    frames = list(
        db_session.query(VisualFrame)
        .filter_by(revision_id=revision_id)
        .order_by(VisualFrame.id)
    )
    return {
        "revision_id": revision_id,
        "index_revision_id": index_revision_id,
        "chunks": [
            (
                chunk.id,
                chunk.modality,
                chunk.content_text,
                chunk.locator_json,
                chunk.frame_id,
                chunk.status,
            )
            for chunk in chunks
        ],
        "frames": [
            (
                frame.id,
                frame.ocr_text,
                frame.visual_description,
                frame.storage_path,
                frame.metadata_json,
            )
            for frame in frames
        ],
        "point_ids": {
            chunk.qdrant_point_id for chunk in chunks if chunk.qdrant_point_id
        },
        "points": deepcopy(vector_store.points),
    }


def test_repeated_transcription_retires_old_sql_and_vector_evidence(
    db_session,
    knowledge_space,
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "upload_dir", tmp_path)
    vector_store = FakeVectorStore()
    service = MediaService(
        transcription_provider=FakeTranscriptionProvider(),
        embedding_service=FakeEmbeddingService(),
        vector_store=vector_store,
    )
    source = service.upload_audio(db_session, knowledge_space.id, make_wav_upload())

    first = service.process_audio_transcription(db_session, source.id)
    first_revision_id = first.active_revision_id
    first_point_ids = set(vector_store.points)
    second = service.process_audio_transcription(db_session, source.id)

    active_revisions = (
        db_session.query(SourceRevision)
        .filter_by(source_id=source.id, status="active")
        .all()
    )
    active_indexes = (
        db_session.query(IndexRevision)
        .filter_by(source_id=source.id, status="active")
        .all()
    )
    active_chunks = (
        db_session.query(MultimodalChunk)
        .filter_by(source_id=source.id, status="active")
        .all()
    )
    old_chunks = (
        db_session.query(MultimodalChunk)
        .filter_by(
            source_id=source.id,
            revision_id=first_revision_id,
        )
        .all()
    )

    assert len(active_revisions) == 1
    assert active_revisions[0].id == second.active_revision_id
    assert len(active_indexes) == 1
    assert second.active_index_revision_id == active_indexes[0].id
    assert len(active_chunks) == 2
    assert all(chunk.content_hash for chunk in active_chunks)
    assert all(
        chunk.status == "retired" and chunk.retired_at is not None
        for chunk in old_chunks
    )
    assert first_point_ids.issubset(set(vector_store.deleted))
    assert not first_point_ids.intersection(vector_store.points)
    assert all(
        point["payload"]["revision_id"] == second.active_revision_id
        and point["payload"]["index_revision_id"] == second.active_index_revision_id
        for point in vector_store.points.values()
    )


def test_image_visual_description_embedding_failure_keeps_ocr_revision_queryable(
    db_session,
    knowledge_space,
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "upload_dir", tmp_path)
    embedding = FakeEmbeddingService()
    vector_store = FakeVectorStore()
    service = MediaService(
        ocr_provider=_ImageEnhancementProvider(),
        embedding_service=embedding,
        vector_store=vector_store,
    )
    source = service.upload_image(
        db_session,
        knowledge_space.id,
        make_png_upload(name="visual-safe.png"),
    )
    source = service.process_image_ocr(db_session, source.id)
    previous_revision_id = source.active_revision_id
    previous_index_revision_id = source.active_index_revision_id
    previous_points = deepcopy(vector_store.points)

    def fail_embedding(_texts: list[str]) -> list[list[float]]:
        raise RuntimeError("simulated enhancement embedding failure")

    monkeypatch.setattr(embedding, "embed_texts", fail_embedding)

    with pytest.raises(RuntimeError, match="simulated enhancement embedding failure"):
        service.process_image_visual_description(db_session, source.id)

    db_session.expire_all()
    source = db_session.get(Source, source.id)
    assert source is not None
    assert source.active_revision_id == previous_revision_id
    assert source.active_index_revision_id == previous_index_revision_id
    assert vector_store.points == previous_points
    assert not set(previous_points).intersection(vector_store.deleted)
    result = SqlEvidenceIndex(db_session).search(
        SearchEvidence(
            text="ModuleNotFoundError",
            scope=ActiveScope(
                space_id=knowledge_space.id,
                source_ids=(source.id,),
            ),
        )
    )
    assert result.hits
    assert {hit.evidence.revision_id for hit in result.hits} == {
        previous_revision_id
    }


@pytest.mark.parametrize("media_kind", ["audio", "image"])
@pytest.mark.parametrize("failure_mode", ["embedding", "vector", "sql"])
def test_failed_media_replacement_keeps_previous_evidence_query_visible(
    db_session,
    knowledge_space,
    tmp_path,
    monkeypatch,
    media_kind: str,
    failure_mode: str,
) -> None:
    monkeypatch.setattr(settings, "upload_dir", tmp_path)
    embedding = FakeEmbeddingService()
    vector_store = FakeVectorStore()
    if media_kind == "audio":
        service = MediaService(
            transcription_provider=FakeTranscriptionProvider(),
            embedding_service=embedding,
            vector_store=vector_store,
        )
        source = service.upload_audio(db_session, knowledge_space.id, make_wav_upload())
        service.process_audio_transcription(db_session, source.id)
        process = service.process_audio_transcription
        query = "RAG 先检索资料"
        status_key = "transcription_status"
    else:
        service = MediaService(
            ocr_provider=FakeOCRProvider(),
            embedding_service=embedding,
            vector_store=vector_store,
        )
        source = service.upload_image(
            db_session,
            knowledge_space.id,
            make_png_upload(name="stable-evidence.png"),
        )
        service.process_image_ocr(db_session, source.id)
        process = service.process_image_ocr
        query = "ModuleNotFoundError"
        status_key = "ocr_status"

    db_session.expire_all()
    source = db_session.get(Source, source.id)
    assert source is not None
    previous_revision_id = source.active_revision_id
    previous_index_revision_id = source.active_index_revision_id
    assert previous_revision_id is not None
    assert previous_index_revision_id is not None
    previous_chunk_ids = {
        chunk.id
        for chunk in db_session.query(MultimodalChunk).filter_by(
            revision_id=previous_revision_id
        )
    }
    assert previous_chunk_ids
    previous_point_ids = {
        chunk.qdrant_point_id
        for chunk in db_session.query(MultimodalChunk).filter_by(
            revision_id=previous_revision_id
        )
        if chunk.qdrant_point_id
    }
    previous_points = deepcopy(
        {point_id: vector_store.points[point_id] for point_id in previous_point_ids}
    )

    activation_listener = None
    if failure_mode == "embedding":

        def fail_embedding(_texts: list[str]) -> list[list[float]]:
            raise RuntimeError("simulated embedding failure")

        monkeypatch.setattr(embedding, "embed_texts", fail_embedding)
        expected_error: type[Exception] = RuntimeError
        expected_message = "simulated embedding failure"
    elif failure_mode == "vector":

        def fail_vector_write(*_args, **_kwargs) -> None:
            raise RuntimeError("simulated vector failure")

        monkeypatch.setattr(vector_store, "upsert_chunks", fail_vector_write)
        expected_error = VectorWriteError
        expected_message = "manifest was committed"
    else:
        armed = True
        activation_count = (
            db_session.query(IndexOperation)
            .filter_by(operation_type="activate_revision")
            .count()
        )

        def fail_activation_commit(session) -> None:
            nonlocal armed
            current_count = (
                session.query(IndexOperation)
                .filter_by(operation_type="activate_revision")
                .count()
            )
            if armed and current_count > activation_count:
                armed = False
                raise RuntimeError("simulated activation SQL failure")

        activation_listener = fail_activation_commit
        event.listen(db_session, "before_commit", activation_listener)
        expected_error = RuntimeError
        expected_message = "simulated activation SQL failure"

    try:
        with pytest.raises(expected_error, match=expected_message):
            process(db_session, source.id)
    finally:
        if activation_listener is not None:
            event.remove(db_session, "before_commit", activation_listener)

    db_session.expire_all()
    source = db_session.get(Source, source.id)
    assert source is not None
    assert source.active_revision_id == previous_revision_id
    assert source.active_index_revision_id == previous_index_revision_id
    assert source.metadata_data[status_key] == "failed"

    previous_revision = db_session.get(SourceRevision, previous_revision_id)
    previous_index = db_session.get(IndexRevision, previous_index_revision_id)
    assert previous_revision is not None and previous_revision.status == "active"
    assert previous_index is not None and previous_index.status == "active"
    active_chunks = list(
        db_session.query(MultimodalChunk).filter_by(
            revision_id=previous_revision_id,
            status="active",
        )
    )
    assert {chunk.id for chunk in active_chunks} == previous_chunk_ids
    assert previous_point_ids.isdisjoint(vector_store.deleted)
    assert {
        point_id: vector_store.points[point_id] for point_id in previous_point_ids
    } == previous_points
    vector_hits = vector_store.search(
        knowledge_space.id,
        [0.0] * embedding.provider.dimensions,
        limit=100,
        score_threshold=0.0,
    )
    assert any(
        hit.payload["revision_id"] == previous_revision_id for hit in vector_hits
    )

    active_result = SqlEvidenceIndex(db_session).search(
        SearchEvidence(
            text=query,
            scope=ActiveScope(
                space_id=knowledge_space.id,
                source_ids=(source.id,),
            ),
        )
    )
    assert active_result.hits
    assert {hit.evidence.revision_id for hit in active_result.hits} == {
        previous_revision_id
    }


@pytest.mark.parametrize(
    "entrypoint",
    [
        "image_visual_description",
        "video_keyframe_ocr",
        "video_visual_description",
    ],
)
@pytest.mark.parametrize("failure_mode", ["provider", "embedding", "upsert", "commit"])
def test_failed_media_enhancement_preserves_the_complete_active_evidence_set(
    db_session,
    knowledge_space,
    tmp_path,
    monkeypatch,
    entrypoint: str,
    failure_mode: str,
) -> None:
    service, provider, embedding, vector_store, source = _prepare_enhancement_source(
        db_session,
        knowledge_space,
        tmp_path,
        monkeypatch,
        entrypoint,
    )
    db_session.expire_all()
    source = service.get_source(db_session, source.id)
    before = _active_media_snapshot(db_session, source, vector_store)
    assert before["point_ids"]
    max_index_revision_id = max(
        index.id for index in db_session.query(IndexRevision).all()
    )
    previous_revision_number = db_session.get(
        SourceRevision, before["revision_id"]
    ).revision_number
    status_key = {
        "image_visual_description": "vision_description_status",
        "video_keyframe_ocr": "keyframe_ocr_status",
        "video_visual_description": "visual_description_status",
    }[entrypoint]

    activation_listener = None
    if failure_mode == "provider":
        if entrypoint == "video_keyframe_ocr":
            provider.fail_extract_on = provider.extract_calls + 2
        else:
            provider.fail_describe_on = provider.describe_calls + (
                2 if entrypoint == "video_visual_description" else 1
            )
        expected_error: type[Exception] = RuntimeError
        expected_message = "simulated enhancement provider failure"
    elif failure_mode == "embedding":

        def fail_embedding(_texts: list[str]) -> list[list[float]]:
            raise RuntimeError("simulated enhancement embedding failure")

        monkeypatch.setattr(embedding, "embed_texts", fail_embedding)
        expected_error = RuntimeError
        expected_message = "simulated enhancement embedding failure"
    elif failure_mode == "upsert":

        def fail_upsert(*_args, **_kwargs) -> None:
            raise RuntimeError("simulated enhancement upsert failure")

        monkeypatch.setattr(vector_store, "upsert_chunks", fail_upsert)
        expected_error = VectorWriteError
        expected_message = "manifest was committed"
    else:
        armed = True

        def fail_activation_commit(session) -> None:
            nonlocal armed
            replacement_is_being_activated = session.scalar(
                db_session.query(IndexRevision.id)
                .filter(
                    IndexRevision.id > max_index_revision_id,
                    IndexRevision.status == "active",
                )
                .statement.limit(1)
            )
            if armed and replacement_is_being_activated is not None:
                armed = False
                raise RuntimeError("simulated enhancement activation commit failure")

        activation_listener = fail_activation_commit
        event.listen(db_session, "before_commit", activation_listener)
        expected_error = RuntimeError
        expected_message = "simulated enhancement activation commit failure"

    try:
        with pytest.raises(expected_error, match=expected_message):
            _process_enhancement(service, entrypoint, db_session, source.id)
    finally:
        if activation_listener is not None:
            event.remove(db_session, "before_commit", activation_listener)

    db_session.expire_all()
    source = service.get_source(db_session, source.id)
    after = _active_media_snapshot(db_session, source, vector_store)
    assert source.metadata_data[status_key] == "failed"
    assert after == before
    assert before["point_ids"].isdisjoint(vector_store.deleted)
    assert set(vector_store.points) == before["point_ids"]
    assert db_session.get(SourceRevision, before["revision_id"]).status == "active"
    assert db_session.get(IndexRevision, before["index_revision_id"]).status == "active"

    later_revisions = list(
        db_session.query(SourceRevision).filter(
            SourceRevision.source_id == source.id,
            SourceRevision.revision_number > previous_revision_number,
        )
    )
    if failure_mode == "provider":
        assert later_revisions == []
    else:
        assert later_revisions
        assert {revision.status for revision in later_revisions} == {"cancelled"}
        later_ids = {revision.id for revision in later_revisions}
        manifests = list(
            db_session.query(VectorPointManifest).filter(
                VectorPointManifest.revision_id.in_(later_ids)
            )
        )
        assert manifests
        assert all(manifest.point_id not in vector_store.points for manifest in manifests)

    target_modality = {
        "image_visual_description": "image_description",
        "video_keyframe_ocr": "video_frame_text",
        "video_visual_description": "video_frame_description",
    }[entrypoint]
    old_target_content = next(
        content
        for _id, modality, content, *_rest in before["chunks"]
        if modality == target_modality
    )
    active_result = SqlEvidenceIndex(db_session).search(
        SearchEvidence(
            text=old_target_content,
            scope=ActiveScope(
                space_id=knowledge_space.id,
                source_ids=(source.id,),
            ),
        )
    )
    assert active_result.hits
    assert {hit.evidence.revision_id for hit in active_result.hits} == {
        before["revision_id"]
    }


@pytest.mark.parametrize(
    "entrypoint",
    [
        "image_visual_description",
        "video_keyframe_ocr",
        "video_visual_description",
    ],
)
def test_successful_media_enhancement_atomically_replaces_the_whole_evidence_set(
    db_session,
    knowledge_space,
    tmp_path,
    monkeypatch,
    entrypoint: str,
) -> None:
    service, _provider, _embedding, vector_store, source = _prepare_enhancement_source(
        db_session,
        knowledge_space,
        tmp_path,
        monkeypatch,
        entrypoint,
    )
    db_session.expire_all()
    source = service.get_source(db_session, source.id)
    before = _active_media_snapshot(db_session, source, vector_store)
    before_by_modality: dict[str, list[str]] = {}
    for _id, modality, content, *_rest in before["chunks"]:
        before_by_modality.setdefault(modality, []).append(content)

    source = _process_enhancement(service, entrypoint, db_session, source.id)
    db_session.expire_all()
    source = service.get_source(db_session, source.id)
    after = _active_media_snapshot(db_session, source, vector_store)
    assert after["revision_id"] != before["revision_id"]
    assert after["index_revision_id"] != before["index_revision_id"]
    assert db_session.get(SourceRevision, before["revision_id"]).status == "retired"
    assert db_session.get(IndexRevision, before["index_revision_id"]).status == "retired"
    assert before["point_ids"].issubset(set(vector_store.deleted))
    assert before["point_ids"].isdisjoint(vector_store.points)
    assert set(vector_store.points) == after["point_ids"]

    after_by_modality: dict[str, list[str]] = {}
    for _id, modality, content, locator_json, frame_id, status in after["chunks"]:
        after_by_modality.setdefault(modality, []).append(content)
        locator = json.loads(locator_json)
        assert locator["kind"] in {"image_region", "media_time"}
        assert status == "active"
        if modality.startswith("video_frame_"):
            assert frame_id is not None
            assert locator["kind"] == "media_time"

    target_modality = {
        "image_visual_description": "image_description",
        "video_keyframe_ocr": "video_frame_text",
        "video_visual_description": "video_frame_description",
    }[entrypoint]
    complementary_modalities = {
        "image_visual_description": {"image_text"},
        "video_keyframe_ocr": {"video_transcript", "video_frame_description"},
        "video_visual_description": {"video_transcript", "video_frame_text"},
    }[entrypoint]
    assert after_by_modality[target_modality] != before_by_modality[target_modality]
    for modality in complementary_modalities:
        assert after_by_modality[modality] == before_by_modality[modality]

    active_revision = db_session.get(SourceRevision, after["revision_id"])
    new_frame_ids = {frame.id for frame in active_revision.visual_frames}
    for chunk in active_revision.chunks:
        if chunk.modality.startswith("video_frame_"):
            assert chunk.frame_id in new_frame_ids
    if entrypoint.startswith("video_"):
        assert len(active_revision.transcript_segments) == 2
        assert [
            segment.text
            for segment in sorted(
                active_revision.transcript_segments,
                key=lambda item: item.segment_index,
            )
        ] == ["视频里先讲 RAG 检索。", "再讲引用校验。"]
        assert all(frame.ocr_text for frame in active_revision.visual_frames)
        assert all(
            frame.visual_description for frame in active_revision.visual_frames
        )
    assert (
        db_session.query(CitationLocator)
        .filter_by(revision_id=after["revision_id"])
        .count()
        == len(active_revision.chunks)
    )

    new_target_content = after_by_modality[target_modality][0]
    active_result = SqlEvidenceIndex(db_session).search(
        SearchEvidence(
            text=new_target_content,
            scope=ActiveScope(
                space_id=knowledge_space.id,
                source_ids=(source.id,),
            ),
        )
    )
    assert active_result.hits
    assert {hit.evidence.revision_id for hit in active_result.hits} == {
        after["revision_id"]
    }
