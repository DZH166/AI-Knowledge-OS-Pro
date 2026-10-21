from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import time
from typing import Callable, Sequence
from urllib.error import URLError
from urllib.request import urlopen
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
INDEX_VERSION = "v2-openai-compatible-1536"
EMBEDDING_DIMENSIONS = 1536
DEFAULT_REDIS_IMAGE = "redis:7.4-alpine"
DEFAULT_QDRANT_IMAGE = "qdrant/qdrant:v1.18.0"
LOOPBACK_HOST = "127.0.0.1"
FRONTEND_PREWARM_PATHS = (
    "/",
    "/dashboard",
    "/upload",
    "/tasks",
    "/chat",
    "/media",
    "/media/sources/3?t=6000&chunk=6",
    "/learning/cards",
    "/learning",
    "/portfolio",
    "/portfolio/resume",
    "/portfolio/interview",
    "/system",
    "/system/observability",
    "/evaluations",
    "/evaluations/evaluation-demo",
    "/policies",
    "/policies/00000000-0000-0000-0000-000000000001",
    "/workbench?demo=1",
    "/runs/demo-run?demo=1",
    "/runs/demo-run/trace",
    "/library",
    "/artifacts",
    "/artifacts/artifact-demo?demo=1",
    "/code?source=44",
    "/documents/1?page=2",
)


class RuntimeBoundaryError(RuntimeError):
    def __init__(self, boundary: str, message: str) -> None:
        super().__init__(message)
        self.boundary = boundary


@dataclass(frozen=True, slots=True)
class RuntimeIdentity:
    token: str
    database_path: Path
    queue_name: str
    qdrant_collection_prefix: str
    qdrant_collection: str
    redis_container: str
    qdrant_container: str
    worker_name: str


@dataclass(frozen=True, slots=True)
class RuntimePorts:
    frontend: int
    backend: int
    redis: int
    qdrant: int

    @property
    def frontend_url(self) -> str:
        return f"http://{LOOPBACK_HOST}:{self.frontend}"

    @property
    def backend_url(self) -> str:
        return f"http://{LOOPBACK_HOST}:{self.backend}"

    @property
    def redis_url(self) -> str:
        return f"redis://{LOOPBACK_HOST}:{self.redis}/0"

    @property
    def qdrant_url(self) -> str:
        return f"http://{LOOPBACK_HOST}:{self.qdrant}"


def _safe_token(value: str) -> str:
    token = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if not token:
        raise ValueError("Runtime token must contain at least one letter or number.")
    return token[:40]


def build_runtime_identity(
    *,
    root: Path = ROOT,
    token: str | None = None,
    database_path: Path | None = None,
) -> RuntimeIdentity:
    safe_token = _safe_token(token or f"{os.getpid()}-{uuid4().hex[:8]}")
    queue_token = safe_token.replace("-", "_")
    queue_name = f"v5_3_{queue_token}"
    container_prefix = f"v5-3-{safe_token}"
    resolved_database = (
        database_path.resolve()
        if database_path is not None
        else root / ".pytest_tmp" / f"v5_3_{safe_token}_showcase_e2e.db"
    )
    qdrant_collection = f"{queue_name}_{INDEX_VERSION}_chunks".replace("-", "_")
    return RuntimeIdentity(
        token=safe_token,
        database_path=resolved_database,
        queue_name=queue_name,
        qdrant_collection_prefix=queue_name,
        qdrant_collection=qdrant_collection,
        redis_container=f"{container_prefix}-redis",
        qdrant_container=f"{container_prefix}-qdrant",
        worker_name=f"{container_prefix}-worker",
    )


def build_runtime_environments(
    identity: RuntimeIdentity,
    ports: RuntimePorts,
    *,
    base_env: dict[str, str] | None = None,
) -> tuple[dict[str, str], dict[str, str]]:
    inherited = dict(os.environ if base_env is None else base_env)
    backend_env = inherited.copy()
    backend_env.update(
        {
            "DATABASE_URL": f"sqlite:///{identity.database_path.as_posix()}",
            "DEMO_MODE": "true",
            "BACKEND_CORS_ORIGINS": json.dumps([ports.frontend_url]),
            "EMBEDDING_DIMENSIONS": str(EMBEDDING_DIMENSIONS),
            "INDEX_VERSION": INDEX_VERSION,
            "REDIS_URL": ports.redis_url,
            "TASK_QUEUE_NAME": identity.queue_name,
            "WORKER_QUEUES": identity.queue_name,
            "WORKER_NAME": identity.worker_name,
            "QDRANT_URL": ports.qdrant_url,
            "QDRANT_COLLECTION_PREFIX": identity.qdrant_collection_prefix,
            "PYTHONUNBUFFERED": "1",
        }
    )
    frontend_env = inherited.copy()
    frontend_env.update(
        {
            "NEXT_PUBLIC_API_BASE_URL": ports.backend_url,
            "E2E_BASE_URL": ports.frontend_url,
            "E2E_SKIP_WEBSERVER": "1",
            "E2E_TEST_TIMEOUT_MS": "60000",
            "E2E_WORKERS": "4",
        }
    )
    return backend_env, frontend_env


def finalize_runtime_manifest(manifest: dict[str, object], result: int) -> dict[str, object]:
    return {
        **manifest,
        "final_test_result": {
            "status": "passed" if result == 0 else "failed",
            "exit_code": result,
        },
    }


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


def require_playwright() -> None:
    node_command = shutil.which("node")
    node = Path(node_command) if node_command else bundled_node()
    if node is None or not node.exists():
        raise RuntimeBoundaryError("playwright_preflight", "Node.js is unavailable.")
    if not has_playwright():
        raise RuntimeBoundaryError(
            "playwright_preflight",
            "@playwright/test is unavailable; run npm ci in frontend.",
        )
    probe = subprocess.run(
        [
            str(node),
            "-e",
            (
                "const fs=require('node:fs');"
                "const {chromium}=require('@playwright/test');"
                "const target=chromium.executablePath();"
                "if(!fs.existsSync(target)){console.error(target);process.exit(1)}"
            ),
        ],
        cwd=FRONTEND,
        text=True,
        capture_output=True,
    )
    if probe.returncode != 0:
        raise RuntimeBoundaryError(
            "playwright_preflight",
            "Chromium is unavailable; run npx playwright install chromium in frontend.",
        )


RunFunction = Callable[..., subprocess.CompletedProcess[str]]


def require_docker(*, run: RunFunction = subprocess.run) -> None:
    if run is subprocess.run and shutil.which("docker") is None:
        raise RuntimeBoundaryError("docker_preflight", "Docker CLI is unavailable.")
    completed = run(
        ["docker", "info", "--format", "{{.ServerVersion}}"],
        text=True,
        capture_output=True,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "unknown Docker error").strip()
        raise RuntimeBoundaryError(
            "docker_preflight",
            f"Docker daemon is unavailable: {detail}",
        )


def stop_owned_containers(
    container_names: Sequence[str],
    *,
    run: RunFunction = subprocess.run,
) -> None:
    for name in reversed(container_names):
        completed = run(
            ["docker", "stop", "--time", "10", name],
            text=True,
            capture_output=True,
        )
        outcome = "stopped" if completed.returncode == 0 else "already_absent"
        print(f"runtime_cleanup=container name={name} outcome={outcome}", flush=True)


def terminate_owned_processes(processes: Sequence[tuple[str, subprocess.Popen[str]]]) -> None:
    for label, process in reversed(processes):
        if process.poll() is not None:
            continue
        if os.name == "nt":
            completed = subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                text=True,
                capture_output=True,
            )
            action = "taskkill_tree"
            if completed.returncode != 0 and process.poll() is None:
                process.kill()
                action = "kill_owned_pid"
            print(f"runtime_cleanup=process label={label} pid={process.pid} action={action}", flush=True)
        else:
            process.terminate()
            print(f"runtime_cleanup=process label={label} pid={process.pid} action=terminate", flush=True)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
            print(f"runtime_cleanup=process label={label} pid={process.pid} action=kill", flush=True)


class OwnedRuntime:
    def __init__(self) -> None:
        self.processes: list[tuple[str, subprocess.Popen[str]]] = []
        self.containers: list[str] = []

    def start_process(
        self,
        label: str,
        command: Sequence[str],
        *,
        cwd: Path,
        env: dict[str, str],
    ) -> subprocess.Popen[str]:
        process = subprocess.Popen(list(command), cwd=cwd, env=env, text=True)
        self.processes.append((label, process))
        print(f"runtime_start=process label={label} pid={process.pid}", flush=True)
        return process

    def start_container(self, label: str, name: str, image: str, host_port: int, container_port: int) -> None:
        completed = subprocess.run(
            [
                "docker",
                "run",
                "--detach",
                "--rm",
                "--name",
                name,
                "--label",
                "ai-knowledge-os.runtime=v5.3-strict-e2e",
                "--publish",
                f"{LOOPBACK_HOST}:{host_port}:{container_port}",
                image,
            ],
            text=True,
            capture_output=True,
        )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "unknown Docker error").strip()
            raise RuntimeBoundaryError(f"{label}_startup", f"Could not start {label}: {detail}")
        self.containers.append(name)
        print(f"runtime_start=container label={label} name={name} port={host_port}", flush=True)

    def close(self) -> None:
        terminate_owned_processes(self.processes)
        stop_owned_containers(self.containers)


def _available_port(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        try:
            probe.bind((LOOPBACK_HOST, port))
        except OSError:
            return False
    return True


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind((LOOPBACK_HOST, 0))
        return int(probe.getsockname()[1])


def resolve_ports(frontend: int, backend: int, redis: int, qdrant: int) -> RuntimePorts:
    requested = {"frontend": frontend, "backend": backend, "redis": redis, "qdrant": qdrant}
    resolved: dict[str, int] = {}
    for label, port in requested.items():
        candidate = _free_port() if port == 0 else port
        if not 1 <= candidate <= 65535:
            raise RuntimeBoundaryError("port_preflight", f"{label} port is outside 1-65535: {candidate}")
        if candidate in resolved.values():
            raise RuntimeBoundaryError("port_preflight", f"{label} port duplicates another runtime port: {candidate}")
        if not _available_port(candidate):
            raise RuntimeBoundaryError("port_preflight", f"{label} port is already in use: {candidate}")
        resolved[label] = candidate
    return RuntimePorts(**resolved)


def ensure_showcase_database_path(path: Path) -> None:
    if "showcase" not in path.name.lower():
        raise RuntimeBoundaryError(
            "database_preflight",
            "The isolated SQLite filename must contain 'showcase' so the demo seeder can reset it safely.",
        )


def ensure_process_alive(process: subprocess.Popen[str], boundary: str) -> None:
    returncode = process.poll()
    if returncode is not None:
        raise RuntimeBoundaryError(boundary, f"Process exited early with code {returncode}.")


def wait_url(
    url: str,
    *,
    timeout: float,
    boundary: str,
    process: subprocess.Popen[str] | None = None,
) -> None:
    deadline = time.monotonic() + timeout
    last_error = ""
    while time.monotonic() < deadline:
        if process is not None:
            ensure_process_alive(process, boundary)
        try:
            with urlopen(url, timeout=3) as response:
                if response.status < 500:
                    print(f"runtime_readiness={boundary} status=ready url={url}", flush=True)
                    return
        except (OSError, URLError) as exc:
            last_error = str(exc)
        time.sleep(0.5)
    raise RuntimeBoundaryError(boundary, f"Timed out waiting for {url}: {last_error}")


def prewarm_frontend_routes(
    frontend_url: str,
    *,
    timeout: float,
    process: subprocess.Popen[str],
    paths: Sequence[str] = FRONTEND_PREWARM_PATHS,
) -> None:
    """Compile each page once before parallel browser workers start."""
    for path in paths:
        ensure_process_alive(process, "frontend_prewarm")
        url = f"{frontend_url}{path}"
        try:
            with urlopen(url, timeout=timeout) as response:
                if response.status >= 500:
                    raise RuntimeBoundaryError(
                        "frontend_prewarm",
                        f"Frontend prewarm returned HTTP {response.status}: {url}",
                    )
        except RuntimeBoundaryError:
            raise
        except (OSError, URLError) as exc:
            raise RuntimeBoundaryError(
                "frontend_prewarm",
                f"Frontend prewarm failed for {url}: {exc}",
            ) from exc
    print(f"runtime_readiness=frontend_prewarm status=ready routes={len(paths)}", flush=True)


def wait_redis(url: str, *, timeout: float) -> None:
    from redis import Redis

    deadline = time.monotonic() + timeout
    last_error = ""
    connection = Redis.from_url(url, socket_connect_timeout=1, socket_timeout=1)
    while time.monotonic() < deadline:
        try:
            if connection.ping():
                print(f"runtime_readiness=redis status=ready url={url}", flush=True)
                return
        except Exception as exc:
            last_error = str(exc)
        time.sleep(0.5)
    raise RuntimeBoundaryError("redis_readiness", f"Timed out waiting for Redis: {last_error}")


def ensure_qdrant_collection(url: str, collection: str, *, timeout: float) -> None:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models as qdrant_models

    deadline = time.monotonic() + timeout
    last_error = ""
    while time.monotonic() < deadline:
        try:
            client = QdrantClient(url=url, timeout=3)
            names = {item.name for item in client.get_collections().collections}
            if collection not in names:
                client.create_collection(
                    collection_name=collection,
                    vectors_config=qdrant_models.VectorParams(
                        size=EMBEDDING_DIMENSIONS,
                        distance=qdrant_models.Distance.COSINE,
                    ),
                )
            client.get_collection(collection)
            print(
                f"runtime_readiness=qdrant status=ready url={url} collection={collection}",
                flush=True,
            )
            return
        except Exception as exc:
            last_error = str(exc)
        time.sleep(0.5)
    raise RuntimeBoundaryError("qdrant_readiness", f"Timed out waiting for Qdrant: {last_error}")


def wait_worker(
    redis_url: str,
    *,
    queue_name: str,
    worker_name: str,
    timeout: float,
    process: subprocess.Popen[str],
) -> None:
    from redis import Redis
    from rq import Queue, Worker

    connection = Redis.from_url(redis_url, socket_connect_timeout=1, socket_timeout=1)
    queue = Queue(queue_name, connection=connection)
    deadline = time.monotonic() + timeout
    last_workers: list[str] = []
    while time.monotonic() < deadline:
        ensure_process_alive(process, "worker_readiness")
        try:
            workers = Worker.all(connection=connection, queue=queue)
            last_workers = [worker.name for worker in workers]
            if any(worker.name == worker_name and queue_name in worker.queue_names() for worker in workers):
                print(
                    f"runtime_readiness=worker status=ready name={worker_name} queue={queue_name}",
                    flush=True,
                )
                return
        except Exception as exc:
            last_workers = [f"error:{exc}"]
        time.sleep(0.5)
    raise RuntimeBoundaryError(
        "worker_readiness",
        f"Timed out waiting for worker {worker_name}; observed={last_workers}",
    )


def frontend_command(host: str, port: int) -> list[str]:
    node_command = shutil.which("node")
    node = Path(node_command) if node_command else bundled_node()
    if node is None or not node.exists():
        raise RuntimeBoundaryError("frontend_preflight", "No Node.js runtime found for frontend E2E.")
    next_cli = FRONTEND / "node_modules" / "next" / "dist" / "bin" / "next"
    if not next_cli.exists():
        raise RuntimeBoundaryError("frontend_preflight", "Next.js is unavailable; run npm ci in frontend.")
    return [str(node), str(next_cli), "dev", "--hostname", host, "--port", str(port)]


def run_checked(command: Sequence[str], *, boundary: str, cwd: Path, env: dict[str, str]) -> None:
    completed = subprocess.run(list(command), cwd=cwd, env=env)
    if completed.returncode != 0:
        raise RuntimeBoundaryError(boundary, f"Command exited with code {completed.returncode}: {list(command)}")


def _remove_generated_database(path: Path) -> None:
    for target in (path, Path(f"{path}-wal"), Path(f"{path}-shm")):
        if target.exists():
            target.unlink()
            print(f"runtime_cleanup=database path={target} outcome=removed", flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Start an isolated Redis/Qdrant/SQLite/backend/worker/frontend runtime and run browser E2E."
    )
    parser.add_argument("--database-path", type=Path)
    parser.add_argument("--backend-port", type=int, default=0)
    parser.add_argument("--frontend-port", type=int, default=0)
    parser.add_argument("--redis-port", type=int, default=0)
    parser.add_argument("--qdrant-port", type=int, default=0)
    parser.add_argument("--startup-timeout", type=float, default=120)
    parser.add_argument("--redis-image", default=DEFAULT_REDIS_IMAGE)
    parser.add_argument("--qdrant-image", default=DEFAULT_QDRANT_IMAGE)
    parser.add_argument("--run-token", help=argparse.SUPPRESS)
    parser.add_argument("--keep-runtime-data", action="store_true")
    parser.add_argument("--strict", action="store_true", help="Fail when any runtime/browser prerequisite is missing.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.strict and not has_playwright():
        print("demo_e2e_status=skipped reason=PLAYWRIGHT_NOT_INSTALLED")
        print("hint=Install @playwright/test and browser binaries, then rerun scripts/run_demo_e2e.py.")
        return 0

    generated_database = args.database_path is None
    identity = build_runtime_identity(
        token=args.run_token,
        database_path=args.database_path,
    )
    owned = OwnedRuntime()
    manifest: dict[str, object] | None = None
    result = 1
    try:
        ensure_showcase_database_path(identity.database_path)
        ports = resolve_ports(args.frontend_port, args.backend_port, args.redis_port, args.qdrant_port)
        backend_env, frontend_env = build_runtime_environments(identity, ports)
        manifest = {
            "token": identity.token,
            "provider_mode": "demo",
            "frontend_url": ports.frontend_url,
            "backend_url": ports.backend_url,
            "redis_url": ports.redis_url,
            "qdrant_url": ports.qdrant_url,
            "database_path": str(identity.database_path),
            "queue_name": identity.queue_name,
            "qdrant_collection": identity.qdrant_collection,
            "worker_name": identity.worker_name,
            "redis_container": identity.redis_container,
            "qdrant_container": identity.qdrant_container,
        }
        print(f"runtime_manifest={json.dumps(manifest, ensure_ascii=False, sort_keys=True)}", flush=True)
        print("provider_disclosure=DEMO_MODE=true synthetic outputs only; no real provider pass is claimed.", flush=True)

        require_playwright()
        require_docker()
        owned.start_container("redis", identity.redis_container, args.redis_image, ports.redis, 6379)
        owned.start_container("qdrant", identity.qdrant_container, args.qdrant_image, ports.qdrant, 6333)
        wait_redis(ports.redis_url, timeout=args.startup_timeout)
        ensure_qdrant_collection(
            ports.qdrant_url,
            identity.qdrant_collection,
            timeout=args.startup_timeout,
        )

        identity.database_path.parent.mkdir(parents=True, exist_ok=True)
        run_checked(
            [
                sys.executable,
                "scripts/seed_demo_data.py",
                "--database-path",
                str(identity.database_path),
                "--reset",
            ],
            boundary="database_seed",
            cwd=ROOT,
            env=backend_env,
        )

        backend = owned.start_process(
            "backend",
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--app-dir",
                "backend",
                "--host",
                LOOPBACK_HOST,
                "--port",
                str(ports.backend),
            ],
            cwd=ROOT,
            env=backend_env,
        )
        wait_url(
            f"{ports.backend_url}/health",
            timeout=args.startup_timeout,
            boundary="backend_readiness",
            process=backend,
        )

        worker = owned.start_process(
            "worker",
            [sys.executable, "-m", "app.worker"],
            cwd=BACKEND,
            env=backend_env,
        )
        wait_worker(
            ports.redis_url,
            queue_name=identity.queue_name,
            worker_name=identity.worker_name,
            timeout=args.startup_timeout,
            process=worker,
        )

        frontend = owned.start_process(
            "frontend",
            frontend_command(LOOPBACK_HOST, ports.frontend),
            cwd=FRONTEND,
            env=frontend_env,
        )
        wait_url(
            f"{ports.frontend_url}/workbench",
            timeout=args.startup_timeout,
            boundary="frontend_readiness",
            process=frontend,
        )
        prewarm_frontend_routes(
            ports.frontend_url,
            timeout=args.startup_timeout,
            process=frontend,
        )

        completed = subprocess.run(
            [sys.executable, "scripts/check_e2e.py", "--run-browser", "--strict"],
            cwd=ROOT,
            env=frontend_env,
        )
        result = completed.returncode
        print(
            f"strict_e2e_status={'passed' if result == 0 else 'failed'} exit_code={result}",
            flush=True,
        )
    except RuntimeBoundaryError as exc:
        print(
            f"runtime_status=failed boundary={exc.boundary} error={exc}",
            file=sys.stderr,
            flush=True,
        )
        result = 1
    finally:
        owned.close()
        if generated_database and not args.keep_runtime_data:
            _remove_generated_database(identity.database_path)
        if manifest is not None:
            print(
                "runtime_manifest_final="
                f"{json.dumps(finalize_runtime_manifest(manifest, result), ensure_ascii=False, sort_keys=True)}",
                flush=True,
            )
    return result


if __name__ == "__main__":
    raise SystemExit(main())
