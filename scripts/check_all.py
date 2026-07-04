from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
DEMO_DB = ROOT / ".pytest_tmp" / "v4_3_demo_showcase.db"
DEFAULT_VERSION = "V4.3"


def run(command: list[str], *, cwd: Path = ROOT, env: dict[str, str] | None = None) -> None:
    print(">", " ".join(str(part) for part in command), flush=True)
    subprocess.run([str(part) for part in command], cwd=cwd, env=env, check=True)


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
        run([npm, "run", "typecheck"], cwd=FRONTEND)
        return
    node = bundled_node()
    if node is None:
        raise SystemExit("No npm or bundled Node runtime found for frontend typecheck.")
    run([str(node), "node_modules/typescript/bin/tsc", "--noEmit"], cwd=FRONTEND)


def frontend_build() -> None:
    npm = shutil.which("npm")
    if npm:
        run([npm, "run", "build"], cwd=FRONTEND)
        return
    node = bundled_node()
    if node is None:
        raise SystemExit("No npm or bundled Node runtime found for frontend build.")
    run([str(node), "node_modules/next/dist/bin/next", "build"], cwd=FRONTEND)


def quick() -> None:
    run([sys.executable, "scripts/check_encoding.py"])
    run([sys.executable, "scripts/check_version.py"])
    run([sys.executable, "scripts/check_docs_links.py"])
    run([sys.executable, "scripts/check_readme_assets.py"])
    run([sys.executable, "scripts/check_frontend_smoke.py"])


def demo() -> None:
    DEMO_DB.parent.mkdir(parents=True, exist_ok=True)
    run([sys.executable, "scripts/seed_demo_data.py", "--database-path", str(DEMO_DB), "--reset"])
    run([sys.executable, "scripts/check_demo_ready.py", "--database-path", str(DEMO_DB)])
    run([sys.executable, "scripts/evaluate_rag.py", "--demo", "--database-path", str(DEMO_DB)])
    run([sys.executable, "scripts/check_full_regression.py", "--database-path", str(DEMO_DB)])


def release() -> None:
    run([sys.executable, "scripts/check_secrets.py"])
    run([sys.executable, "scripts/check_repo_clean.py"])
    run([sys.executable, "scripts/release.py", "--version", DEFAULT_VERSION, "--dry-run"])


def full() -> None:
    run([sys.executable, "-m", "compileall", "backend/app", "scripts"])
    run([sys.executable, "-m", "pytest"])
    frontend_typecheck()
    frontend_build()
    quick()
    demo()
    release()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run AI Knowledge OS Pro quality gates.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--quick", action="store_true", help="Run lightweight local static checks.")
    mode.add_argument("--demo", action="store_true", help="Run synthetic demo readiness/RAG/full-regression checks.")
    mode.add_argument("--release", action="store_true", help="Run release-safety checks.")
    mode.add_argument("--full", action="store_true", help="Run backend, frontend, quick, demo and release gates.")
    args = parser.parse_args()

    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    if args.demo:
        demo()
        selected = "demo"
    elif args.release:
        release()
        selected = "release"
    elif args.full:
        full()
        selected = "full"
    else:
        quick()
        selected = "quick"
    print(f"check_all={selected}")
    print("result=passed")


if __name__ == "__main__":
    main()
