from __future__ import annotations

import argparse
from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
DEMO_DB = ROOT / ".pytest_tmp" / "v4_5_demo_showcase.db"
RAG_EVAL_REPORT = ROOT / ".pytest_tmp" / "v4_5_rag_eval_report.json"
DEFAULT_VERSION = "V4.5"
REPORT_PATH = "docs/v4_5_quality_gate_report.md"


@dataclass
class GateResult:
    name: str
    status: str
    duration_sec: float
    next_step: str
    failure_reason: str = ""


RESULTS: list[GateResult] = []


def run(
    command: list[str],
    *,
    cwd: Path = ROOT,
    env: dict[str, str] | None = None,
    name: str | None = None,
    next_step: str = "Review the command output above and rerun this gate after fixing the reported failure.",
) -> None:
    gate_name = name or " ".join(str(part) for part in command)
    print(">", " ".join(str(part) for part in command), flush=True)
    started = time.perf_counter()
    try:
        subprocess.run([str(part) for part in command], cwd=cwd, env=env, check=True)
    except subprocess.CalledProcessError as exc:
        duration = time.perf_counter() - started
        result = GateResult(
            name=gate_name,
            status="failed",
            duration_sec=duration,
            failure_reason=f"exit_code={exc.returncode}",
            next_step=next_step,
        )
        RESULTS.append(result)
        print_gate_result(result)
        raise
    duration = time.perf_counter() - started
    result = GateResult(name=gate_name, status="passed", duration_sec=duration, next_step="No action required.")
    RESULTS.append(result)
    print_gate_result(result)


def record_skipped(name: str, reason: str) -> None:
    result = GateResult(name=name, status="skipped", duration_sec=0.0, failure_reason=reason, next_step="Run without --skip-frontend before a frontend release.")
    RESULTS.append(result)
    print_gate_result(result)


def print_gate_result(result: GateResult) -> None:
    print(
        "gate={name} status={status} duration_sec={duration:.2f} failure_reason={reason} next_step={next_step} report_path={report}".format(
            name=result.name,
            status=result.status,
            duration=result.duration_sec,
            reason=result.failure_reason or "-",
            next_step=result.next_step,
            report=REPORT_PATH,
        ),
        flush=True,
    )


def bundled_node() -> Path | None:
    candidates = [
        Path.home() / ".cache" / "codex-runtimes" / "codex-primary-runtime" / "dependencies" / "node" / "bin" / "node.exe",
        Path.home() / ".cache" / "codex-runtimes" / "codex-primary-runtime" / "dependencies" / "node" / "bin" / "node",
        Path.home() / ".cache" / "codex-runtimes" / "codex-primary-runtime" / "dependencies" / "node" / "node.exe",
        Path.home() / ".cache" / "codex-runtimes" / "codex-primary-runtime" / "dependencies" / "node" / "node",
    ]
    return next((path for path in candidates if path.exists()), None)


def frontend_typecheck() -> None:
    npm = shutil.which("npm")
    if npm:
        run([npm, "run", "typecheck"], cwd=FRONTEND, name="frontend typecheck")
        return
    node = bundled_node()
    if node is None:
        raise SystemExit("No npm or bundled Node runtime found for frontend typecheck.")
    run([str(node), "node_modules/typescript/bin/tsc", "--noEmit"], cwd=FRONTEND, name="frontend typecheck")


def frontend_build() -> None:
    npm = shutil.which("npm")
    if npm:
        run([npm, "run", "build"], cwd=FRONTEND, name="frontend build")
        return
    node = bundled_node()
    if node is None:
        raise SystemExit("No npm or bundled Node runtime found for frontend build.")
    run([str(node), "node_modules/next/dist/bin/next", "build"], cwd=FRONTEND, name="frontend build")


def quick() -> None:
    run([sys.executable, "scripts/check_encoding.py"], name="encoding")
    run([sys.executable, "scripts/check_version.py"], name="version")
    run([sys.executable, "scripts/check_docs_links.py"], name="docs links")
    run([sys.executable, "scripts/check_readme_assets.py"], name="README assets")
    run([sys.executable, "scripts/check_frontend_smoke.py"], name="frontend smoke")
    run([sys.executable, "scripts/check_e2e.py"], name="E2E scaffolding")


def demo() -> None:
    DEMO_DB.parent.mkdir(parents=True, exist_ok=True)
    run([sys.executable, "scripts/seed_demo_data.py", "--database-path", str(DEMO_DB), "--reset"], name="demo seed")
    run([sys.executable, "scripts/check_demo_ready.py", "--database-path", str(DEMO_DB)], name="demo readiness")
    run(
        [
            sys.executable,
            "scripts/evaluate_rag.py",
            "--demo",
            "--database-path",
            str(DEMO_DB),
            "--output",
            str(RAG_EVAL_REPORT),
        ],
        name="demo RAG evaluation",
    )
    run([sys.executable, "scripts/check_full_regression.py", "--database-path", str(DEMO_DB)], name="full regression")


def release() -> None:
    run([sys.executable, "scripts/check_secrets.py"], name="secret scan")
    run([sys.executable, "scripts/check_repo_clean.py"], name="repo clean")
    run([sys.executable, "scripts/release.py", "--version", DEFAULT_VERSION, "--dry-run"], name="release dry-run")


def observability() -> None:
    run(
        [
            sys.executable,
            "-m",
            "pytest",
            "backend/tests/test_v4_4_observability.py",
            "backend/tests/test_citation_jump_contracts.py",
        ],
        name="V4.5 observability and citation contracts",
    )


def provider_eval() -> None:
    run([sys.executable, "scripts/evaluate_providers.py", "--dry-run"], name="provider eval dry-run")


def e2e() -> None:
    run([sys.executable, "scripts/check_e2e.py"], name="E2E scaffolding")
    run([sys.executable, "scripts/run_demo_e2e.py"], name="optional demo browser E2E")


def live_e2e() -> None:
    run([sys.executable, "scripts/check_e2e.py", "--run-browser", "--strict"], name="strict browser E2E")


def full(*, skip_frontend: bool = False) -> None:
    run([sys.executable, "-m", "compileall", "backend/app", "scripts"], name="backend compileall")
    run([sys.executable, "-m", "pytest"], name="backend pytest")
    observability()
    if skip_frontend:
        record_skipped("frontend typecheck", "--skip-frontend requested")
        record_skipped("frontend build", "--skip-frontend requested")
    else:
        frontend_typecheck()
        frontend_build()
    quick()
    provider_eval()
    e2e()
    demo()
    release()


def print_summary(selected: str) -> None:
    print("quality_gate_summary=begin")
    for result in RESULTS:
        print(
            "| {name} | {status} | {duration:.2f}s | {reason} | {next_step} |".format(
                name=result.name,
                status=result.status,
                duration=result.duration_sec,
                reason=result.failure_reason or "-",
                next_step=result.next_step,
            )
        )
    print(f"mode={selected}")
    print(f"report_path={REPORT_PATH}")
    print("quality_gate_summary=end")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run AI Knowledge OS Pro quality gates.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--quick", action="store_true", help="Run lightweight local static checks.")
    mode.add_argument("--demo", action="store_true", help="Run synthetic demo readiness/RAG/full-regression checks.")
    mode.add_argument("--release", action="store_true", help="Run release-safety checks.")
    mode.add_argument("--observability", action="store_true", help="Run V4.5 observability and citation contract tests.")
    mode.add_argument("--provider-eval", action="store_true", help="Run provider readiness dry-run without external calls.")
    mode.add_argument("--e2e", action="store_true", help="Run optional browser E2E scaffolding checks.")
    mode.add_argument("--live-e2e", action="store_true", help="Run strict live browser E2E; missing browser runtime fails.")
    mode.add_argument("--full", action="store_true", help="Run backend, frontend, quick, demo and release gates.")
    parser.add_argument(
        "--skip-frontend",
        action="store_true",
        help="When used with --full, skip frontend typecheck/build. When used alone, run full mode without frontend.",
    )
    args = parser.parse_args()

    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    selected = "quick"
    try:
        if args.demo:
            demo()
            selected = "demo"
        elif args.release:
            release()
            selected = "release"
        elif args.observability:
            observability()
            selected = "observability"
        elif args.provider_eval:
            provider_eval()
            selected = "provider-eval"
        elif args.e2e:
            e2e()
            selected = "e2e"
        elif args.live_e2e:
            live_e2e()
            selected = "live-e2e"
        elif args.full or args.skip_frontend:
            full(skip_frontend=args.skip_frontend)
            selected = "full-skip-frontend" if args.skip_frontend else "full"
        else:
            quick()
            selected = "quick"
    finally:
        print_summary(selected)
    print(f"check_all={selected}")
    print("result=passed")


if __name__ == "__main__":
    main()
