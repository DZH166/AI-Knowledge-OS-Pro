from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
DEFAULT_DB = ROOT / ".pytest_tmp" / "v5_evidence_agent_showcase_live_e2e.db"


def bundled_node() -> Path | None:
    candidates = [
        Path.home() / ".cache" / "codex-runtimes" / "codex-primary-runtime" / "dependencies" / "node" / "bin" / "node.exe",
        Path.home() / ".cache" / "codex-runtimes" / "codex-primary-runtime" / "dependencies" / "node" / "bin" / "node",
        Path.home() / ".cache" / "codex-runtimes" / "codex-primary-runtime" / "dependencies" / "node" / "node.exe",
        Path.home() / ".cache" / "codex-runtimes" / "codex-primary-runtime" / "dependencies" / "node" / "node",
    ]
    return next((path for path in candidates if path.exists()), None)


def has_playwright() -> bool:
    return (FRONTEND / "node_modules" / "@playwright" / "test").exists()


def wait_url(url: str, *, timeout: int) -> None:
    deadline = time.time() + timeout
    last_error = ""
    while time.time() < deadline:
        try:
            with urlopen(url, timeout=3) as response:
                if response.status < 500:
                    return
        except (OSError, URLError) as exc:
            last_error = str(exc)
        time.sleep(1)
    raise RuntimeError(f"Timed out waiting for {url}: {last_error}")


def frontend_command(host: str, port: int) -> list[str]:
    npm = shutil.which("npm")
    if npm:
        return [npm, "run", "dev", "--", "--hostname", host, "--port", str(port)]
    node = bundled_node()
    if node is None:
        raise SystemExit("No npm or bundled Node runtime found for frontend E2E.")
    return [str(node), "node_modules/next/dist/bin/next", "dev", "--hostname", host, "--port", str(port)]


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed synthetic demo data, start local services and run optional browser E2E.")
    parser.add_argument("--database-path", type=Path, default=DEFAULT_DB)
    parser.add_argument("--backend-host", default="127.0.0.1")
    parser.add_argument("--backend-port", type=int, default=8010)
    parser.add_argument("--frontend-host", default="127.0.0.1")
    parser.add_argument("--frontend-port", type=int, default=3010)
    parser.add_argument("--skip-if-missing-playwright", action="store_true", default=True)
    parser.add_argument("--strict", action="store_true", help="Fail when Playwright or browser binaries are missing.")
    args = parser.parse_args()

    if not args.strict and args.skip_if_missing_playwright and not has_playwright():
        print("demo_e2e_status=skipped reason=PLAYWRIGHT_NOT_INSTALLED")
        print("hint=Install @playwright/test and browser binaries, then rerun scripts/run_demo_e2e.py.")
        raise SystemExit(0)
    if args.strict and not has_playwright():
        print("demo_e2e_status=failed reason=PLAYWRIGHT_NOT_INSTALLED")
        print("hint=Run npm ci and npx playwright install before strict live demo E2E.")
        raise SystemExit(1)

    database = args.database_path.resolve()
    database.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [sys.executable, "scripts/seed_demo_data.py", "--database-path", str(database), "--reset"],
        cwd=ROOT,
        check=True,
    )

    backend_url = f"http://{args.backend_host}:{args.backend_port}"
    frontend_url = f"http://{args.frontend_host}:{args.frontend_port}"
    backend_env = os.environ.copy()
    backend_env["DATABASE_URL"] = f"sqlite:///{database.as_posix()}"
    backend_env["DEMO_MODE"] = "true"
    backend_env["BACKEND_CORS_ORIGINS"] = json.dumps([frontend_url])
    backend_env["EMBEDDING_DIMENSIONS"] = "1536"
    backend_env["INDEX_VERSION"] = "v2-openai-compatible-1536"
    frontend_env = os.environ.copy()
    frontend_env["NEXT_PUBLIC_API_BASE_URL"] = backend_url
    frontend_env["E2E_BASE_URL"] = frontend_url
    frontend_env["E2E_SKIP_WEBSERVER"] = "1"

    processes: list[subprocess.Popen[str]] = []
    try:
        processes.append(
            subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "app.main:app",
                    "--app-dir",
                    "backend",
                    "--host",
                    args.backend_host,
                    "--port",
                    str(args.backend_port),
                ],
                cwd=ROOT,
                env=backend_env,
                text=True,
            )
        )
        wait_url(f"{backend_url}/health", timeout=60)

        demo_worker = subprocess.Popen(
            [sys.executable, "scripts/run_demo_agent_worker.py"],
            cwd=ROOT,
            env=backend_env,
            text=True,
        )
        processes.append(demo_worker)
        time.sleep(0.25)
        if demo_worker.poll() is not None:
            raise RuntimeError(f"Demo Agent worker exited early with code {demo_worker.returncode}.")

        processes.append(
            subprocess.Popen(
                frontend_command(args.frontend_host, args.frontend_port),
                cwd=FRONTEND,
                env=frontend_env,
                text=True,
            )
        )
        wait_url(frontend_url, timeout=120)

        completed = subprocess.run(
            [sys.executable, "scripts/check_e2e.py", "--run-browser", *(["--strict"] if args.strict else [])],
            cwd=ROOT,
            env=frontend_env,
        )
        raise SystemExit(completed.returncode)
    finally:
        for process in reversed(processes):
            process.terminate()
        for process in reversed(processes):
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()


if __name__ == "__main__":
    main()
