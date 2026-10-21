from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile
from typing import BinaryIO, Iterable, Iterator
import zipfile


ROOT = Path(__file__).resolve().parents[1]
RELEASES = ROOT / "releases"
RELEASE_MANIFEST = "RELEASE-MANIFEST.json"
RELEASE_MANIFEST_DIGEST = "RELEASE-MANIFEST.sha256"
RELEASE_MANIFEST_SCHEMA = "ai-knowledge-os.release-manifest.v1"
HASH_CHUNK_SIZE = 1024 * 1024
WINDOWS_REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)

EXCLUDED_DIRS = {
    ".git",
    ".agents",
    ".codex",
    ".next",
    ".pytest_cache",
    ".pytest_tmp",
    ".mypy_cache",
    ".ruff_cache",
    "__pycache__",
    "node_modules",
    "releases",
    "backend/data",
    "backend/storage",
    "backend/storage/uploads",
    "frontend/.next",
    "frontend/node_modules",
    "uploads",
    "logs",
    "qdrant_storage",
    "redis_data",
    "media_cache",
    "transcripts_cache",
    "keyframes_cache",
    "sub2api",
}

EXCLUDED_SUFFIXES = {
    ".pyc",
    ".pyo",
    ".db",
    ".sqlite",
    ".sqlite3",
    ".log",
    ".tsbuildinfo",
    ".tmp",
}
EXCLUDED_NAMES = {".env", ".env.local", "tmp", "temp"}
SECRET_PATTERNS = (
    re.compile(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{20,}"),
    re.compile(
        r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{24,}"
    ),
    re.compile(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"),
)


@dataclass(frozen=True)
class ReleaseAnalysis:
    included: list[Path]
    excluded: list[Path]
    has_secret: bool
    has_database: bool
    has_upload: bool
    has_cache: bool

    @property
    def passed(self) -> bool:
        return not (
            self.has_secret or self.has_database or self.has_upload or self.has_cache
        )


@dataclass(frozen=True)
class ValidatedReleaseSource:
    archive_name: str
    path: Path
    stat_result: os.stat_result


def _absolute_without_resolving(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _is_link_or_reparse(stat_result: os.stat_result) -> bool:
    return stat.S_ISLNK(stat_result.st_mode) or bool(
        getattr(stat_result, "st_file_attributes", 0) & WINDOWS_REPARSE_POINT
    )


def _same_file(left: os.stat_result, right: os.stat_result) -> bool:
    return os.path.samestat(left, right)


def _same_file_snapshot(left: os.stat_result, right: os.stat_result) -> bool:
    return (
        _same_file(left, right)
        and left.st_size == right.st_size
        and left.st_mtime_ns == right.st_mtime_ns
    )


def portable_path_ancestor_conflicts(
    paths: Iterable[str],
) -> tuple[tuple[str, str], ...]:
    """Return file-vs-directory conflicts after portable case folding."""

    entries: list[tuple[tuple[str, ...], str]] = []
    for name in paths:
        parts = name.split("/")
        if (
            not name
            or name.startswith("/")
            or "\\" in name
            or "\x00" in name
            or any(part in {"", ".", ".."} for part in parts)
        ):
            continue
        entries.append((tuple(part.casefold() for part in parts), name))

    names_by_parts: dict[tuple[str, ...], list[str]] = {}
    for folded_parts, name in entries:
        names_by_parts.setdefault(folded_parts, []).append(name)

    conflicts: set[tuple[str, str]] = set()
    for folded_parts, descendant in entries:
        for length in range(1, len(folded_parts)):
            for ancestor in names_by_parts.get(folded_parts[:length], []):
                conflicts.add((ancestor, descendant))
    return tuple(
        sorted(
            conflicts, key=lambda pair: (pair[0].casefold(), pair[1].casefold(), pair)
        )
    )


def _format_path_conflicts(conflicts: Iterable[tuple[str, str]]) -> str:
    return ", ".join(
        f"{ancestor!r} -> {descendant!r}" for ancestor, descendant in conflicts
    )


def validate_release_source(root: Path, source: Path) -> ValidatedReleaseSource:
    """Validate a lexical source path without resolving or following links."""

    absolute_root = _absolute_without_resolving(root)
    absolute_source = _absolute_without_resolving(source)
    try:
        relative = absolute_source.relative_to(absolute_root)
    except ValueError as exc:
        raise ValueError(f"Release source is outside the repository: {source}") from exc
    if not relative.parts:
        raise ValueError(f"Release source is not a regular file: {source}")

    current = absolute_root
    root_stat = os.lstat(current)
    if _is_link_or_reparse(root_stat):
        raise ValueError(
            f"Release source traverses a symbolic link or reparse point: {current}"
        )
    if not stat.S_ISDIR(root_stat.st_mode):
        raise ValueError(f"Release root is not a directory: {root}")

    source_stat = root_stat
    for index, part in enumerate(relative.parts):
        current = current / part
        source_stat = os.lstat(current)
        if _is_link_or_reparse(source_stat):
            raise ValueError(
                f"Release source traverses a symbolic link or reparse point: {current}"
            )
        if index < len(relative.parts) - 1 and not stat.S_ISDIR(source_stat.st_mode):
            raise ValueError(f"Release source parent is not a directory: {current}")

    if not stat.S_ISREG(source_stat.st_mode):
        raise ValueError(f"Release source is not a regular file: {source}")
    archive_name = relative.as_posix()
    if archive_name in {RELEASE_MANIFEST, RELEASE_MANIFEST_DIGEST}:
        raise ValueError(f"Release source uses a reserved archive path: {archive_name}")
    return ValidatedReleaseSource(archive_name, absolute_source, source_stat)


@contextmanager
def open_release_source(
    root: Path,
    source: Path,
) -> Iterator[tuple[ValidatedReleaseSource, BinaryIO, os.stat_result]]:
    """Open one validated regular file and reject path substitution around the read."""

    validated = validate_release_source(root, source)
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(validated.path, flags)
    stream = os.fdopen(descriptor, "rb")
    try:
        opened_stat = os.fstat(stream.fileno())
        if not stat.S_ISREG(opened_stat.st_mode) or not _same_file_snapshot(
            validated.stat_result,
            opened_stat,
        ):
            raise ValueError(f"Release source changed while it was opened: {source}")
        yield validated, stream, opened_stat
        current = validate_release_source(root, source)
        final_stat = os.fstat(stream.fileno())
        if not _same_file_snapshot(opened_stat, final_stat) or not _same_file_snapshot(
            opened_stat,
            current.stat_result,
        ):
            raise ValueError(f"Release source changed while it was packaged: {source}")
    finally:
        stream.close()


def should_exclude(path: Path) -> bool:
    relative = path.relative_to(ROOT).as_posix()
    parts = set(path.relative_to(ROOT).parts)
    if path.name.startswith(".env") and not path.name.endswith(".example"):
        return True
    if path.name in EXCLUDED_NAMES:
        return True
    if path.suffix.lower() in EXCLUDED_SUFFIXES:
        return True
    if any(
        relative == item or relative.startswith(f"{item}/") for item in EXCLUDED_DIRS
    ):
        return True
    if ".git" in parts or "__pycache__" in parts or "node_modules" in parts:
        return True
    return False


def candidate_files() -> list[Path]:
    try:
        output = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT)
        return [ROOT / item for item in output.decode("utf-8").split("\0") if item]
    except (FileNotFoundError, subprocess.CalledProcessError, UnicodeDecodeError):
        return list(ROOT.rglob("*"))


def release_files() -> list[Path]:
    return analyze_release().included


def file_contains_secret(path: Path) -> bool:
    if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip"}:
        return False
    try:
        with open_release_source(ROOT, path) as (_validated, stream, _opened_stat):
            text = stream.read().decode("utf-8")
    except UnicodeDecodeError:
        return False
    return any(pattern.search(text) for pattern in SECRET_PATTERNS)


def analyze_release() -> ReleaseAnalysis:
    included: list[Path] = []
    excluded: list[Path] = []
    for path in candidate_files():
        try:
            path_stat = os.lstat(path)
        except FileNotFoundError:
            continue
        if not stat.S_ISREG(path_stat.st_mode) and not _is_link_or_reparse(path_stat):
            continue
        validated = validate_release_source(ROOT, path)
        if should_exclude(path):
            excluded.append(path)
        else:
            included.append(validated.path)

    included_names = [path.relative_to(ROOT).as_posix() for path in included]
    has_database = any(
        path.suffix.lower() in {".db", ".sqlite", ".sqlite3"} for path in included
    )
    has_upload = any(
        "/uploads/" in f"/{name}/" or name.startswith("backend/storage/")
        for name in included_names
    )
    has_cache = any(
        token in f"/{name}/"
        for name in included_names
        for token in (
            "/node_modules/",
            "/.next/",
            "/__pycache__/",
            "/.pytest_cache/",
            "/qdrant_storage/",
            "/redis_data/",
        )
    )
    has_secret = any(file_contains_secret(path) for path in included)
    return ReleaseAnalysis(
        included=sorted(included),
        excluded=sorted(excluded),
        has_secret=has_secret,
        has_database=has_database,
        has_upload=has_upload,
        has_cache=has_cache,
    )


def print_dry_run(version: str) -> None:
    analysis = analyze_release()
    print(f"release_dry_run_version={version}")
    print(f"included_files={len(analysis.included)}")
    print(f"excluded_files={len(analysis.excluded)}")
    print(f"found_secrets={'yes' if analysis.has_secret else 'no'}")
    print(f"found_database={'yes' if analysis.has_database else 'no'}")
    print(f"found_uploads={'yes' if analysis.has_upload else 'no'}")
    print(f"found_cache={'yes' if analysis.has_cache else 'no'}")
    print(f"passed={'yes' if analysis.passed else 'no'}")
    if not analysis.passed:
        raise SystemExit(1)


def _copy_and_hash(source: BinaryIO, destination: BinaryIO) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    while chunk := source.read(HASH_CHUNK_SIZE):
        destination.write(chunk)
        digest.update(chunk)
        size += len(chunk)
    return digest.hexdigest(), size


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(HASH_CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def _manifest_bytes(version: str, records: list[dict[str, object]]) -> bytes:
    payload = {
        "schema": RELEASE_MANIFEST_SCHEMA,
        "version": version,
        "hash_algorithm": "sha256",
        "files": records,
    }
    return (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def create_release_archive(
    archive_path: Path,
    *,
    version: str,
    root: Path,
    files: Iterable[Path],
) -> None:
    """Write an exact source snapshot plus a detached digest for its manifest."""

    sources: list[ValidatedReleaseSource] = []
    for source in files:
        sources.append(validate_release_source(root, source))

    names = [source.archive_name for source in sources]
    if len(names) != len(set(names)):
        raise ValueError("Release source paths must be unique.")
    if len(names) != len({name.casefold() for name in names}):
        raise ValueError(
            "Release source paths must be unique across case-insensitive filesystems."
        )
    portable_names = (*names, RELEASE_MANIFEST, RELEASE_MANIFEST_DIGEST)
    if len(portable_names) != len({name.casefold() for name in portable_names}):
        raise ValueError(
            "Release source has a reserved metadata path collision on "
            "case-insensitive filesystems."
        )
    path_conflicts = portable_path_ancestor_conflicts(portable_names)
    if path_conflicts:
        raise ValueError(
            "Release sources have a portable extraction path ancestor conflict: "
            f"{_format_path_conflicts(path_conflicts)}"
        )

    archive_path.parent.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, object]] = []
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=archive_path.parent,
            prefix=f".{archive_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
        with zipfile.ZipFile(
            temporary_path, "w", compression=zipfile.ZIP_DEFLATED
        ) as archive:
            for source in sorted(sources, key=lambda item: item.archive_name):
                with open_release_source(root, source.path) as (
                    validated,
                    input_stream,
                    opened_stat,
                ):
                    info = zipfile.ZipInfo(validated.archive_name)
                    info.create_system = 3
                    info.external_attr = (
                        stat.S_IFREG | stat.S_IMODE(opened_stat.st_mode)
                    ) << 16
                    info.compress_type = zipfile.ZIP_DEFLATED
                    with archive.open(info, "w") as output_stream:
                        digest, size = _copy_and_hash(input_stream, output_stream)
                records.append(
                    {"path": validated.archive_name, "sha256": digest, "size": size}
                )

            manifest = _manifest_bytes(version, records)
            archive.writestr(RELEASE_MANIFEST, manifest)
            manifest_digest = hashlib.sha256(manifest).hexdigest()
            archive.writestr(
                RELEASE_MANIFEST_DIGEST,
                f"{manifest_digest}  {RELEASE_MANIFEST}\n".encode("ascii"),
            )
        temporary_path.replace(archive_path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _publish_release_pair(
    staged_archive: Path,
    staged_sidecar: Path,
    archive_path: Path,
    sidecar_path: Path,
) -> None:
    """Publish a verified pair and restore the previous pair after any failed step."""

    backup_archive = staged_archive.parent / ".previous-release.zip"
    backup_sidecar = staged_archive.parent / ".previous-release.zip.sha256"
    archive_backed_up = False
    sidecar_backed_up = False
    archive_published = False
    sidecar_published = False
    try:
        if archive_path.exists():
            os.replace(archive_path, backup_archive)
            archive_backed_up = True
        if sidecar_path.exists():
            os.replace(sidecar_path, backup_sidecar)
            sidecar_backed_up = True
        os.replace(staged_archive, archive_path)
        archive_published = True
        os.replace(staged_sidecar, sidecar_path)
        sidecar_published = True
    except BaseException as publish_error:
        rollback_errors: list[OSError] = []
        for backup, destination, had_backup, published in (
            (backup_sidecar, sidecar_path, sidecar_backed_up, sidecar_published),
            (backup_archive, archive_path, archive_backed_up, archive_published),
        ):
            try:
                if had_backup:
                    os.replace(backup, destination)
                elif published:
                    destination.unlink(missing_ok=True)
            except OSError as exc:
                rollback_errors.append(exc)
        if rollback_errors:
            details = "; ".join(str(error) for error in rollback_errors)
            raise RuntimeError(
                f"Release publication failed and rollback was incomplete: {details}"
            ) from publish_error
        raise


def make_release(
    version: str,
    *,
    root: Path = ROOT,
    releases: Path = RELEASES,
    files: Iterable[Path] | None = None,
    required_entries: set[str] | None = None,
) -> tuple[Path, Path, str]:
    releases.mkdir(parents=True, exist_ok=True)
    date = datetime.now().strftime("%Y%m%d")
    zip_path = releases / f"AI-Knowledge-OS-Pro-{version}-{date}.zip"
    sha_path = zip_path.with_suffix(zip_path.suffix + ".sha256")
    release_sources = list(files) if files is not None else release_files()

    with tempfile.TemporaryDirectory(
        dir=releases, prefix=".release-stage-"
    ) as stage_directory:
        stage = Path(stage_directory)
        staged_zip = stage / zip_path.name
        staged_sha = stage / sha_path.name
        create_release_archive(
            staged_zip, version=version, root=root, files=release_sources
        )
        digest = _file_sha256(staged_zip)
        staged_sha.write_bytes(f"{digest}  {zip_path.name}\n".encode("ascii"))

        if __package__:
            from scripts.check_release import validate_release_archive
        else:
            from check_release import validate_release_archive

        result = validate_release_archive(
            staged_zip,
            version=version,
            root=root,
            expected_files=release_sources,
            required_entries=required_entries,
        )
        if result.archive_sha256 != digest:
            raise RuntimeError(
                "Staged release digest changed between creation and validation."
            )
        _publish_release_pair(staged_zip, staged_sha, zip_path, sha_path)

    return zip_path, sha_path, digest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default="V5.7")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.dry_run:
        print_dry_run(args.version)
        return
    zip_path, sha_path, digest = make_release(args.version)
    print(f"zip={zip_path}")
    print(f"sha256={sha_path}")
    print(digest)


if __name__ == "__main__":
    main()
