from io import BytesIO
from pathlib import Path
import wave

from fastapi import UploadFile
import pytest

from app.core.errors import ConfigurationError
from app.models.source import CitationLocator, MultimodalChunk, TranscriptSegment
from app.services.media_service import MediaService
from app.services.rag_service import RAGService
from app.services.transcription_service import (
    TranscriptionResult,
    TranscriptionSegmentResult,
    UnconfiguredTranscriptionProvider,
)
from tests.conftest import FakeEmbeddingService, FakeLLMService, FakeVectorStore


def make_wav_upload(name: str = "lesson.wav", duration_ms: int = 300) -> UploadFile:
    buffer = BytesIO()
    sample_rate = 8000
    frame_count = max(1, round(sample_rate * duration_ms / 1000))
    with wave.open(buffer, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(b"\x00\x00" * frame_count)
    buffer.seek(0)
    return UploadFile(filename=name, file=buffer, headers={"content-type": "audio/wav"})


class FakeTranscriptionProvider:
    name = "fake_transcription"
    model = "fake-whisper"

    def is_configured(self) -> bool:
        return True

    def transcribe(self, audio_path: Path, mime_type: str | None = None) -> TranscriptionResult:
        assert audio_path.exists()
        return TranscriptionResult(
            text="RAG 先检索资料。然后把资料交给大模型。",
            language="zh",
            duration_ms=3000,
            segments=[
                TranscriptionSegmentResult(index=0, start_ms=0, end_ms=1500, text="RAG 先检索资料。", confidence=0.94),
                TranscriptionSegmentResult(index=1, start_ms=1500, end_ms=3000, text="然后把资料交给大模型。", confidence=0.91),
            ],
            provider=self.name,
            model=self.model,
        )


def test_audio_upload_and_transcription_create_timestamped_rag_chunks(db_session, knowledge_space, tmp_path, monkeypatch) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "upload_dir", tmp_path)
    fake_embedding = FakeEmbeddingService()
    fake_vector_store = FakeVectorStore()
    service = MediaService(
        transcription_provider=FakeTranscriptionProvider(),
        embedding_service=fake_embedding,
        vector_store=fake_vector_store,
    )

    source = service.upload_audio(db_session, knowledge_space.id, make_wav_upload())
    assert source.source_type == "audio"
    assert 250 <= (source.duration_ms or 0) <= 350
    assert source.media_assets[0].asset_type == "original_audio"

    source = service.process_audio_transcription(db_session, source.id)
    segments = db_session.query(TranscriptSegment).order_by(TranscriptSegment.segment_index).all()
    chunks = db_session.query(MultimodalChunk).order_by(MultimodalChunk.chunk_index).all()
    assert source.metadata_data["transcription_status"] == "completed"
    assert source.language == "zh"
    assert len(segments) == 2
    assert segments[1].start_ms == 1500
    assert segments[0].confidence == 94
    assert len(chunks) == 2
    assert chunks[1].modality == "audio_transcript"
    assert chunks[1].start_ms == 1500
    assert chunks[1].qdrant_point_id
    assert db_session.query(CitationLocator).count() == 2

    rag = RAGService()
    rag.embedding_service = fake_embedding
    rag.vector_store = fake_vector_store
    rag.llm_service = FakeLLMService()
    response = rag.ask_question(db_session, knowledge_space.id, "RAG 流程是什么？", "normal")
    assert response.retrieval_status == "success"
    assert response.citations[0].source_type == "audio"
    assert response.citations[0].start_ms == 0
    assert response.citations[1].start_ms == 1500


def test_audio_transcription_requires_real_provider(db_session, knowledge_space, tmp_path, monkeypatch) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "upload_dir", tmp_path)
    service = MediaService(transcription_provider=UnconfiguredTranscriptionProvider())
    source = service.upload_audio(db_session, knowledge_space.id, make_wav_upload())

    with pytest.raises(ConfigurationError) as exc_info:
        service.process_audio_transcription(db_session, source.id)

    assert exc_info.value.code == "TRANSCRIPTION_NOT_CONFIGURED"
