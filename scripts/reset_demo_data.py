from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE = ROOT / "backend" / "data" / "demo_showcase.db"


def run(command: list[str]) -> None:
    print(">", " ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def ensure_demo_database_path(database: Path) -> Path:
    resolved = database.resolve()
    demo_dir = (ROOT / "backend" / "data").resolve()
    if not resolved.is_relative_to(demo_dir):
        raise SystemExit(
            "Refusing to reset a database outside backend/data. "
            f"Use the synthetic demo database location instead: {DEFAULT_DATABASE}"
        )
    if resolved.name != "demo_showcase.db":
        raise SystemExit("Refusing to reset a non-demo database. Expected demo_showcase.db.")
    return resolved


def main() -> None:
    parser = argparse.ArgumentParser(description="Reset the isolated synthetic demo database.")
    parser.add_argument("--database-path", type=Path, default=DEFAULT_DATABASE)
    args = parser.parse_args()

    database = ensure_demo_database_path(args.database_path)
    database.parent.mkdir(parents=True, exist_ok=True)

    if database.exists():
        database.unlink()
        print(f"Removed synthetic demo database: {database}", flush=True)

    run([sys.executable, "scripts/seed_demo_data.py", "--database-path", str(database), "--reset"])
    run([sys.executable, "scripts/check_demo_ready.py", "--database-path", str(database)])
    print("Demo data reset complete. The database contains labelled synthetic showcase data only.", flush=True)


if __name__ == "__main__":
    main()
