from dataclasses import dataclass, field
from pathlib import Path

from pypdf import PdfReader


@dataclass(frozen=True)
class ParsedDocument:
    text: str
    summary: str
    page_count: int | None = None
    pages: list[tuple[int, str]] = field(default_factory=list)
    document_type: str = "text"


class DocumentParser:
    supported_extensions = {".txt", ".md", ".pdf"}

    def parse(self, file_path: Path) -> ParsedDocument:
        suffix = file_path.suffix.lower()
        if suffix not in self.supported_extensions:
            raise ValueError("V2 当前仅支持 txt、md、pdf 文件。")

        if suffix in {".txt", ".md"}:
            text = self._read_text(file_path)
            return ParsedDocument(
                text=text,
                summary=self._summary(text),
                page_count=None,
                document_type="markdown" if suffix == ".md" else "text",
            )

        text, page_count, pages = self._read_pdf(file_path)
        return ParsedDocument(text=text, summary=self._summary(text), page_count=page_count, pages=pages, document_type="pdf")

    def _read_text(self, file_path: Path) -> str:
        for encoding in ("utf-8", "utf-8-sig", "gb18030"):
            try:
                return file_path.read_text(encoding=encoding)
            except UnicodeDecodeError:
                continue
        return file_path.read_text(encoding="utf-8", errors="ignore")

    def _read_pdf(self, file_path: Path) -> tuple[str, int, list[tuple[int, str]]]:
        reader = PdfReader(str(file_path))
        pages: list[str] = []
        page_items: list[tuple[int, str]] = []
        for index, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            if text.strip():
                cleaned = text.strip()
                page_items.append((index, cleaned))
                pages.append(f"[Page {index}]\n{cleaned}")
        return "\n\n".join(pages), len(reader.pages), page_items

    def _summary(self, text: str, limit: int = 260) -> str:
        compact = " ".join(text.split())
        if not compact:
            return "未解析到有效文本内容。"
        if len(compact) <= limit:
            return compact
        return compact[:limit].rstrip() + "..."
