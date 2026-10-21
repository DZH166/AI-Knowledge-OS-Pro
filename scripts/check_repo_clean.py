from __future__ import annotations

from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = (
    re.compile(r"(^|/)\.env($|\.)"),
    re.compile(r"\.(db|sqlite|sqlite3|log|tsbuildinfo)$"),
    re.compile(r"(^|/)(uploads|logs?|node_modules|\.next|__pycache__|releases|qdrant_storage|redis_data|media_cache|transcripts_cache|keyframes_cache)/"),
    re.compile(r"(^|/)(\.venv|venv|\.pytest_cache|\.mypy_cache|\.ruff_cache)/"),
)


def tracked_names() -> list[str]:
    output = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT)
    return [item for item in output.decode("utf-8").split("\0") if item]


def is_allowed_example(name: str) -> bool:
    return name.endswith(".env.example") or name.endswith(".env.local.example")


def main() -> None:
    violations = [
        name
        for name in tracked_names()
        if not is_allowed_example(name) and any(pattern.search(name) for pattern in FORBIDDEN)
    ]
    if violations:
        print("Forbidden tracked files:")
        for name in violations:
            print(f"- {name}")
        raise SystemExit(1)
    print("Repository cleanliness check passed: forbidden tracked files=0")


if __name__ == "__main__":
    main()
