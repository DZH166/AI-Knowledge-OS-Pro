from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DISPLAY_VERSION = "V5.3"
SEMANTIC_VERSION = "5.3.0"
PRODUCT_GENERATION = "V5"

VERSION_TEXT_SURFACES = {
    "README": ("README.md", (DISPLAY_VERSION, SEMANTIC_VERSION)),
    "contributing guide": ("CONTRIBUTING.md", (DISPLAY_VERSION,)),
    "release process": ("docs/release_process.md", (DISPLAY_VERSION,)),
    "versioning doc": ("docs/versioning.md", (DISPLAY_VERSION, SEMANTIC_VERSION)),
    "local release checklist": ("docs/release_checklist.md", (DISPLAY_VERSION, SEMANTIC_VERSION)),
    "GitHub release checklist": ("docs/github_release_checklist.md", (DISPLAY_VERSION, SEMANTIC_VERSION)),
    "CI workflow": (".github/workflows/ci.yml", (DISPLAY_VERSION, "codex/**")),
    "GitHub bug template": (".github/ISSUE_TEMPLATE/bug_report.yml", (DISPLAY_VERSION, SEMANTIC_VERSION)),
}

PRODUCT_GENERATION_SURFACES = {
    "AppShell product generation": (
        "frontend/components/AppShell.tsx",
        ("<strong>溯知</strong>", "<small>证据研究工作台</small>"),
    ),
}


def surface_contains(path_text: str, tokens: tuple[str, ...]) -> bool:
    text = (ROOT / path_text).read_text(encoding="utf-8")
    return all(token in text for token in tokens)


def main() -> None:
    config = (ROOT / "backend" / "app" / "core" / "config.py").read_text(encoding="utf-8")
    package = json.loads((ROOT / "frontend" / "package.json").read_text(encoding="utf-8"))
    package_lock = json.loads((ROOT / "frontend" / "package-lock.json").read_text(encoding="utf-8"))

    checks = {
        "backend display version": f'app_version: str = "{DISPLAY_VERSION}"' in config,
        "backend semantic version": f'app_semver: str = "{SEMANTIC_VERSION}"' in config,
        "frontend package version": package.get("version") == SEMANTIC_VERSION,
        "frontend lock version": package_lock.get("version") == SEMANTIC_VERSION,
        "frontend lock root package version": package_lock.get("packages", {}).get("", {}).get("version")
        == SEMANTIC_VERSION,
    }
    checks.update(
        {
            f"{label} version surface": surface_contains(path_text, tokens)
            for label, (path_text, tokens) in VERSION_TEXT_SURFACES.items()
        }
    )
    checks.update(
        {
            f"{label} surface": surface_contains(path_text, tokens)
            for label, (path_text, tokens) in PRODUCT_GENERATION_SURFACES.items()
        }
    )
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        raise SystemExit("Version consistency failed: " + ", ".join(failed))
    print(
        f"Version consistency passed: {DISPLAY_VERSION} / {SEMANTIC_VERSION}; "
        f"product generation: {PRODUCT_GENERATION}"
    )


if __name__ == "__main__":
    main()
