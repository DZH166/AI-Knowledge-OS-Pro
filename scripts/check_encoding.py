from __future__ import annotations

import argparse
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {
    ".css",
    ".env",
    ".example",
    ".html",
    ".ini",
    ".js",
    ".json",
    ".md",
    ".mjs",
    ".py",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".yaml",
    ".yml",
}
TEXT_NAMES = {"Dockerfile", "LICENSE", "Makefile"}
EXCLUDED_PARTS = {
    ".git",
    ".mypy_cache",
    ".next",
    ".pytest_cache",
    ".pytest_tmp",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "data",
    "dist",
    "node_modules",
    "out",
    "releases",
    "storage",
    "sub2api",
    "venv",
}
MOJIBAKE_TOKENS = (
    chr(0xFFFD),
    "".join(chr(value) for value in (0x951F, 0x65A4, 0x62F7)),
    chr(0x9471),
    chr(0x959E),
    chr(0x00C3),
    chr(0x00C2),
    chr(0x00E2) + chr(0x20AC),
    chr(0x00F0) + chr(0x0178),
)
QUESTION_RUN = re.compile(r"\?{4,}")
IMMUTABLE_LEGACY_LOGS = {
    "docs/learning_log.md",
    "docs/stage_delivery_log.md",
}


def iter_text_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT)
        if any(part in EXCLUDED_PARTS for part in relative.parts):
            continue
        if path.suffix.lower() in TEXT_SUFFIXES or path.name in TEXT_NAMES:
            files.append(path)
    return sorted(files)


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate repository text files as clean UTF-8.")
    parser.add_argument(
        "--strict-legacy",
        action="store_true",
        help="Treat irreversible question-mark runs in append-only legacy logs as failures.",
    )
    args = parser.parse_args()

    failures: list[str] = []
    legacy_warnings: list[str] = []
    files = iter_text_files()
    for path in files:
        relative = path.relative_to(ROOT).as_posix()
        try:
            raw = path.read_bytes()
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            failures.append(f"{relative}: invalid UTF-8 at byte {exc.start}")
            continue
        if raw.startswith(b"\xef\xbb\xbf"):
            failures.append(f"{relative}: UTF-8 BOM is not allowed")
        for line_number, line in enumerate(text.splitlines(), start=1):
            token = next((item for item in MOJIBAKE_TOKENS if item in line), None)
            if token:
                failures.append(f"{relative}:{line_number}: suspicious mojibake token {token!r}")
            if QUESTION_RUN.search(line):
                message = f"{relative}:{line_number}: irreversible question-mark run"
                if relative in IMMUTABLE_LEGACY_LOGS and not args.strict_legacy:
                    legacy_warnings.append(message)
                else:
                    failures.append(message)

    if failures:
        print("Encoding check failed:")
        for item in failures:
            print(f"- {item}")
        raise SystemExit(1)

    print(f"Encoding check passed for {len(files)} UTF-8 text files.")
    if legacy_warnings:
        print(
            f"Preserved {len(legacy_warnings)} immutable legacy log lines with irreversible source loss; "
            "readable recovery entries remain append-only."
        )


if __name__ == "__main__":
    main()
