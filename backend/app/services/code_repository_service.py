from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.errors import ConfigurationError, DuplicateDocumentError
from app.models.knowledge_space import KnowledgeSpace
from app.models.source import CitationLocator, MultimodalChunk, Source, SourceRevision
from app.modules.evidence_index import (
    ActivateRevision,
    CancelRevision,
    ChunkDraft,
    GetRevision,
    PointEmbedding,
    RevisionDraft,
    SqlEvidenceIndex,
    StageRevision,
    UpsertRevisionVectors,
    VerifiedPoint,
)
from app.services.embedding_service import EmbeddingService
from app.services.ingestion_service import LegacyVectorStoreEvidenceAdapter
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

        selected_root = Path(local_path).expanduser()
        if self._is_reparse_point(selected_root):
            raise ValueError("本地代码仓库根目录不能是符号链接或目录联接。")
        root = selected_root.resolve()
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
        repository_path = str(root)
        source = db.scalar(
            select(Source)
            .where(
                Source.space_id == space.id,
                Source.source_type == "code_repository",
                Source.storage_path == repository_path,
                Source.status != "deleted",
                Source.retired_at.is_(None),
            )
            .order_by(Source.id)
            .limit(1)
        )
        metadata = {
            "ingestion_mode": "code_repository",
            "repository_name": root.name,
            "github_url": github_url,
            "file_count": len(files),
            "chunk_count": len(chunks),
            "skipped_count": skipped_count,
            "max_files": max_files,
            "supported_extensions": sorted(self.included_extensions),
            "safety_note": "Skipped .env, databases, media, build outputs, dependency directories and caches.",
        }
        if source is None:
            source = Source(
                space_id=space.id,
                source_type="code_repository",
                title=title or root.name,
                original_filename=root.name,
                mime_type="text/x-code-repository",
                file_size=sum(len(file.content.encode("utf-8")) for file in files),
                storage_path=repository_path,
                # Activation publishes the hash atomically with the active
                # revision pointer. A failed first attempt must remain retryable.
                content_hash=None,
                status="uploaded",
                metadata_json=json.dumps(metadata, ensure_ascii=False),
            )
            db.add(source)
        else:
            source.title = title or source.title or root.name
            source.original_filename = root.name
            source.mime_type = "text/x-code-repository"
            source.file_size = sum(len(file.content.encode("utf-8")) for file in files)
            source.metadata_json = json.dumps(metadata, ensure_ascii=False)
        db.flush()

        old_point_ids = [
            point_id
            for point_id in db.scalars(
                select(MultimodalChunk.qdrant_point_id).where(
                    MultimodalChunk.source_id == source.id,
                    MultimodalChunk.revision_id == source.active_revision_id,
                )
            )
            if point_id
        ]
        fingerprint = self.embedding_service.fingerprint()
        vector_adapter = LegacyVectorStoreEvidenceAdapter(self.vector_store)
        evidence_index = SqlEvidenceIndex(db, vector_adapter=vector_adapter)
        command_prefix = f"code-repository:{source.id}:{manifest_hash}:{uuid4().hex}"
        staged_revision_id: int | None = None
        try:
            staged = evidence_index.command(
                StageRevision(
                    command_id=f"{command_prefix}:stage",
                    draft=RevisionDraft(
                        source_id=source.id,
                        content_hash=manifest_hash,
                        index_version=settings.index_version,
                        collection_name=settings.qdrant_collection,
                        chunks=tuple(
                            ChunkDraft(
                                chunk_index=index,
                                modality="code_file",
                                content=(
                                    f"File: {chunk.file_path}\n"
                                    f"Lines: {chunk.line_start}-{chunk.line_end}\n"
                                    f"Language: {chunk.language}\n\n"
                                    f"{chunk.content}"
                                ),
                                search_text=(
                                    f"代码文件 {chunk.file_path} {chunk.symbol_name or ''}\n{chunk.content}"
                                ),
                                locator={
                                    "kind": "code_range",
                                    "source_type": "code_repository",
                                    "source_id": source.id,
                                    "document_name": source.title
                                    or source.original_filename
                                    or f"code-repository-{source.id}",
                                    "file_path": chunk.file_path,
                                    "line_start": chunk.line_start,
                                    "line_end": chunk.line_end,
                                    "symbol_name": chunk.symbol_name,
                                    "language": chunk.language,
                                    "github_url": github_url,
                                },
                            )
                            for index, chunk in enumerate(chunks)
                        ),
                        parser_name="code_repository_service",
                        parser_version="v5-canonical-1",
                        embedding_provider=self.embedding_service.provider.name,
                        embedding_model=self.embedding_service.provider.model,
                        embedding_dimensions=self.embedding_service.provider.dimensions,
                        embedding_fingerprint=fingerprint,
                        metadata={
                            "github_url": github_url,
                            "file_count": len(files),
                            "repository_path": repository_path,
                        },
                    ),
                )
            )
            staged_revision_id = staged.revision_id
            db_chunks = list(
                db.scalars(
                    select(MultimodalChunk)
                    .where(MultimodalChunk.revision_id == staged_revision_id)
                    .order_by(MultimodalChunk.chunk_index, MultimodalChunk.id)
                )
            )
            if len(db_chunks) != len(chunks):
                raise RuntimeError("Canonical code revision did not preserve the scanned chunk cardinality.")
            for model, chunk in zip(db_chunks, chunks, strict=True):
                model.language = chunk.language
                model.raw_payload_json = json.dumps({"language": chunk.language}, ensure_ascii=False)
                db.add(
                    CitationLocator(
                        source_id=source.id,
                        revision_id=staged_revision_id,
                        chunk_id=model.id,
                        locator_json=model.locator_json,
                        display_text=f"{chunk.file_path}:{chunk.line_start}-{chunk.line_end}",
                    )
                )
            db.commit()

            vectors = self.embedding_service.embed_texts([chunk.search_text for chunk in db_chunks])
            evidence_index.command(
                UpsertRevisionVectors(
                    command_id=f"{command_prefix}:upsert",
                    revision_id=staged_revision_id,
                    points=tuple(
                        PointEmbedding(
                            point_id=chunk.qdrant_point_id or "",
                            vector=tuple(float(value) for value in vector),
                        )
                        for chunk, vector in zip(db_chunks, vectors, strict=True)
                    ),
                )
            )
            revision_view = evidence_index.query(GetRevision(revision_id=staged_revision_id))
            evidence_index.command(
                ActivateRevision(
                    command_id=f"{command_prefix}:activate",
                    revision_id=staged_revision_id,
                    verified_points=tuple(
                        VerifiedPoint(point_id=point.point_id, payload_digest=point.payload_digest)
                        for point in revision_view.points
                    ),
                )
            )
        except Exception as exc:
            self._cancel_staged_revision(
                db,
                evidence_index=evidence_index,
                revision_id=staged_revision_id,
                command_prefix=command_prefix,
                reason=f"Code repository ingestion failed: {exc}",
            )
            raise

        self._best_effort_delete_points(
            [
                point_id
                for point_id in old_point_ids
                if point_id not in {chunk.qdrant_point_id for chunk in db_chunks}
            ]
        )
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

    def _cancel_staged_revision(
        self,
        db: Session,
        *,
        evidence_index: SqlEvidenceIndex,
        revision_id: int | None,
        command_prefix: str,
        reason: str,
    ) -> None:
        if revision_id is None:
            return
        revision = db.get(SourceRevision, revision_id)
        if revision is None or revision.status in {"active", "cancelled"}:
            return
        try:
            evidence_index.command(
                CancelRevision(
                    command_id=f"{command_prefix}:cancel",
                    revision_id=revision_id,
                    reason=reason[:1000],
                )
            )
        except Exception:
            # The durable operation/manifest rows let the reconciler finish a
            # compensation that the synchronous writer could not complete.
            db.rollback()

    def _best_effort_delete_points(self, point_ids: list[str]) -> None:
        unique_point_ids = list(dict.fromkeys(point_id for point_id in point_ids if point_id))
        if not unique_point_ids:
            return
        try:
            self.vector_store.delete_points(unique_point_ids)
        except Exception:
            # SQL active pointers already exclude the retired revision. Physical
            # deletion is a recoverable maintenance concern after activation.
            return

    def _scan_files(self, root: Path, *, max_files: int) -> tuple[list[CodeFileSnapshot], int]:
        snapshots: list[CodeFileSnapshot] = []
        skipped_count = 0
        for current_root, dirs, files in os.walk(root):
            current = Path(current_root)
            if not self._is_within_root(current, root):
                dirs[:] = []
                skipped_count += len(files)
                continue
            safe_dirs: list[str] = []
            for name in dirs:
                path = current / name
                if (
                    name in self.excluded_dirs
                    or name.startswith(".codex")
                    or self._is_reparse_point(path)
                    or not self._is_within_root(path, root)
                ):
                    continue
                safe_dirs.append(name)
            dirs[:] = safe_dirs
            for name in sorted(files):
                if len(snapshots) >= max_files:
                    skipped_count += 1
                    continue
                path = Path(current_root) / name
                if self._should_skip_file(path) or not self._is_within_root(path, root):
                    skipped_count += 1
                    continue
                try:
                    if not path.is_file() or path.stat().st_size > self.max_file_bytes:
                        skipped_count += 1
                        continue
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
        if self._is_reparse_point(path) or name in self.excluded_names:
            return True
        if name.startswith(".env"):
            return True
        if suffix in self.excluded_suffixes:
            return True
        if suffix not in self.included_extensions:
            return True
        return any(part in self.excluded_dirs for part in path.parts)

    def _is_reparse_point(self, path: Path) -> bool:
        try:
            mode = path.lstat()
        except FileNotFoundError:
            return False
        except OSError:
            return True
        return stat.S_ISLNK(mode.st_mode) or bool(
            getattr(mode, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        )

    def _is_within_root(self, path: Path, root: Path) -> bool:
        try:
            return path.resolve(strict=True).is_relative_to(root)
        except (OSError, RuntimeError):
            return False

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
