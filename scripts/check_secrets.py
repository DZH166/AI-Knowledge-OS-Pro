from __future__ import annotations

from pathlib import Path
import os
import re
import subprocess


ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {".md", ".py", ".ts", ".tsx", ".json", ".yml", ".yaml", ".toml", ".ini", ".txt", ".example"}
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
SECRET_PATTERNS = (
    re.compile(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"(?i)\b(api[_-]?key|secret|token|password)\s*[:=]\s*['\"]?(?!<|your-|example|demo|fake|not_configured|$)[A-Za-z0-9_\-]{24,}"),
)


def git_files() -> list[Path] | None:
    if not (ROOT / ".git").exists():
        return None
    try:
        output = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT)
    except (OSError, subprocess.CalledProcessError):
        return None
    return [ROOT / item for item in output.decode("utf-8").split("\0") if item]


def is_excluded_dir(path: Path) -> bool:
    relative = path.relative_to(ROOT).as_posix()
    return path.name in EXCLUDED_DIRS or any(relative == item or relative.startswith(f"{item}/") for item in EXCLUDED_RELATIVE_DIRS)


def filesystem_files() -> list[Path]:
    files: list[Path] = []
    for current, dirs, names in os.walk(ROOT):
        current_path = Path(current)
        dirs[:] = [name for name in dirs if not is_excluded_dir(current_path / name)]
        for name in names:
            files.append(current_path / name)
    return files


def candidate_files() -> tuple[str, str, list[Path]]:
    files = git_files()
    if files is not None:
        return "git", "git_ls_files", files
    return "filesystem", "no_git_metadata", filesystem_files()


def should_scan(path: Path) -> bool:
    if path.name.endswith(".example"):
        return True
    return path.suffix.lower() in TEXT_SUFFIXES


def main() -> None:
    findings: list[str] = []
    scanned = 0
    mode, reason, files = candidate_files()
    for path in files:
        if not path.is_file() or not should_scan(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        scanned += 1
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                findings.append(path.relative_to(ROOT).as_posix())
                break

    if findings:
        print(f"Potential secrets found: mode={mode} reason={reason}")
        for item in findings:
            print(f"- {item}")
        raise SystemExit(1)
    print(f"Secret check passed: mode={mode} reason={reason} scanned={scanned} findings=0")


if __name__ == "__main__":
    main()
