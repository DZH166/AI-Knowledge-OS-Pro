from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]
RELEASES = ROOT / "releases"

EXCLUDED_DIRS = {
    ".git",
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
    "frontend/.next",
    "frontend/node_modules",
}

EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".db", ".sqlite", ".sqlite3", ".log", ".tsbuildinfo", ".tmp"}
EXCLUDED_NAMES = {".env", ".env.local", "tmp", "temp"}


def should_exclude(path: Path) -> bool:
    relative = path.relative_to(ROOT).as_posix()
    parts = set(path.relative_to(ROOT).parts)
    if path.name in EXCLUDED_NAMES:
        return True
    if path.suffix.lower() in EXCLUDED_SUFFIXES:
        return True
    if any(relative == item or relative.startswith(f"{item}/") for item in EXCLUDED_DIRS):
        return True
    if "__pycache__" in parts or "node_modules" in parts:
        return True
    return False


def make_release(version: str) -> tuple[Path, Path, str]:
    RELEASES.mkdir(exist_ok=True)
    date = datetime.now().strftime("%Y%m%d")
    zip_path = RELEASES / f"AI-Knowledge-OS-Pro-{version}-{date}.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in ROOT.rglob("*"):
            if path.is_dir() or should_exclude(path):
                continue
            archive.write(path, path.relative_to(ROOT).as_posix())

    digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    sha_path = zip_path.with_suffix(zip_path.suffix + ".sha256")
    sha_path.write_text(f"{digest}  {zip_path.name}\n", encoding="utf-8")
    return zip_path, sha_path, digest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default="V3.6")
    args = parser.parse_args()
    zip_path, sha_path, digest = make_release(args.version)
    print(f"zip={zip_path}")
    print(f"sha256={sha_path}")
    print(digest)


if __name__ == "__main__":
    main()
