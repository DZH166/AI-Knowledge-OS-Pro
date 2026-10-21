from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.errors import ConfigurationError, DuplicateDocumentError
from app.models.knowledge_space import KnowledgeSpace
from app.models.source import CitationLocator, IndexRevision, MultimodalChunk, Source, SourceRevision
from app.services.embedding_service import EmbeddingService
from app.services.vector_store import VectorStore


@dataclass(frozen=True)
class CodeFileSnapshot:
    relative_path: str
    language: str
    content: str
    line_count: int
    sha256: str


@dataclass(frozen=True)
class CodeChunkSnapshot:
    file_path: str
    language: str
    line_start: int
    line_end: int
    symbol_name: str | None
    content: str


class CodeRepositoryService:
    included_extensions = {
        ".py",
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".md",
        ".json",
        ".toml",
        ".yaml",
        ".yml",
        ".ini",
        ".css",
        ".html",
        ".sql",
        ".sh",
        ".ps1",
        ".txt",
    }
    excluded_dirs = {
        ".git",
        ".hg",
        ".svn",
        ".next",
        ".pytest_cache",
        ".ruff_cache",
        ".mypy_cache",
        ".venv",
        "venv",
        "env",
        "__pycache__",
        "node_modules",
        "dist",
        "build",
        "coverage",
        "uploads",
        "logs",
        "releases",
        "qdrant_storage",
        "redis_data",
        "media_cache",
        "transcripts_cache",
        "keyframes_cache",
    }
    excluded_names = {
        ".env",
        ".env.local",
        ".env.production",
        ".env.development",
        "knowledge_os.db",
        "demo_showcase.db",
    }
    excluded_suffixes = {
        ".db",
        ".sqlite",
        ".sqlite3",
        ".pyc",
        ".pyo",
        ".zip",
        ".tar",
        ".gz",
        ".7z",
        ".rar",
        ".png",
        ".jpg",
        ".jpeg",
        ".webp",
        ".gif",
        ".mp3",
        ".wav",
        ".m4a",
        ".mp4",
        ".mov",
        ".pdf",
    }
    max_file_bytes = 120_000
    max_chunk_lines = 80

    def __init__(
        self,
        embedding_service: EmbeddingService | None = None,
        vector_store: VectorStore | None = None,
    ) -> None:
        self.embedding_service = embedding_service or EmbeddingService()
        self.vector_store = vector_store or VectorStore()

    def ingest_local_repository(
        self,
        db: Session,
        *,
        space_id: int,
        local_path: str,
        title: str | None = None,
        github_url: str | None = None,
        max_files: int = 80,
    ) -> tuple[Source, int, int]:
        space = db.get(KnowledgeSpace, space_id)
        if space is None:
            raise ValueError("知识库不存在。")
        if not self.embedding_service.is_configured():
            raise ConfigurationError(
                "代码仓库接入需要真实 Embedding provider。请配置 EMBEDDING_API_KEY 或开启明确的 Demo provider。",
                code="EMBEDDING_NOT_CONFIGURED",
            )

        root = Path(local_path).expanduser().resolve()
        if not root.exists() or not root.is_dir():
            raise ValueError("本地代码仓库路径不存在或不是目录。")

        files, skipped_count = self._scan_files(root, max_files=max_files)
        if not files:
            raise ValueError("没有找到可接入的安全代码文件。请确认目录包含受支持的文本代码文件。")
        manifest_hash = self._manifest_hash(files)
        duplicate = db.scalar(
            select(Source).where(
                Source.space_id == space_id,
                Source.source_type == "code_repository",
                Source.content_hash == manifest_hash,
                Source.status != "deleted",
            )
        )
        if duplicate is not None:
            raise DuplicateDocumentError(
                "同一知识库中已经存在内容相同的代码仓库快照。",
                details={"source_id": duplicate.id, "title": duplicate.title},
            )

        chunks = self._split_files(files)
        source = Source(
            space_id=space.id,
            source_type="code_repository",
            title=title or root.name,
            original_filename=root.name,
            mime_type="text/x-code-repository",
            file_size=sum(len(file.content.encode("utf-8")) for file in files),
            storage_path=str(root),
            content_hash=manifest_hash,
            status="ready",
            metadata_json=json.dumps(
                {
                    "ingestion_mode": "code_repository",
                    "repository_name": root.name,
                    "github_url": github_url,
                    "file_count": len(files),
                    "chunk_count": len(chunks),
                    "skipped_count": skipped_count,
                    "max_files": max_files,
                    "supported_extensions": sorted(self.included_extensions),
                    "safety_note": "Skipped .env, databases, media, build outputs, dependency directories and caches.",
                },
                ensure_ascii=False,
            ),
        )
        db.add(source)
        db.flush()

        revision = SourceRevision(
            source_id=source.id,
            revision_number=1,
            status="active",
            parser_name="code_repository_service",
            parser_version="v4.0-lightweight",
            content_hash=manifest_hash,
            chunk_count=len(chunks),
            vector_count=0,
            validation_status="passed",
            metadata_json=json.dumps({"github_url": github_url, "file_count": len(files)}, ensure_ascii=False),
            activated_at=datetime.now(timezone.utc),
        )
        db.add(revision)
        db.flush()

        db_chunks: list[MultimodalChunk] = []
        for index, chunk in enumerate(chunks):
            locator = {
                "source_type": "code_repository",
                "source_id": source.id,
                "file_path": chunk.file_path,
                "line_start": chunk.line_start,
                "line_end": chunk.line_end,
                "symbol_name": chunk.symbol_name,
                "github_url": github_url,
            }
            content_text = (
                f"File: {chunk.file_path}\n"
                f"Lines: {chunk.line_start}-{chunk.line_end}\n"
                f"Language: {chunk.language}\n\n"
                f"{chunk.content}"
            )
            model = MultimodalChunk(
                source_id=source.id,
                revision_id=revision.id,
                chunk_index=index,
                modality="code_file",
                source_type="code_repository",
                content_text=content_text,
                search_text=f"代码文件 {chunk.file_path} {chunk.symbol_name or ''}\n{chunk.content}",
                raw_payload_json=json.dumps({"language": chunk.language}, ensure_ascii=False),
                locator_json=json.dumps(locator, ensure_ascii=False),
                language=chunk.language,
                status="active",
            )
            db.add(model)
            db.flush()
            db.add(
                CitationLocator(
                    source_id=source.id,
                    revision_id=revision.id,
                    chunk_id=model.id,
                    locator_json=model.locator_json,
                    display_text=f"{chunk.file_path}:{chunk.line_start}-{chunk.line_end}",
                )
            )
            db_chunks.append(model)

        vectors = self.embedding_service.embed_texts([chunk.search_text for chunk in db_chunks])
        point_ids = [f"code-{uuid4()}" for _ in db_chunks]
        fingerprint = self.embedding_service.fingerprint()
        payloads = [
            {
                "space_id": source.space_id,
                "source_id": source.id,
                "source_type": "code_repository",
                "document_name": source.title or source.original_filename or f"code-repository-{source.id}",
                "chunk_id": chunk.id,
                "chunk_index": chunk.chunk_index,
                "modality": chunk.modality,
                "content": chunk.content_text,
                "content_preview": self._preview(chunk.content_text),
                "locator": self._json_dict(chunk.locator_json),
                "file_path": self._json_dict(chunk.locator_json).get("file_path"),
                "line_start": self._json_dict(chunk.locator_json).get("line_start"),
                "line_end": self._json_dict(chunk.locator_json).get("line_end"),
                "symbol_name": self._json_dict(chunk.locator_json).get("symbol_name"),
                "embedding_fingerprint": fingerprint,
                "index_version": settings.index_version,
            }
            for chunk in db_chunks
        ]
        self.vector_store.upsert_chunks(point_ids=point_ids, vectors=vectors, payloads=payloads)
        for chunk, point_id in zip(db_chunks, point_ids, strict=True):
            chunk.qdrant_point_id = point_id

        index_revision = IndexRevision(
            source_id=source.id,
            revision_id=revision.id,
            status="active",
            index_version=settings.index_version,
            embedding_provider=self.embedding_service.provider.name,
            embedding_model=self.embedding_service.provider.model,
            embedding_dimensions=self.embedding_service.provider.dimensions,
            embedding_fingerprint=fingerprint,
            qdrant_collection=settings.qdrant_collection,
            point_count=len(db_chunks),
            validation_status="passed",
            activated_at=datetime.now(timezone.utc),
        )
        db.add(index_revision)
        revision.vector_count = len(db_chunks)
        source.active_revision_id = revision.id
        source.latest_revision_id = revision.id
        db.commit()
        db.refresh(source)
        return self.get_source(db, source.id), len(files), skipped_count

    def list_repositories(self, db: Session, space_id: int | None = None) -> list[Source]:
        stmt = (
            select(Source)
            .where(Source.source_type == "code_repository")
            .options(selectinload(Source.revisions).selectinload(SourceRevision.chunks))
            .order_by(Source.created_at.desc())
        )
        if space_id is not None:
            stmt = stmt.where(Source.space_id == space_id)
        return list(db.scalars(stmt).all())

    def get_source(self, db: Session, source_id: int) -> Source:
        source = db.scalar(
            select(Source)
            .where(Source.id == source_id, Source.source_type == "code_repository")
            .options(selectinload(Source.revisions).selectinload(SourceRevision.chunks))
        )
        if source is None:
            raise ValueError("代码仓库来源不存在。")
        return source

    def _scan_files(self, root: Path, *, max_files: int) -> tuple[list[CodeFileSnapshot], int]:
        snapshots: list[CodeFileSnapshot] = []
        skipped_count = 0
        for current_root, dirs, files in os.walk(root):
            dirs[:] = [name for name in dirs if name not in self.excluded_dirs and not name.startswith(".codex")]
            for name in sorted(files):
                if len(snapshots) >= max_files:
                    skipped_count += 1
                    continue
                path = Path(current_root) / name
                if self._should_skip_file(path):
                    skipped_count += 1
                    continue
                try:
                    raw = path.read_bytes()
                except OSError:
                    skipped_count += 1
                    continue
                if b"\x00" in raw or len(raw) > self.max_file_bytes:
                    skipped_count += 1
                    continue
                try:
                    content = raw.decode("utf-8")
                except UnicodeDecodeError:
                    skipped_count += 1
                    continue
                relative = path.relative_to(root).as_posix()
                snapshots.append(
                    CodeFileSnapshot(
                        relative_path=relative,
                        language=self._language(path),
                        content=content,
                        line_count=len(content.splitlines()) or 1,
                        sha256=hashlib.sha256(raw).hexdigest(),
                    )
                )
        snapshots.sort(key=lambda item: item.relative_path)
        return snapshots, skipped_count

    def _should_skip_file(self, path: Path) -> bool:
        name = path.name.lower()
        suffix = path.suffix.lower()
        if path.is_symlink() or name in self.excluded_names:
            return True
        if name.startswith(".env"):
            return True
        if suffix in self.excluded_suffixes:
            return True
        if suffix not in self.included_extensions:
            return True
        return any(part in self.excluded_dirs for part in path.parts)

    def _split_files(self, files: list[CodeFileSnapshot]) -> list[CodeChunkSnapshot]:
        chunks: list[CodeChunkSnapshot] = []
        for file in files:
            lines = file.content.splitlines()
            if not lines:
                lines = [""]
            for start in range(0, len(lines), self.max_chunk_lines):
                segment = lines[start : start + self.max_chunk_lines]
                text = "\n".join(segment).strip()
                if not text:
                    continue
                line_start = start + 1
                line_end = start + len(segment)
                chunks.append(
                    CodeChunkSnapshot(
                        file_path=file.relative_path,
                        language=file.language,
                        line_start=line_start,
                        line_end=line_end,
                        symbol_name=self._symbol_name(text),
                        content=text,
                    )
                )
        return chunks

    def _manifest_hash(self, files: list[CodeFileSnapshot]) -> str:
        hasher = hashlib.sha256()
        for file in files:
            hasher.update(file.relative_path.encode("utf-8"))
            hasher.update(file.sha256.encode("ascii"))
        return hasher.hexdigest()

    def _language(self, path: Path) -> str:
        mapping = {
            ".py": "python",
            ".ts": "typescript",
            ".tsx": "typescript-react",
            ".js": "javascript",
            ".jsx": "javascript-react",
            ".md": "markdown",
            ".json": "json",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".toml": "toml",
            ".css": "css",
            ".html": "html",
            ".sql": "sql",
            ".sh": "shell",
            ".ps1": "powershell",
        }
        return mapping.get(path.suffix.lower(), "text")

    def _symbol_name(self, text: str) -> str | None:
        patterns = [
            r"^\s*(?:async\s+)?def\s+([A-Za-z_][\w]*)",
            r"^\s*class\s+([A-Za-z_][\w]*)",
            r"^\s*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)",
            r"^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.MULTILINE)
            if match:
                return match.group(1)
        return None

    def _preview(self, text: str) -> str:
        return re.sub(r"\s+", " ", text).strip()[:220]

    def _json_dict(self, raw: str | None) -> dict:
        try:
            value = json.loads(raw or "{}")
        except json.JSONDecodeError:
            return {}
        return value if isinstance(value, dict) else {}


code_repository_service = CodeRepositoryService()
