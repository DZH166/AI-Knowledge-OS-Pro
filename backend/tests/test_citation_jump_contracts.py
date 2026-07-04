from pathlib import Path

from app.schemas.chat_schema import Citation


ROOT = Path(__file__).resolve().parents[2]


def test_document_image_audio_video_and_code_citation_contracts_are_explicit() -> None:
    document = Citation(
        citation_id="D1",
        document_name="guide.pdf",
        chunk_id=10,
        chunk_index=0,
        content_preview="Document evidence",
        score=0.9,
        document_id=3,
        page_number=2,
        heading_path="Setup",
        source_type="document",
    )
    image = Citation(
        citation_id="I1",
        document_name="screenshot.png",
        chunk_id=11,
        chunk_index=1,
        content_preview="Image OCR evidence",
        score=0.88,
        source_id=4,
        source_type="image",
    )
    audio = Citation(
        citation_id="A1",
        document_name="lesson.mp3",
        chunk_id=12,
        chunk_index=2,
        content_preview="Audio transcript evidence",
        score=0.87,
        source_id=5,
        source_type="audio",
        start_ms=1200,
        end_ms=4200,
    )
    video = Citation(
        citation_id="V1",
        document_name="demo.mp4",
        chunk_id=13,
        chunk_index=3,
        content_preview="Video transcript evidence",
        score=0.86,
        source_id=6,
        source_type="video",
        start_ms=5000,
        end_ms=9000,
    )
    code = Citation(
        citation_id="C1",
        document_name="repo",
        chunk_id=14,
        chunk_index=4,
        content_preview="Code locator evidence",
        score=0.85,
        source_id=7,
        source_type="code_file",
        file_path="backend/app/services/rag_service.py",
        line_start=120,
        line_end=155,
        symbol_name="ask",
    )

    assert document.document_id and (document.page_number or document.heading_path)
    assert image.source_id and image.source_type == "image"
    assert audio.source_id and audio.start_ms is not None and audio.end_ms is not None
    assert video.source_id and video.start_ms is not None and video.end_ms is not None
    assert code.file_path and code.line_start and code.line_end


def test_frontend_citation_panel_contains_document_media_code_and_missing_locator_paths() -> None:
    text = (ROOT / "frontend" / "components" / "CitationPanel.tsx").read_text(encoding="utf-8")
    assert "export function citationHref" in text
    assert "/documents/${citation.document_id}" in text
    assert "/media/sources/${citation.source_id}" in text
    assert "/code?" in text
    assert "无法定位来源" in text
    assert "file_path" in text
    assert "line_start" in text

