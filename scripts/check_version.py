from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DISPLAY_VERSION = "V3.7"
SEMANTIC_VERSION = "3.7.0"


def main() -> None:
    config = (ROOT / "backend" / "app" / "core" / "config.py").read_text(encoding="utf-8")
    package = json.loads((ROOT / "frontend" / "package.json").read_text(encoding="utf-8"))
    package_lock = json.loads((ROOT / "frontend" / "package-lock.json").read_text(encoding="utf-8"))
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    checks = {
        "backend display version": f'app_version: str = "{DISPLAY_VERSION}"' in config,
        "backend semantic version": f'app_semver: str = "{SEMANTIC_VERSION}"' in config,
        "frontend package version": package.get("version") == SEMANTIC_VERSION,
        "frontend lock version": package_lock.get("version") == SEMANTIC_VERSION,
        "frontend lock root package version": package_lock.get("packages", {}).get("", {}).get("version")
        == SEMANTIC_VERSION,
        "README display version": DISPLAY_VERSION in readme,
        "README semantic version": SEMANTIC_VERSION in readme,
    }
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        raise SystemExit("Version consistency failed: " + ", ".join(failed))
    print(f"Version consistency passed: {DISPLAY_VERSION} / {SEMANTIC_VERSION}")


if __name__ == "__main__":
    main()
