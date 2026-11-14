from __future__ import annotations

import os
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Literal

from sqlalchemy import func, inspect, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.document import Document
from app.models.source import (
    IndexRevision,
    MediaAsset,
    MultimodalChunk,
    Source,
    SourceRevision,
    VisualFrame,
)

Severity = Literal["error", "warning", "info"]

_SYNTHETIC_PREFIXES = ("synthetic://", "http://", "https://", "recording://")
_SAMPLE_LIMIT = 5


@dataclass(frozen=True, slots=True)
class StorageFinding:
    code: str
    severity: Severity
    entity: str
    message: str


@dataclass(frozen=True, slots=True)
class StorageHealthReport:
    ok: bool
    checked_at: str
    database: dict
    files: dict
    evidence: dict
    findings: tuple[StorageFinding, ...] = ()
    metrics: dict[str, int] = field(default_factory=dict)
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["findings"] = [asdict(item) for item in self.findings]
        payload["notes"] = list(self.notes)
        return payload


@dataclass(frozen=True, slots=True)
class _FileRef:
    entity: str
    path: Path
    declared_size: int | None
    expected_hash: str | None


class StorageIntegrityService:
    """Read-only storage audit for the local evidence workspace.

    The service never mutates application data. It validates the SQLite file,
    every referenced upload, and the revision/index bookkeeping that makes an
    evidence claim reproducible after uploads or restarts.
    """

    def check(
        self,
        session: Session,
        *,
        upload_dir: Path | None = None,
        deep_hash: bool = False,
        scan_orphans: bool = True,
        max_orphan_scan: int = 20_000,
    ) -> StorageHealthReport:
        findings: list[StorageFinding] = []
        notes: list[str] = []
        upload_root = (upload_dir or settings.upload_dir).resolve()

        database, db_findings = self._database_checks(session)
        findings.extend(db_findings)
        if database.get("status") == "unreadable":
            errors = sum(1 for item in findings if item.severity == "error")
            return StorageHealthReport(
                ok=False,
                checked_at=datetime.now(timezone.utc).isoformat(),
                database=database,
                files={"status": "skipped"},
                evidence={"status": "skipped"},
                findings=tuple(findings),
                metrics={"findings": len(findings), "errors": errors, "warnings": 0},
                notes=("数据库不可读，已跳过文件与证据台账检查。先修复数据库或从备份恢复。",),
            )

        required_tables = {
            "sources",
            "documents",
            "source_revisions",
            "multimodal_chunks",
            "index_revisions",
            "media_assets",
            "visual_frames",
        }
        try:
            tables = set(inspect(session.get_bind()).get_table_names())
        except Exception:
            tables = set()
        missing_tables = sorted(required_tables - tables)
        if missing_tables:
            findings.append(StorageFinding(
                code="database_schema_incomplete",
                severity="error",
                entity="database",
                message="数据库缺少必需表：" + "、".join(missing_tables[:6]),
            ))
            errors = sum(1 for item in findings if item.severity == "error")
            return StorageHealthReport(
                ok=False,
                checked_at=datetime.now(timezone.utc).isoformat(),
                database=database,
                files={"status": "skipped"},
                evidence={"status": "skipped"},
                findings=tuple(findings),
                metrics={"findings": len(findings), "errors": errors, "warnings": 0},
                notes=("数据库结构不完整，已跳过文件与证据台账检查。请先执行 alembic upgrade head。",),
            )

        refs, reference_findings = self._file_references(session)
        findings.extend(reference_findings)

        missing = 0
        size_mismatch = 0
        hashed = 0
        seen_paths: set[str] = set()
        referenced_real: set[str] = set()
        for ref in refs:
            key = str(ref.path)
            if key in seen_paths:
                continue
            seen_paths.add(key)
            referenced_real.add(key)
            if not ref.path.exists() or not ref.path.is_file():
                missing += 1
                findings.append(StorageFinding(
                    code="file_missing",
                    severity="error",
                    entity=ref.entity,
                    message=f"引用的文件不存在：{ref.path}",
                ))
                continue
            try:
                actual_size = ref.path.stat().st_size
            except OSError as exc:
                findings.append(StorageFinding(
                    code="file_unreadable",
                    severity="error",
                    entity=ref.entity,
                    message=f"无法读取文件大小：{ref.path}（{exc.__class__.__name__}）",
                ))
                continue
            if ref.declared_size is not None and ref.declared_size >= 0 and actual_size != ref.declared_size:
                size_mismatch += 1
                findings.append(StorageFinding(
                    code="file_size_mismatch",
                    severity="warning",
                    entity=ref.entity,
                    message=f"声明大小 {ref.declared_size} 字节，实际 {actual_size} 字节：{ref.path}",
                ))
            if deep_hash and ref.expected_hash:
                hashed += 1
                actual_hash = self._hash_file(ref.path)
                if actual_hash != ref.expected_hash:
                    findings.append(StorageFinding(
                        code="file_hash_mismatch",
                        severity="error",
                        entity=ref.entity,
                        message=f"内容指纹不一致：{ref.path}",
                    ))

        orphan_count, orphan_findings = (0, [])
        if scan_orphans:
            orphan_count, orphan_findings = self._scan_orphan_files(upload_root, referenced_real, max_orphan_scan)
            findings.extend(orphan_findings)

        evidence, evidence_findings, evidence_metrics = self._evidence_checks(session)
        findings.extend(evidence_findings)

        errors = sum(1 for item in findings if item.severity == "error")
        warnings = sum(1 for item in findings if item.severity == "warning")
        if errors:
            notes.append("存在阻断性存储问题：先修复后再继续写入或索引，避免产生无法回放的证据。")
        if deep_hash:
            notes.append(f"已核对 {hashed} 个内容指纹；未开启时仅检查文件存在性与大小。")
        else:
            notes.append("默认检查文件存在性与声明大小；使用 deep_hash 可核对内容指纹。")
        if not scan_orphans:
            notes.append("本次跳过了未被引用的上传文件扫描。")

        files = {
            "upload_dir": str(upload_root),
            "referenced": len(seen_paths),
            "missing": missing,
            "size_mismatch": size_mismatch,
            "orphans": orphan_count,
            "hashed": hashed,
        }
        metrics = {
            "findings": len(findings),
            "errors": errors,
            "warnings": warnings,
            **evidence_metrics,
            "referenced_files": len(seen_paths),
            "orphan_files": orphan_count,
        }
        findings_sorted = tuple(sorted(findings, key=lambda item: (item.severity != "error", item.code, item.entity)))
        return StorageHealthReport(
            ok=errors == 0,
            checked_at=datetime.now(timezone.utc).isoformat(),
            database=database,
            files=files,
            evidence=evidence,
            findings=findings_sorted,
            metrics=metrics,
            notes=tuple(notes),
        )

    def _database_checks(self, session: Session) -> tuple[dict, list[StorageFinding]]:
        bind = session.get_bind()
        dialect = bind.dialect.name if bind is not None else "unknown"
        info: dict = {"dialect": dialect, "status": "checked"}
        findings: list[StorageFinding] = []
        if dialect != "sqlite":
            info["status"] = "not_applicable"
            findings.append(StorageFinding(
                code="database_dialect_skipped",
                severity="info",
                entity="database",
                message=f"当前数据库方言 {dialect} 不执行 SQLite 文件级检查。",
            ))
            return info, findings

        try:
            connection = session.connection()
            integrity_rows = [row[0] for row in connection.exec_driver_sql("PRAGMA integrity_check").fetchall()]
        except Exception as exc:
            info["status"] = "unreadable"
            findings.append(StorageFinding(
                code="database_unreadable",
                severity="error",
                entity="database",
                message=f"无法执行 SQLite 完整性检查：{exc.__class__.__name__}",
            ))
            return info, findings
        info["integrity"] = "ok" if integrity_rows == ["ok"] else integrity_rows[:3]
        if integrity_rows != ["ok"]:
            findings.append(StorageFinding(
                code="database_integrity_failed",
                severity="error",
                entity="database",
                message=f"SQLite integrity_check 返回异常：{info['integrity']}",
            ))
        try:
            fk_rows = connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
        except Exception as exc:
            findings.append(StorageFinding(
                code="database_foreign_key_check_failed",
                severity="error",
                entity="database",
                message=f"无法执行外键检查：{exc.__class__.__name__}",
            ))
            fk_rows = []
        info["foreign_key_violations"] = len(fk_rows)
        if fk_rows:
            findings.append(StorageFinding(
                code="database_foreign_key_violation",
                severity="error",
                entity="database",
                message=f"检测到 {len(fk_rows)} 条外键不一致记录。",
            ))
        try:
            journal_mode = str(connection.exec_driver_sql("PRAGMA journal_mode").scalar() or "").lower()
        except Exception:
            journal_mode = ""
        info["journal_mode"] = journal_mode
        if journal_mode and journal_mode not in {"wal", "memory"}:
            findings.append(StorageFinding(
                code="database_journal_mode",
                severity="warning",
                entity="database",
                message=f"当前 journal_mode={journal_mode}；并发写入时建议启用 WAL。",
            ))
        try:
            page_count = int(connection.exec_driver_sql("PRAGMA page_count").scalar() or 0)
            page_size = int(connection.exec_driver_sql("PRAGMA page_size").scalar() or 0)
            freelist = int(connection.exec_driver_sql("PRAGMA freelist_count").scalar() or 0)
            info["bytes"] = page_count * page_size
            info["free_pages"] = freelist
        except Exception:
            pass

        if dialect == "sqlite":
            file_path = bind.url.database
            if file_path and file_path != ":memory:":
                path = Path(file_path)
                if not path.is_absolute():
                    path = (Path(settings.project_root) / path).resolve()
                info["path"] = str(path)
                info["file_exists"] = path.exists()
                if path.exists():
                    info["file_bytes"] = path.stat().st_size
                    try:
                        usage = shutil.disk_usage(path.parent)
                    except OSError:
                        usage = None
                    if usage is not None:
                        info["disk_free_bytes"] = usage.free
        return info, findings

    def _file_references(self, session: Session) -> tuple[list[_FileRef], list[StorageFinding]]:
        findings: list[StorageFinding] = []
        refs: list[_FileRef] = []

        def add(entity: str, raw: str | None, size: int | None, expected_hash: str | None = None) -> None:
            if not raw or raw.startswith(_SYNTHETIC_PREFIXES):
                return
            path = Path(raw)
            if not path.is_absolute():
                path = (Path(settings.project_root) / path).resolve()
            if ".." in path.parts:
                findings.append(StorageFinding(
                    code="file_path_traversal",
                    severity="error",
                    entity=entity,
                    message=f"存储路径包含上级目录引用：{raw}",
                ))
                return
            refs.append(_FileRef(entity=entity, path=path, declared_size=size, expected_hash=expected_hash))

        for row in session.execute(select(Source)).scalars():
            add(f"source:{row.id}", row.storage_path, row.file_size, row.content_hash)
        for row in session.execute(select(Document)).scalars():
            add(f"document:{row.id}", row.storage_path, row.file_size, row.content_hash)
        for row in session.execute(select(MediaAsset)).scalars():
            add(f"media_asset:{row.id}", row.storage_path, row.file_size, None)
        for row in session.execute(select(VisualFrame)).scalars():
            add(f"visual_frame:{row.id}", row.storage_path, None, None)
        return refs, findings

    def _scan_orphan_files(
        self,
        upload_root: Path,
        referenced: set[str],
        max_files: int,
    ) -> tuple[int, list[StorageFinding]]:
        if not upload_root.exists() or not upload_root.is_dir():
            return 0, [StorageFinding(
                code="upload_dir_missing",
                severity="warning",
                entity="files",
                message=f"上传目录不存在：{upload_root}",
            )]
        scanned = 0
        orphan_samples: list[str] = []
        orphan_count = 0
        for root, directories, filenames in os.walk(upload_root):
            directories[:] = [name for name in directories if name not in {"__pycache__", ".git"}]
            for name in filenames:
                scanned += 1
                if scanned > max_files:
                    return orphan_count, [StorageFinding(
                        code="orphan_scan_truncated",
                        severity="info",
                        entity="files",
                        message=f"上传目录文件超过 {max_files} 个，已停止扫描未引用文件。",
                    )]
                path = str((Path(root) / name).resolve())
                if path not in referenced:
                    orphan_count += 1
                    if len(orphan_samples) < _SAMPLE_LIMIT:
                        orphan_samples.append(path)
        if orphan_count:
            return orphan_count, [StorageFinding(
                code="unreferenced_files",
                severity="warning",
                entity="files",
                message=f"上传目录中有 {orphan_count} 个未被数据库引用的文件；示例：{', '.join(orphan_samples)}",
            )]
        return 0, []

    def _evidence_checks(self, session: Session) -> tuple[dict, list[StorageFinding], dict[str, int]]:
        findings: list[StorageFinding] = []
        counts = {
            "sources": int(session.execute(select(func.count()).select_from(Source)).scalar_one()),
            "revisions": int(session.execute(select(func.count()).select_from(SourceRevision)).scalar_one()),
            "chunks": int(session.execute(select(func.count()).select_from(MultimodalChunk)).scalar_one()),
            "index_revisions": int(session.execute(select(func.count()).select_from(IndexRevision)).scalar_one()),
        }
        active_sources = int(session.execute(
            select(func.count()).select_from(Source).where(Source.active_revision_id.is_not(None))
        ).scalar_one())
        counts["active_sources"] = active_sources
        info = {"status": "checked", "active_sources": active_sources}

        active_by_source: dict[int, int] = {}
        for source in session.execute(select(Source)).scalars():
            if source.active_revision_id is None:
                continue
            active_by_source[source.id] = source.active_revision_id
            revision = session.get(SourceRevision, source.active_revision_id)
            if revision is None:
                findings.append(StorageFinding(
                    code="active_revision_missing",
                    severity="error",
                    entity=f"source:{source.id}",
                    message=f"active_revision_id={source.active_revision_id} 指向不存在的版本。",
                ))
                continue
            if revision.source_id != source.id:
                findings.append(StorageFinding(
                    code="active_revision_source_mismatch",
                    severity="error",
                    entity=f"source:{source.id}",
                    message=f"活动版本 {revision.id} 属于 source:{revision.source_id}，与当前来源不一致。",
                ))
            if revision.status != "active":
                findings.append(StorageFinding(
                    code="active_revision_not_active",
                    severity="error",
                    entity=f"source:{source.id}",
                    message=f"版本 {revision.id} 的状态为 {revision.status}，但被标记为 active_revision_id。",
                ))
            chunk_count = int(session.execute(
                select(func.count()).select_from(MultimodalChunk).where(MultimodalChunk.revision_id == revision.id)
            ).scalar_one())
            if chunk_count != revision.chunk_count:
                findings.append(StorageFinding(
                    code="revision_chunk_count_mismatch",
                    severity="warning",
                    entity=f"revision:{revision.id}",
                    message=f"版本声明 {revision.chunk_count} 个片段，实际 {chunk_count} 个。",
                ))
            if revision.vector_count > chunk_count:
                findings.append(StorageFinding(
                    code="revision_vector_count_exceeds_chunks",
                    severity="warning",
                    entity=f"revision:{revision.id}",
                    message=f"版本声明 {revision.vector_count} 条向量，但只有 {chunk_count} 个片段。",
                ))
            if source.active_index_revision_id is not None:
                index_revision = session.get(IndexRevision, source.active_index_revision_id)
                if index_revision is None:
                    findings.append(StorageFinding(
                        code="active_index_revision_missing",
                        severity="warning",
                        entity=f"source:{source.id}",
                        message=f"active_index_revision_id={source.active_index_revision_id} 指向不存在的索引版本。",
                    ))
                elif index_revision.status != "active":
                    findings.append(StorageFinding(
                        code="active_index_revision_not_active",
                        severity="warning",
                        entity=f"source:{source.id}",
                        message=f"索引版本 {index_revision.id} 的状态为 {index_revision.status}。",
                    ))
                elif index_revision.revision_id != revision.id or index_revision.source_id != source.id:
                    findings.append(StorageFinding(
                        code="active_index_revision_mismatch",
                        severity="error",
                        entity=f"source:{source.id}",
                        message=(
                            f"索引版本 {index_revision.id} 指向 revision {index_revision.revision_id}"
                            f" / source {index_revision.source_id}，与当前活动版本不一致。"
                        ),
                    ))

        duplicate_active = session.execute(
            select(SourceRevision.source_id, func.count())
            .where(SourceRevision.status == "active")
            .group_by(SourceRevision.source_id)
            .having(func.count() > 1)
        ).all()
        for source_id, active_count in duplicate_active:
            findings.append(StorageFinding(
                code="multiple_active_revisions",
                severity="error",
                entity=f"source:{source_id}",
                message=f"来源存在 {active_count} 个 active 版本，违反不可变证据前提。",
            ))

        known_index_ids = set(session.execute(select(IndexRevision.id)).scalars())
        dangling_index = sum(
            1
            for source in session.execute(select(Source)).scalars()
            if source.active_index_revision_id is not None
            and source.active_index_revision_id not in known_index_ids
        )
        if dangling_index:
            findings.append(StorageFinding(
                code="dangling_index_references",
                severity="warning",
                entity="sources",
                message=f"{dangling_index} 个来源的活动索引版本无法解析。",
            ))
        info.update({
            "active_index_sources": int(session.execute(
                select(func.count()).select_from(Source).where(Source.active_index_revision_id.is_not(None))
            ).scalar_one()),
            "duplicate_active_sources": len(duplicate_active),
        })
        return info, findings, counts

    @staticmethod
    def _hash_file(path: Path) -> str:
        digest = sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()


storage_integrity_service = StorageIntegrityService()
