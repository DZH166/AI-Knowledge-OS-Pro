from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
DEMO_DB = BACKEND / "data" / "demo_showcase.db"


def run(command: list[str], *, env: dict[str, str] | None = None) -> None:
    print(">", " ".join(command))
    subprocess.run(command, cwd=ROOT, env=env, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare local services and synthetic data for the V3.8 demo.")
    parser.add_argument("--skip-docker", action="store_true", help="Do not run docker compose up -d.")
    parser.add_argument("--reset", action="store_true", help="Recreate the synthetic demo database.")
    args = parser.parse_args()

    (BACKEND / "data").mkdir(parents=True, exist_ok=True)
    (BACKEND / "storage").mkdir(parents=True, exist_ok=True)

    if not args.skip_docker:
        run(["docker", "compose", "up", "-d", "redis", "qdrant"])
    run([sys.executable, "scripts/seed_demo_data.py", "--database-path", str(DEMO_DB), *(["--reset"] if args.reset else [])])
    run([sys.executable, "scripts/check_demo_ready.py", "--database-path", str(DEMO_DB)])

    print("")
    print("Demo is prepared. Start the API with:")
    print(f"$env:DATABASE_URL='sqlite:///{DEMO_DB.as_posix()}'")
    print("$env:DEMO_MODE='true'")
    print("python -m uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000")
    print("")
    print("Then start the frontend:")
    print("cd frontend")
    print("$env:NEXT_PUBLIC_API_BASE_URL='http://127.0.0.1:8000'")
    print("npm run dev")


if __name__ == "__main__":
    main()
