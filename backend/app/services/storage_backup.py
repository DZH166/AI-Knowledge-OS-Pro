from __future__ import annotations

import json
import os
import shutil
import sqlite3
import tempfile
import zipfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path, PurePosixPath
from sqlalchemy.engine import make_url

BACKUP_FORMAT = "evidence-os-storage-backup"
BACKUP_VERSION = 1
MANIFEST_NAME = "manifest.json"
DATABASE_PREFIX = "database/"
UPLOAD_PREFIX = "uploads/"


class StorageBackupError(RuntimeError):
    """Raised when a backup or restore cannot be completed safely."""


@dataclass(frozen=True, slots=True)
class BackupEntry:
    path: str
    size: int
    sha256: str


@dataclass(frozen=True, slots=True)
class BackupSummary:
    archive: str
    created_at: str
    database_bytes: int
    upload_files: int
    upload_bytes: int
    manifest_sha256: str


@dataclass(frozen=True, slots=True)
class VerificationResult:
    archive: str
    ok: bool
    created_at: str
    database: BackupEntry
    uploads: tuple[BackupEntry, ...]
    source_upload_dir: str | None = None
    warnings: tuple[str, ...] = field(default_factory=tuple)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sqlite_path_from_url(database_url: str) -> Path:
    url = make_url(database_url)
    if url.get_backend_name() != "sqlite":
        raise StorageBackupError("存储备份目前只支持 SQLite 数据库。")
    database = url.database
    if not database or database == ":memory:":
        raise StorageBackupError("无法备份内存数据库；请使用文件型 SQLite。")
    path = Path(database)
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    return path


def _hash_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _safe_relative(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise StorageBackupError(f"归档内存在不安全路径：{value}")
    return path


def _collect_uploads(upload_dir: Path) -> list[Path]:
    if not upload_dir.exists():
        return []
    if not upload_dir.is_dir():
        raise StorageBackupError(f"上传目录不是文件夹：{upload_dir}")
    files: list[Path] = []
    for root, directories, filenames in os.walk(upload_dir):
        directories[:] = sorted(name for name in directories if name not in {".git", "__pycache__"})
        for name in sorted(filenames):
            files.append(Path(root) / name)
    return files


def _sqlite_integrity(path: Path) -> str:
    connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try:
        rows = connection.execute("PRAGMA integrity_check").fetchall()
    finally:
        connection.close()
    result = ",".join(str(row[0]) for row in rows)
    if result != "ok":
        raise StorageBackupError(f"SQLite integrity_check 失败：{result}")
    return result


def _expected_file_hashes(snapshot: Path, upload_root: Path) -> dict[Path, str]:
    """Map files under the upload root to the hash the database recorded.

    Tables are read directly from the consistent snapshot; a missing historical
    table is treated as no expectation rather than a false backup failure.
    """

    expected: dict[Path, str] = {}
    connection = sqlite3.connect(f"file:{snapshot.as_posix()}?mode=ro", uri=True)
    try:
        for table in ("sources", "documents"):
            try:
                rows = connection.execute(
                    f"select storage_path, content_hash from {table} "
                    "where storage_path is not null and content_hash is not null"
                ).fetchall()
            except sqlite3.OperationalError:
                continue
            for raw_path, content_hash in rows:
                if not raw_path or not content_hash:
                    continue
                value = str(raw_path)
                if value.startswith(("synthetic://", "http://", "https://", "recording://")):
                    continue
                path = Path(value)
                if not path.is_absolute():
                    path = (Path.cwd() / path).resolve()
                try:
                    path.relative_to(upload_root)
                except ValueError:
                    continue
                expected[path] = str(content_hash)
    finally:
        connection.close()
    return expected


def create_backup(
    *,
    database_url: str,
    upload_dir: Path,
    output: Path,
    label: str | None = None,
) -> BackupSummary:
    """Create a consistent SQLite + uploads archive with a hash manifest.

    The SQLite online backup API is used so a running workspace can be copied
    without a torn database file. The archive is verified before this function
    returns.
    """

    database_path = sqlite_path_from_url(database_url)
    if not database_path.is_file():
        raise StorageBackupError(f"数据库文件不存在：{database_path}")
    upload_root = upload_dir.resolve()
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise StorageBackupError(f"备份文件已经存在，拒绝覆盖：{output}")

    created_at = _utc_now()
    with tempfile.TemporaryDirectory(prefix="evidence-backup-") as temp_raw:
        temp = Path(temp_raw)
        snapshot = temp / "knowledge_os.db"
        source = sqlite3.connect(f"file:{database_path.as_posix()}?mode=ro", uri=True)
        try:
            target = sqlite3.connect(snapshot)
            try:
                source.backup(target)
            finally:
                target.close()
        finally:
            source.close()
        _sqlite_integrity(snapshot)
        expected_hashes = _expected_file_hashes(snapshot, upload_root)

        upload_entries: list[BackupEntry] = []
        seen_files: set[Path] = set()
        hash_mismatches: list[str] = []
        staged_uploads = temp / "uploads"
        for file_path in _collect_uploads(upload_root):
            relative = file_path.relative_to(upload_root).as_posix()
            destination = staged_uploads / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file_path, destination)
            digest = _hash_file(destination)
            seen_files.add(file_path.resolve())
            expected = expected_hashes.get(file_path.resolve())
            if expected is not None and expected != digest:
                hash_mismatches.append(f"{file_path}（数据库 {expected[:12]}… / 文件 {digest[:12]}…）")
            upload_entries.append(BackupEntry(path=relative, size=destination.stat().st_size, sha256=digest))

        missing = sorted(str(path) for path in expected_hashes if path not in seen_files)
        if missing:
            raise StorageBackupError(
                "数据库引用的文件不在上传目录或已经缺失：" + "；".join(missing[:3])
            )
        if hash_mismatches:
            raise StorageBackupError(
                "上传文件内容与数据库登记指纹不一致，拒绝生成不一致的备份：" + "；".join(hash_mismatches[:3])
            )

        database_entry = BackupEntry(path="knowledge_os.db", size=snapshot.stat().st_size, sha256=_hash_file(snapshot))
        manifest = {
            "format": BACKUP_FORMAT,
            "version": BACKUP_VERSION,
            "created_at": created_at,
            "label": label,
            "source_upload_dir": str(upload_root),
            "database": {"path": DATABASE_PREFIX + database_entry.path, **{k: getattr(database_entry, k) for k in ("size", "sha256")}},
            "integrity": "ok",
            "uploads": [
                {"path": UPLOAD_PREFIX + entry.path, "size": entry.size, "sha256": entry.sha256}
                for entry in upload_entries
            ],
            "totals": {
                "upload_files": len(upload_entries),
                "upload_bytes": sum(entry.size for entry in upload_entries),
                "database_bytes": database_entry.size,
            },
        }
        manifest_path = temp / MANIFEST_NAME
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        manifest_sha = _hash_file(manifest_path)

        try:
            with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
                archive.write(manifest_path, MANIFEST_NAME)
                archive.write(snapshot, DATABASE_PREFIX + database_entry.path)
                for root, _directories, filenames in os.walk(staged_uploads):
                    for name in sorted(filenames):
                        file_path = Path(root) / name
                        relative = file_path.relative_to(staged_uploads).as_posix()
                        archive.write(file_path, UPLOAD_PREFIX + relative)
        except OSError as exc:
            output.unlink(missing_ok=True)
            raise StorageBackupError(f"无法写入备份归档：{exc}") from exc

    try:
        verification = verify_backup(output)
    except Exception:
        output.unlink(missing_ok=True)
        raise
    return BackupSummary(
        archive=str(output),
        created_at=verification.created_at,
        database_bytes=verification.database.size,
        upload_files=len(verification.uploads),
        upload_bytes=sum(entry.size for entry in verification.uploads),
        manifest_sha256=manifest_sha,
    )


def verify_backup(archive_path: Path) -> VerificationResult:
    archive_path = archive_path.resolve()
    if not archive_path.is_file():
        raise StorageBackupError(f"备份文件不存在：{archive_path}")
    warnings: list[str] = []
    with zipfile.ZipFile(archive_path) as archive:
        names = archive.namelist()
        if MANIFEST_NAME not in names:
            raise StorageBackupError("备份缺少 manifest.json。")
        for name in names:
            if name == MANIFEST_NAME:
                continue
            _safe_relative(name)
        try:
            manifest = json.loads(archive.read(MANIFEST_NAME).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise StorageBackupError(f"manifest.json 无法解析：{exc}") from exc
        if manifest.get("format") != BACKUP_FORMAT or manifest.get("version") != BACKUP_VERSION:
            raise StorageBackupError("备份格式或版本不受支持。")

        database_meta = manifest.get("database")
        if not isinstance(database_meta, dict) or not str(database_meta.get("path", "")).startswith(DATABASE_PREFIX):
            raise StorageBackupError("manifest 缺少数据库条目。")
        database_entry = BackupEntry(
            path=str(database_meta["path"])[len(DATABASE_PREFIX):],
            size=int(database_meta["size"]),
            sha256=str(database_meta["sha256"]),
        )
        _verify_entry(archive, DATABASE_PREFIX + database_entry.path, database_entry)

        uploads: list[BackupEntry] = []
        for item in manifest.get("uploads", []):
            raw_path = str(item.get("path", ""))
            if not raw_path.startswith(UPLOAD_PREFIX):
                raise StorageBackupError(f"manifest 上传条目路径非法：{raw_path}")
            entry = BackupEntry(
                path=raw_path[len(UPLOAD_PREFIX):],
                size=int(item["size"]),
                sha256=str(item["sha256"]),
            )
            _verify_entry(archive, raw_path, entry)
            uploads.append(entry)

        listed = {MANIFEST_NAME, DATABASE_PREFIX + database_entry.path, *(UPLOAD_PREFIX + entry.path for entry in uploads)}
        extra = sorted(set(names) - listed)
        if extra:
            warnings.append(f"归档存在 manifest 未列出的条目：{', '.join(extra[:3])}")

        with tempfile.TemporaryDirectory(prefix="evidence-verify-") as temp_raw:
            snapshot = Path(temp_raw) / "knowledge_os.db"
            with archive.open(DATABASE_PREFIX + database_entry.path) as source, snapshot.open("wb") as target:
                shutil.copyfileobj(source, target)
            _sqlite_integrity(snapshot)

    return VerificationResult(
        archive=str(archive_path),
        ok=True,
        created_at=str(manifest.get("created_at") or ""),
        database=database_entry,
        uploads=tuple(uploads),
        source_upload_dir=str(manifest.get("source_upload_dir") or "") or None,
        warnings=tuple(warnings),
    )


def _verify_entry(archive: zipfile.ZipFile, name: str, entry: BackupEntry) -> None:
    try:
        info = archive.getinfo(name)
    except KeyError as exc:
        raise StorageBackupError(f"归档缺少文件：{name}") from exc
    if info.file_size != entry.size:
        raise StorageBackupError(f"文件大小与 manifest 不一致：{name}")
    digest = sha256()
    with archive.open(name) as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    if digest.hexdigest() != entry.sha256:
        raise StorageBackupError(f"文件指纹与 manifest 不一致：{name}")


def _rewrite_storage_paths(database_path: Path, old_root: str | None, new_root: Path) -> int:
    """Point restored rows at the new upload root instead of the old absolute path.

    Backups store absolute storage paths. Restoring into a different directory
    (or a moved workspace) must not leave every file looking orphaned.
    """

    if not old_root:
        return 0
    old_prefix = os.path.normpath(old_root)
    new_prefix = os.path.normpath(str(new_root))
    if os.path.normcase(old_prefix) == os.path.normcase(new_prefix):
        return 0
    connection = sqlite3.connect(database_path)
    updated = 0
    try:
        for table in ("sources", "documents", "media_assets", "visual_frames"):
            try:
                rows = connection.execute(
                    f"select rowid, storage_path from {table} where storage_path is not null"
                ).fetchall()
            except sqlite3.OperationalError:
                continue
            for rowid, raw in rows:
                raw_path = os.path.normpath(str(raw))
                raw_key = os.path.normcase(raw_path)
                old_key = os.path.normcase(old_prefix)
                if raw_key != old_key and not raw_key.startswith(old_key + os.sep):
                    continue
                suffix = raw_path[len(old_prefix):].lstrip("\\/")
                replacement = os.path.join(new_prefix, suffix) if suffix else new_prefix
                connection.execute(
                    f"update {table} set storage_path=? where rowid=?",
                    (replacement, rowid),
                )
                updated += 1
        connection.commit()
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        connection.close()
    return updated


def restore_backup(
    *,
    archive_path: Path,
    database_url: str,
    upload_dir: Path,
    force: bool = False,
) -> dict[str, str]:
    """Restore a verified archive, keeping the previous state as a sibling backup."""

    verification = verify_backup(archive_path)
    database_path = sqlite_path_from_url(database_url)
    upload_root = upload_dir.resolve()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    previous_database: Path | None = None
    previous_uploads: Path | None = None
    if not force and (database_path.exists() or (upload_root.exists() and any(upload_root.iterdir()))):
        raise StorageBackupError("目标数据库或上传目录非空；使用 force=True 才会先备份并替换。")

    archive_path = archive_path.resolve()
    with tempfile.TemporaryDirectory(prefix="evidence-restore-") as temp_raw:
        staging = Path(temp_raw)
        with zipfile.ZipFile(archive_path) as archive:
            for name in archive.namelist():
                if name == MANIFEST_NAME:
                    continue
                relative = _safe_relative(name)
                destination = staging.joinpath(*relative.parts)
                destination.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(name) as source, destination.open("wb") as target:
                    shutil.copyfileobj(source, target)

        staged_database = staging / DATABASE_PREFIX / verification.database.path
        if not staged_database.is_file():
            raise StorageBackupError("归档解压后缺少数据库文件。")
        _sqlite_integrity(staged_database)

        database_path.parent.mkdir(parents=True, exist_ok=True)
        if database_path.exists():
            previous_database = database_path.with_name(database_path.name + f".before-restore-{stamp}")
            database_path.replace(previous_database)
        for suffix in ("-wal", "-shm"):
            sidecar = Path(str(database_path) + suffix)
            if sidecar.exists():
                sidecar.replace(Path(str(previous_database) + suffix)) if previous_database else sidecar.unlink()
        shutil.copy2(staged_database, database_path)

        if upload_root.exists():
            previous_uploads = upload_root.with_name(upload_root.name + f".before-restore-{stamp}")
            if any(upload_root.iterdir()):
                upload_root.replace(previous_uploads)
            else:
                upload_root.rmdir()
        upload_root.mkdir(parents=True, exist_ok=True)
        staged_uploads = staging / UPLOAD_PREFIX
        if staged_uploads.exists():
            for root, _directories, filenames in os.walk(staged_uploads):
                for name in filenames:
                    source = Path(root) / name
                    relative = source.relative_to(staged_uploads)
                    destination = upload_root / relative
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, destination)

        rewritten_paths = _rewrite_storage_paths(
            database_path, verification.source_upload_dir, upload_root
        )

    return {
        "archive": str(archive_path),
        "database": str(database_path),
        "uploads": str(upload_root),
        "previous_database": str(previous_database) if previous_database else "",
        "previous_uploads": str(previous_uploads) if previous_uploads else "",
        "restored_upload_files": str(len(verification.uploads)),
        "rewritten_storage_paths": str(rewritten_paths),
        "verified_at": verification.created_at,
    }


def summary_dict(summary: BackupSummary | VerificationResult | dict) -> dict:
    if isinstance(summary, (BackupSummary, VerificationResult)):
        return asdict(summary)
    return dict(summary)
