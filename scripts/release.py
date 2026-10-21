from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
import hashlib
from pathlib import Path
import re
import subprocess
import zipfile


ROOT = Path(__file__).resolve().parents[1]
RELEASES = ROOT / "releases"

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

EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".db", ".sqlite", ".sqlite3", ".log", ".tsbuildinfo", ".tmp"}
EXCLUDED_NAMES = {".env", ".env.local", "tmp", "temp"}
SECRET_PATTERNS = (
    re.compile(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{24,}"),
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
        return not (self.has_secret or self.has_database or self.has_upload or self.has_cache)


def should_exclude(path: Path) -> bool:
    relative = path.relative_to(ROOT).as_posix()
    parts = set(path.relative_to(ROOT).parts)
    if path.name.startswith(".env") and not path.name.endswith(".example"):
        return True
    if path.name in EXCLUDED_NAMES:
        return True
    if path.suffix.lower() in EXCLUDED_SUFFIXES:
        return True
    if any(relative == item or relative.startswith(f"{item}/") for item in EXCLUDED_DIRS):
        return True
    if ".git" in parts or "__pycache__" in parts or "node_modules" in parts:
        return True
    return False


def candidate_files() -> list[Path]:
    try:
        output = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT)
        return [ROOT / item for item in output.decode("utf-8").split("\0") if item]
    except (FileNotFoundError, subprocess.CalledProcessError, UnicodeDecodeError):
        return [path for path in ROOT.rglob("*") if path.is_file()]


def release_files() -> list[Path]:
    return analyze_release().included


def file_contains_secret(path: Path) -> bool:
    if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip"}:
        return False
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return False
    return any(pattern.search(text) for pattern in SECRET_PATTERNS)


def analyze_release() -> ReleaseAnalysis:
    included: list[Path] = []
    excluded: list[Path] = []
    for path in candidate_files():
        if not path.is_file():
            continue
        if should_exclude(path):
            excluded.append(path)
        else:
            included.append(path)

    included_names = [path.relative_to(ROOT).as_posix() for path in included]
    has_database = any(path.suffix.lower() in {".db", ".sqlite", ".sqlite3"} for path in included)
    has_upload = any("/uploads/" in f"/{name}/" or name.startswith("backend/storage/") for name in included_names)
    has_cache = any(
        token in f"/{name}/"
        for name in included_names
        for token in ("/node_modules/", "/.next/", "/__pycache__/", "/.pytest_cache/", "/qdrant_storage/", "/redis_data/")
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


def make_release(version: str) -> tuple[Path, Path, str]:
    RELEASES.mkdir(exist_ok=True)
    date = datetime.now().strftime("%Y%m%d")
    zip_path = RELEASES / f"AI-Knowledge-OS-Pro-{version}-{date}.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in release_files():
            archive.write(path, path.relative_to(ROOT).as_posix())

    digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    sha_path = zip_path.with_suffix(zip_path.suffix + ".sha256")
    sha_path.write_text(f"{digest}  {zip_path.name}\n", encoding="utf-8")
    return zip_path, sha_path, digest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default="V4.8")
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
