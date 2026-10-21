from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import re
import zipfile


ROOT = Path(__file__).resolve().parents[1]
RELEASES = ROOT / "releases"
FORBIDDEN_PATTERNS = (
    re.compile(r"(^|/)node_modules/"),
    re.compile(r"(^|/)\.next/"),
    re.compile(r"(^|/)\.env$"),
    re.compile(r"(^|/)\.env\.local$"),
    re.compile(r"(^|/)releases/"),
    re.compile(r"(^|/)\.git/"),
    re.compile(r"(^|/)\.(agents|codex)/"),
    re.compile(r"(^|/)backend/(data|storage)/"),
    re.compile(r"(^|/)(uploads|logs?)/"),
    re.compile(r"(^|/)(qdrant_storage|redis_data|media_cache|transcripts_cache|keyframes_cache)/"),
    re.compile(r"(^|/)sub2api/"),
    re.compile(r"(^|/)__pycache__/"),
    re.compile(r"\.(db|sqlite|sqlite3|log|pyc|tsbuildinfo)$"),
)
COMMON_REQUIRED_ENTRIES = {
    ".github/workflows/ci.yml",
    "CONTRIBUTING.md",
    "LICENSE",
    "README.md",
    "SECURITY.md",
    "backend/app/main.py",
    "docs/archive/v3/v3_6_acceptance_report.md",
    "frontend/package.json",
    "scripts/check_encoding.py",
}

VERSION_REQUIRED_ENTRIES = {
    "V4.2": {
        "docs/v4_2_acceptance_report.md",
        "docs/v4_2_full_regression_report.md",
    },
    "V4.3": {
        "docs/v4_3_release_readiness_report.md",
        "docs/v4_3_quality_gate_report.md",
        "docs/v4_3_readme_asset_report.md",
        "docs/v4_3_ux_error_state_report.md",
        "docs/v4_4_planning.md",
        "scripts/check_all.py",
        "scripts/check_docs_links.py",
        "scripts/check_readme_assets.py",
    },
    "V4.4": {
        "docs/v4_4_acceptance_report.md",
        "docs/v4_4_browser_e2e_report.md",
        "docs/v4_4_citation_jump_report.md",
        "docs/v4_4_observability_report.md",
        "docs/v4_4_provider_eval_report.md",
        "docs/v4_4_quality_gate_report.md",
        "docs/v4_4_release_notes.md",
        "frontend/e2e/demo-smoke.spec.ts",
        "frontend/playwright.config.ts",
        "scripts/check_e2e.py",
        "scripts/evaluate_providers.py",
    },
}


def latest_release(version: str) -> Path:
    candidates = sorted(RELEASES.glob(f"AI-Knowledge-OS-Pro-{version}-*.zip"), key=lambda item: item.stat().st_mtime)
    if not candidates:
        raise SystemExit(f"No release zip found for {version}.")
    return candidates[-1]


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect an AI Knowledge OS Pro release archive.")
    parser.add_argument("--version", default="V4.4")
    parser.add_argument("--path", type=Path)
    args = parser.parse_args()

    archive_path = args.path.resolve() if args.path else latest_release(args.version)
    with zipfile.ZipFile(archive_path) as archive:
        names = set(archive.namelist())
    forbidden = sorted(name for name in names if any(pattern.search(name) for pattern in FORBIDDEN_PATTERNS))
    required_entries = COMMON_REQUIRED_ENTRIES | VERSION_REQUIRED_ENTRIES.get(args.version, set())
    missing = sorted(required_entries - names)
    if forbidden or missing:
        if forbidden:
            print("Forbidden release entries:")
            for name in forbidden:
                print(f"- {name}")
        if missing:
            print("Missing required release entries:")
            for name in missing:
                print(f"- {name}")
        raise SystemExit(1)

    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    print(f"Release check passed: {archive_path.name}")
    print(f"files={len(names)} forbidden=0 missing=0")
    print(f"sha256={digest}")


if __name__ == "__main__":
    main()
