from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"

REQUIRED_FILES = (
    FRONTEND / "playwright.config.ts",
    FRONTEND / "e2e" / "demo-smoke.spec.ts",
    FRONTEND / "e2e" / "citation-jump.spec.ts",
    FRONTEND / "e2e" / "system-observability.spec.ts",
    FRONTEND / "e2e" / "v5-evidence-agent.spec.ts",
    FRONTEND / "e2e" / "v5-2-agent-control.spec.ts",
    FRONTEND / "e2e" / "run-optional-e2e.mjs",
    ROOT / "scripts" / "run_demo_e2e.py",
    ROOT / "scripts" / "run_demo_agent_worker.py",
)


def bundled_node() -> Path | None:
    candidates = [
        Path.home() / ".cache" / "codex-runtimes" / "codex-primary-runtime" / "dependencies" / "node" / "bin" / "node.exe",
        Path.home() / ".cache" / "codex-runtimes" / "codex-primary-runtime" / "dependencies" / "node" / "bin" / "node",
        Path.home() / ".cache" / "codex-runtimes" / "codex-primary-runtime" / "dependencies" / "node" / "node.exe",
        Path.home() / ".cache" / "codex-runtimes" / "codex-primary-runtime" / "dependencies" / "node" / "node",
    ]
    return next((path for path in candidates if path.exists()), None)


def static_check() -> list[str]:
    failures: list[str] = []
    for path in REQUIRED_FILES:
        if not path.exists():
            failures.append(f"Missing E2E file: {path.relative_to(ROOT).as_posix()}")
    package_path = FRONTEND / "package.json"
    try:
        package = json.loads(package_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        failures.append(f"Cannot read frontend/package.json: {exc}")
        return failures
    scripts = package.get("scripts") if isinstance(package.get("scripts"), dict) else {}
    if scripts.get("test:e2e") != "node e2e/run-optional-e2e.mjs":
        failures.append("frontend/package.json must expose scripts.test:e2e as node e2e/run-optional-e2e.mjs")
    if scripts.get("test:e2e:strict") != "node e2e/run-optional-e2e.mjs --strict":
        failures.append("frontend/package.json must expose scripts.test:e2e:strict as node e2e/run-optional-e2e.mjs --strict")
    dev_dependencies = package.get("devDependencies") if isinstance(package.get("devDependencies"), dict) else {}
    if "@playwright/test" not in dev_dependencies:
        failures.append("frontend/package.json must include @playwright/test as a devDependency for strict live E2E")
    runner = (FRONTEND / "e2e" / "run-optional-e2e.mjs").read_text(encoding="utf-8")
    if "NEXT_PUBLIC_API_BASE_URL_MISSING" not in runner:
        failures.append("Strict E2E runner must fail or skip explicitly when NEXT_PUBLIC_API_BASE_URL is missing")
    for required in ("--hostname", "--port", "taskkill", "CHROME_LOG_FILE"):
        if required not in runner:
            failures.append(f"E2E runner owned web-server contract is missing: {required}")
    config = (FRONTEND / "playwright.config.ts").read_text(encoding="utf-8")
    if "webServer: undefined" not in config or "reuseExistingServer" in config:
        failures.append("Playwright config must never start or reuse an unowned web server")
    return failures


def run_browser(*, strict: bool) -> int:
    npm = shutil.which("npm")
    if npm:
        command = [npm, "run", "test:e2e:strict" if strict else "test:e2e"]
    else:
        node = bundled_node()
        if node is None:
            print(f"e2e_status={'failed' if strict else 'skipped'} reason=NO_NODE_OR_NPM")
            return 1 if strict else 0
        command = [str(node), "e2e/run-optional-e2e.mjs"]
        if strict:
            command.append("--strict")
    completed = subprocess.run(command, cwd=FRONTEND)
    return completed.returncode


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate optional browser E2E scaffolding.")
    parser.add_argument("--run-browser", action="store_true", help="Try to run npm run test:e2e; missing Playwright/browser runtime skips honestly.")
    parser.add_argument("--strict", action="store_true", help="Require a real browser E2E run; missing Playwright or browsers fail.")
    args = parser.parse_args()

    failures = static_check()
    print("e2e_static_check=checked")
    print(f"required_files={len(REQUIRED_FILES)}")
    if failures:
        print("result=failed")
        for failure in failures:
            print(f"failure: {failure}")
        raise SystemExit(1)
    print("e2e_static_check=passed")

    if args.run_browser:
        raise SystemExit(run_browser(strict=args.strict))
    print("e2e_status=not_run reason=STATIC_MODE")
    print("result=passed")


if __name__ == "__main__":
    main()
