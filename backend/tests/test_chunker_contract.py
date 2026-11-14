from __future__ import annotations

import pytest

from app.services.chunker import Chunker


def test_chunker_rejects_non_advancing_overlap() -> None:
    with pytest.raises(ValueError, match="chunk_overlap 必须小于 chunk_size"):
        Chunker(chunk_size=100, overlap=100)
    with pytest.raises(ValueError, match="chunk_overlap 必须小于 chunk_size"):
        Chunker(chunk_size=100, overlap=140)


def test_chunker_rejects_invalid_sizes() -> None:
    with pytest.raises(ValueError, match="chunk_size 必须大于 0"):
        Chunker(chunk_size=0, overlap=0)
    with pytest.raises(ValueError, match="chunk_overlap 不能为负数"):
        Chunker(chunk_size=100, overlap=-1)


def test_chunks_advance_and_stay_within_configured_size() -> None:
    text = ("第一段证据说明版本与引用身份。" * 30) + "\n\n" + ("Second paragraph adds provenance context. " * 30)
    chunks = Chunker(chunk_size=120, overlap=20).split(text)

    assert len(chunks) > 2
    assert all(0 < chunk.char_count <= 120 for chunk in chunks)
    assert [chunk.chunk_index for chunk in chunks] == list(range(len(chunks)))
    assert chunks[0].content.startswith("第一段证据")


def test_markdown_headings_populate_heading_path_without_dropping_content() -> None:
    markdown = "# 一级标题\n\n正文一。\n\n## 二级标题\n\n正文二，包含关键事实。\n"

    chunks = Chunker(chunk_size=200, overlap=20).split_markdown(markdown)

    assert chunks
    assert any("一级标题" in (chunk.heading_path or "") for chunk in chunks)
    assert any("二级标题" in (chunk.heading_path or "") for chunk in chunks)
    assert any("关键事实" in chunk.content for chunk in chunks)
