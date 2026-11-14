from dataclasses import dataclass
import re

from app.core.config import settings


@dataclass(frozen=True)
class TextChunk:
    chunk_index: int
    content: str
    content_preview: str
    char_count: int
    token_count: int
    section_title: str | None = None
    page_number: int | None = None
    heading_path: str | None = None


class Chunker:
    def __init__(self, chunk_size: int | None = None, overlap: int | None = None) -> None:
        self.chunk_size = settings.chunk_size if chunk_size is None else chunk_size
        self.overlap = settings.chunk_overlap if overlap is None else overlap
        # An overlap greater than or equal to the chunk size makes the
        # sliding window non-advancing (or empty), which used to risk an
        # infinite loop on a hand-edited configuration.
        if self.chunk_size <= 0:
            raise ValueError("chunk_size 必须大于 0。")
        if self.overlap < 0:
            raise ValueError("chunk_overlap 不能为负数。")
        if self.overlap >= self.chunk_size:
            raise ValueError("chunk_overlap 必须小于 chunk_size，否则切片无法前进。")

    def clean_text(self, text: str) -> str:
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]{2,}", " ", text)
        return text.strip()

    def split(self, text: str) -> list[TextChunk]:
        cleaned = self.clean_text(text)
        if not cleaned:
            return []

        chunks: list[TextChunk] = []
        start = 0
        index = 0
        while start < len(cleaned):
            end = min(start + self.chunk_size, len(cleaned))
            if end < len(cleaned):
                boundary = max(cleaned.rfind("\n\n", start, end), cleaned.rfind("。", start, end))
                if boundary > start + int(self.chunk_size * 0.55):
                    end = boundary + 1

            content = cleaned[start:end].strip()
            if content:
                chunks.append(
                    TextChunk(
                        chunk_index=index,
                        content=content,
                        content_preview=self._preview(content),
                        char_count=len(content),
                        token_count=self._estimate_tokens(content),
                        section_title=self._detect_section_title(content),
                    )
                )
                index += 1

            if end >= len(cleaned):
                break
            start = max(0, end - self.overlap)

        return chunks

    def split_markdown(self, text: str) -> list[TextChunk]:
        cleaned = self.clean_text(text)
        if not cleaned:
            return []

        chunks: list[TextChunk] = []
        heading_stack: list[str] = []
        buffer: list[str] = []
        buffer_heading = ""

        def flush() -> None:
            nonlocal buffer, buffer_heading
            content = "\n".join(buffer).strip()
            if not content:
                buffer = []
                return
            for item in self.split(content):
                chunks.append(
                    TextChunk(
                        chunk_index=len(chunks),
                        content=item.content,
                        content_preview=item.content_preview,
                        char_count=item.char_count,
                        token_count=item.token_count,
                        section_title=item.section_title or (heading_stack[-1] if heading_stack else None),
                        heading_path=buffer_heading or None,
                    )
                )
            buffer = []

        for line in cleaned.splitlines():
            match = re.match(r"^(#{1,6})\s+(.+)$", line.strip())
            if match:
                flush()
                level = len(match.group(1))
                title = match.group(2).strip()
                heading_stack = heading_stack[: level - 1]
                heading_stack.append(title)
                buffer_heading = " / ".join(heading_stack)
            buffer.append(line)
        flush()
        return chunks

    def split_pdf_pages(self, pages: list[tuple[int, str]]) -> list[TextChunk]:
        chunks: list[TextChunk] = []
        for page_number, text in pages:
            for item in self.split(text):
                chunks.append(
                    TextChunk(
                        chunk_index=len(chunks),
                        content=item.content,
                        content_preview=item.content_preview,
                        char_count=item.char_count,
                        token_count=item.token_count,
                        section_title=item.section_title,
                        page_number=page_number,
                    )
                )
        return chunks

    @staticmethod
    def _preview(text: str, limit: int = 220) -> str:
        compact = re.sub(r"\s+", " ", text).strip()
        if len(compact) <= limit:
            return compact
        return compact[:limit].rstrip() + "..."

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        ascii_words = re.findall(r"[A-Za-z0-9_]+", text)
        cjk_chars = re.findall(r"[\u4e00-\u9fff]", text)
        return max(1, len(ascii_words) + int(len(cjk_chars) * 0.7))

    @staticmethod
    def _detect_section_title(text: str) -> str | None:
        first_line = next((line.strip() for line in text.splitlines() if line.strip()), "")
        if first_line.startswith("#"):
            return first_line.lstrip("#").strip()[:120] or None
        if len(first_line) <= 80 and first_line.endswith(("：", ":")):
            return first_line.rstrip("：:")
        return None
