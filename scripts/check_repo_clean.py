from __future__ import annotations

from pathlib import Path
import os
import re
import subprocess


ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = (
    re.compile(r"(^|/)\.env($|\.)"),
    re.compile(r"\.(db|sqlite|sqlite3|log|tsbuildinfo)$"),
    re.compile(r"(^|/)(uploads|logs?|node_modules|\.next|__pycache__|releases|qdrant_storage|redis_data|media_cache|transcripts_cache|keyframes_cache)/"),
    re.compile(r"(^|/)(\.venv|venv|\.pytest_cache|\.mypy_cache|\.ruff_cache)/"),
)
EXCLUDED_DIRS = {
    ".git",
    ".agents",
    ".codex",
    ".next",
    ".pytest_cache",
    ".pytest_tmp",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "node_modules",
    "releases",
    "uploads",
    "logs",
    "qdrant_storage",
    "redis_data",
    "media_cache",
    "transcripts_cache",
    "keyframes_cache",
}
EXCLUDED_RELATIVE_DIRS = {
    "backend/data",
    "backend/storage",
    "frontend/.next",
    "frontend/node_modules",
}


def git_names() -> list[str] | None:
    if not (ROOT / ".git").exists():
        return None
    try:
        output = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT)
    except (OSError, subprocess.CalledProcessError):
        return None
    return [item for item in output.decode("utf-8").split("\0") if item]


def is_excluded_dir(path: Path) -> bool:
    relative = path.relative_to(ROOT).as_posix()
    return path.name in EXCLUDED_DIRS or any(relative == item or relative.startswith(f"{item}/") for item in EXCLUDED_RELATIVE_DIRS)


def filesystem_names() -> list[str]:
    names: list[str] = []
    for current, dirs, files in os.walk(ROOT):
        current_path = Path(current)
        dirs[:] = [name for name in dirs if not is_excluded_dir(current_path / name)]
        for name in files:
            names.append((current_path / name).relative_to(ROOT).as_posix())
    return names


def candidate_names() -> tuple[str, str, list[str]]:
    names = git_names()
    if names is not None:
        return "git", "git_ls_files", names
    return "filesystem", "no_git_metadata", filesystem_names()


def is_allowed_example(name: str) -> bool:
    return name.endswith(".env.example") or name.endswith(".env.local.example")


def main() -> None:
    mode, reason, names = candidate_names()
    violations = [
        name
        for name in names
        if not is_allowed_example(name) and any(pattern.search(name) for pattern in FORBIDDEN)
    ]
    if violations:
        print(f"Forbidden files: mode={mode} reason={reason}")
        for name in violations:
            print(f"- {name}")
        raise SystemExit(1)
    print(f"Repository cleanliness check passed: mode={mode} reason={reason} forbidden_files=0")


if __name__ == "__main__":
    main()
