from __future__ import annotations

import json
from pathlib import Path
import subprocess

import pytest

from app import worker as worker_module
from scripts import run_demo_e2e as runtime


ROOT = Path(__file__).resolve().parents[2]


def test_runtime_identity_is_run_scoped_and_resolves_the_qdrant_collection(tmp_path: Path) -> None:
    first = runtime.build_runtime_identity(root=tmp_path, token="alpha")
    second = runtime.build_runtime_identity(root=tmp_path, token="beta")

    assert first.database_path == tmp_path / ".pytest_tmp" / "v5_7_alpha_showcase_e2e.db"
    assert first.queue_name == "v5_7_alpha"
    assert first.qdrant_collection_prefix == "v5_7_alpha"
    assert first.qdrant_collection == "v5_7_alpha_v2_openai_compatible_1536_chunks"
    assert first.redis_container == "v5-7-alpha-redis"
    assert first.qdrant_container == "v5-7-alpha-qdrant"
    assert first.worker_name == "v5-7-alpha-worker"
    assert runtime.worker_names(first) == (
        "v5-7-alpha-worker-1",
        "v5-7-alpha-worker-2",
        "v5-7-alpha-worker-3",
    )
    assert first != second


def test_runtime_environments_share_exact_isolated_origins_and_resources(tmp_path: Path) -> None:
    identity = runtime.build_runtime_identity(root=tmp_path, token="contract")
    ports = runtime.RuntimePorts(frontend=43101, backend=43102, redis=43103, qdrant=43104)

    backend_env, frontend_env = runtime.build_runtime_environments(
        identity,
        ports,
        base_env={"PATH": "runtime-path"},
    )

    assert backend_env["DATABASE_URL"] == f"sqlite:///{identity.database_path.as_posix()}"
    assert backend_env["REDIS_URL"] == "redis://127.0.0.1:43103/0"
    assert backend_env["TASK_QUEUE_NAME"] == identity.queue_name
    assert backend_env["WORKER_QUEUES"] == identity.queue_name
    assert backend_env["WORKER_NAME"] == identity.worker_name
    assert backend_env["QDRANT_URL"] == "http://127.0.0.1:43104"
    assert backend_env["QDRANT_COLLECTION_PREFIX"] == identity.qdrant_collection_prefix
    assert backend_env["BACKEND_CORS_ORIGINS"] == json.dumps(["http://127.0.0.1:43101"])
    assert backend_env["DEMO_MODE"] == "true"
    assert "OPENAI_API_KEY" not in backend_env

    assert frontend_env["NEXT_PUBLIC_API_BASE_URL"] == "http://127.0.0.1:43102"
    assert frontend_env["E2E_BASE_URL"] == "http://127.0.0.1:43101"
    assert frontend_env["E2E_SKIP_WEBSERVER"] == "1"
    assert frontend_env["E2E_TEST_TIMEOUT_MS"] == "60000"
    assert frontend_env["E2E_WORKERS"] == "4"


def test_final_runtime_manifest_contains_a_machine_readable_verdict() -> None:
    manifest = {"token": "contract", "provider_mode": "demo"}

    assert runtime.finalize_runtime_manifest(manifest, 0) == {
        **manifest,
        "final_test_result": {"status": "passed", "exit_code": 0},
    }
    assert runtime.finalize_runtime_manifest(manifest, 7)["final_test_result"] == {
        "status": "failed",
        "exit_code": 7,
    }


def test_docker_preflight_reports_the_daemon_boundary() -> None:
    def unavailable(*_args, **_kwargs):
        return subprocess.CompletedProcess(
            args=["docker", "info"],
            returncode=1,
            stdout="",
            stderr="failed to connect to the docker API",
        )

    with pytest.raises(RuntimeError, match="Docker daemon is unavailable"):
        runtime.require_docker(run=unavailable)


def test_container_cleanup_stops_only_recorded_names_in_reverse_order() -> None:
    calls: list[list[str]] = []

    def record(command, **_kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(args=command, returncode=0, stdout="", stderr="")

    runtime.stop_owned_containers(
        ["v5-3-owned-redis", "v5-3-owned-qdrant"],
        run=record,
    )

    assert calls == [
        ["docker", "stop", "--time", "10", "v5-3-owned-qdrant"],
        ["docker", "stop", "--time", "10", "v5-3-owned-redis"],
    ]


def test_worker_builder_applies_the_run_scoped_name(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class RecordingWorker:
        def __init__(self, queues, *, connection, name=None) -> None:
            captured.update(queues=queues, connection=connection, name=name)

    monkeypatch.setattr(worker_module, "SimpleWorker", RecordingWorker)
    queues = [object()]
    connection = object()

    built = worker_module.build_worker(queues, connection=connection, worker_name="v5-3-owned-worker")

    assert isinstance(built, RecordingWorker)
    assert captured == {"queues": queues, "connection": connection, "name": "v5-3-owned-worker"}


def test_frontend_strict_contract_requires_api_base_and_disables_server_reuse() -> None:
    runner = (ROOT / "frontend" / "e2e" / "run-optional-e2e.mjs").read_text(encoding="utf-8")
    config = (ROOT / "frontend" / "playwright.config.ts").read_text(encoding="utf-8")

    assert "NEXT_PUBLIC_API_BASE_URL_MISSING" in runner
    assert "E2E_FRONTEND_ORIGIN_MISSING" in runner
    assert "process.env.NEXT_PUBLIC_API_BASE_URL" in runner
    assert "--hostname" in runner
    assert "--port" in runner
    assert "taskkill" in runner
    assert "CHROME_LOG_FILE" in runner
    assert "webServer: undefined" in config
    assert "reuseExistingServer" not in config
    assert "expectTimeout" in config
    assert "E2E_WORKERS" in config


def test_frontend_prewarm_covers_parallel_e2e_route_groups(monkeypatch) -> None:
    requested: list[str] = []

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            return None

    class RunningProcess:
        @staticmethod
        def poll():
            return None

    def open_url(url: str, *, timeout: float):
        assert timeout == 30
        requested.append(url)
        return Response()

    monkeypatch.setattr(runtime, "urlopen", open_url)
    paths = ("/workbench?demo=1", "/code?source=44", "/artifacts")

    runtime.prewarm_frontend_routes(
        "http://127.0.0.1:43101",
        timeout=30,
        process=RunningProcess(),
        paths=paths,
    )

    assert requested == [f"http://127.0.0.1:43101{path}" for path in paths]
    assert "/code?source=44" in runtime.FRONTEND_PREWARM_PATHS
    assert "/system/observability" in runtime.FRONTEND_PREWARM_PATHS
