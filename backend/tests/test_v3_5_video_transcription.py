from io import BytesIO
import json
from pathlib import Path
import subprocess

from fastapi import UploadFile
import pytest

from app.core.errors import ConfigurationError
from app.models.source import CitationLocator, MediaAsset, MultimodalChunk, TranscriptSegment, VisualFrame
from app.services.media_service import MediaService
from app.services.rag_service import RAGService
from app.services.transcription_service import (
    TranscriptionResult,
    TranscriptionSegmentResult,
    UnconfiguredTranscriptionProvider,
)
from app.services.video_service import video_tooling
from tests.conftest import FakeEmbeddingService, FakeLLMService, FakeVectorStore


def make_video_upload(tmp_path: Path, name: str = "lesson.mp4", content_type: str = "video/mp4") -> UploadFile:
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir(parents=True, exist_ok=True)
    video_path = fixture_dir / name
    commands = [
        [
            video_tooling.ffmpeg_path,
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=32x24:rate=8:duration=1",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:sample_rate=16000:duration=1",
            "-shortest",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-movflags",
            "+faststart",
            str(video_path),
        ],
        [
            video_tooling.ffmpeg_path,
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=32x24:rate=8:duration=1",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:sample_rate=16000:duration=1",
            "-shortest",
            "-c:v",
            "mpeg4",
            "-q:v",
            "5",
            "-c:a",
            "aac",
            str(video_path),
        ],
    ]
    last_error = ""
    for command in commands:
        result = subprocess.run(command, capture_output=True, text=True, timeout=60)
        if result.returncode == 0 and video_path.exists():
            return UploadFile(
                filename=name,
                file=BytesIO(video_path.read_bytes()),
                headers={"content-type": content_type},
            )
        last_error = result.stderr
    pytest.skip(f"ffmpeg could not create a test video: {last_error[:300]}")


class FakeVideoTranscriptionProvider:
    name = "fake_video_transcription"
    model = "fake-whisper-video"

    def __init__(self) -> None:
        self.calls: list[tuple[Path, str | None]] = []

    def is_configured(self) -> bool:
        return True

    def transcribe(self, audio_path: Path, mime_type: str | None = None) -> TranscriptionResult:
        self.calls.append((audio_path, mime_type))
        assert audio_path.exists()
        assert audio_path.suffix.lower() == ".wav"
        assert mime_type == "audio/wav"
        return TranscriptionResult(
            text="视频里先讲 RAG 检索，再讲引用校验。",
            language="zh",
            duration_ms=1000,
            segments=[
                TranscriptionSegmentResult(index=0, start_ms=0, end_ms=500, text="视频里先讲 RAG 检索。", confidence=0.93),
                TranscriptionSegmentResult(index=1, start_ms=500, end_ms=1000, text="再讲引用校验。", confidence=0.9),
            ],
            provider=self.name,
            model=self.model,
        )


@pytest.mark.parametrize(
    ("filename", "content_type"),
    [("lesson.mp4", "video/mp4"), ("lesson.mov", "video/quicktime")],
)
def test_video_upload_reads_real_metadata_and_keyframe(
    db_session,
    knowledge_space,
    tmp_path,
    monkeypatch,
    filename: str,
    content_type: str,
) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "upload_dir", tmp_path / "uploads")
    service = MediaService()

    source = service.upload_video(db_session, knowledge_space.id, make_video_upload(tmp_path, filename, content_type))

    metadata = json.loads(source.metadata_json)
    asset_types = {asset.asset_type for asset in source.media_assets}
    active_revision = next(revision for revision in source.revisions if revision.id == source.active_revision_id)
    assert source.source_type == "video"
    assert 900 <= (source.duration_ms or 0) <= 1200
    assert source.width == 32
    assert source.height == 24
    assert metadata["has_audio"] is True
    assert metadata["keyframe_status"] == "completed"
    assert {"original_video", "keyframe"}.issubset(asset_types)
    assert len(active_revision.visual_frames) == 1
    assert Path(active_revision.visual_frames[0].storage_path or "").exists()


def test_video_transcription_requires_real_provider_without_extracting_audio(
    db_session,
    knowledge_space,
    tmp_path,
    monkeypatch,
) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "upload_dir", tmp_path / "uploads")
    service = MediaService(transcription_provider=UnconfiguredTranscriptionProvider())
    source = service.upload_video(db_session, knowledge_space.id, make_video_upload(tmp_path))
    asset_count = db_session.query(MediaAsset).count()

    with pytest.raises(ConfigurationError) as exc_info:
        service.process_audio_transcription(db_session, source.id)

    refreshed = service.get_source(db_session, source.id)
    assert exc_info.value.code == "TRANSCRIPTION_NOT_CONFIGURED"
    assert db_session.query(MediaAsset).count() == asset_count
    assert not any(asset.asset_type == "extracted_audio" for asset in refreshed.media_assets)
    assert refreshed.metadata_data["transcription_status"] == "not_configured"


def test_video_transcription_creates_timestamped_rag_chunks_and_video_citations(
    db_session,
    knowledge_space,
    tmp_path,
    monkeypatch,
) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "upload_dir", tmp_path / "uploads")
    fake_embedding = FakeEmbeddingService()
    fake_vector_store = FakeVectorStore()
    fake_transcription = FakeVideoTranscriptionProvider()
    service = MediaService(
        transcription_provider=fake_transcription,
        embedding_service=fake_embedding,
        vector_store=fake_vector_store,
    )

    source = service.upload_video(db_session, knowledge_space.id, make_video_upload(tmp_path))
    source = service.process_audio_transcription(db_session, source.id)

    segments = db_session.query(TranscriptSegment).order_by(TranscriptSegment.segment_index).all()
    chunks = db_session.query(MultimodalChunk).order_by(MultimodalChunk.chunk_index).all()
    locators = db_session.query(CitationLocator).order_by(CitationLocator.id).all()
    asset_types = [asset.asset_type for asset in source.media_assets]
    active_revision = next(revision for revision in source.revisions if revision.id == source.active_revision_id)

    assert len(fake_transcription.calls) == 1
    assert source.metadata_data["ingestion_mode"] == "video_transcription"
    assert source.metadata_data["transcription_status"] == "completed"
    assert source.metadata_data["extracted_audio_status"] == "completed"
    assert "extracted_audio" in asset_types
    assert "keyframe" in asset_types
    assert db_session.query(VisualFrame).count() >= 2
    assert len(active_revision.visual_frames) == 1
    assert len(segments) == 2
    assert segments[1].start_ms == 500
    assert segments[0].confidence == 93
    assert len(chunks) == 2
    assert chunks[0].modality == "video_transcript"
    assert chunks[0].source_type == "video"
    assert chunks[1].start_ms == 500
    assert chunks[1].qdrant_point_id
    locator = json.loads(chunks[0].locator_json)
    assert locator["type"] == "video"
    assert locator["asset"] == "original_video"
    assert len(locators) == 2
    assert locators[0].display_text == "视频 00:00"

    rag = RAGService()
    rag.embedding_service = fake_embedding
    rag.vector_store = fake_vector_store
    rag.llm_service = FakeLLMService()
    response = rag.ask_question(db_session, knowledge_space.id, "视频里讲了什么？", "normal")
    assert response.retrieval_status == "success"
    assert response.citations[0].source_type == "video"
    assert response.citations[0].start_ms == 0
    assert response.citations[1].start_ms == 500
