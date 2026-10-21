from __future__ import annotations

import argparse
from pathlib import Path
import sqlite3


REQUIRED_TABLE_COUNTS = {
    "knowledge_spaces": 1,
    "documents": 1,
    "sources": 3,
    "ingestion_jobs": 3,
    "qa_logs": 1,
    "learning_cards": 1,
    "learning_logs": 1,
}


def table_count(connection: sqlite3.Connection, table: str) -> int:
    return int(connection.execute(f"select count(*) from {table}").fetchone()[0])


def main() -> None:
    parser = argparse.ArgumentParser(description="Check whether the local V3.7 demo database is ready.")
    parser.add_argument("--database-path", type=Path, default=Path("backend/data/demo_showcase.db"))
    args = parser.parse_args()

    database = args.database_path.resolve()
    if not database.exists():
        raise SystemExit(f"Demo database is missing: {database}")

    failures: list[str] = []
    with sqlite3.connect(database) as connection:
        for table, minimum in REQUIRED_TABLE_COUNTS.items():
            count = table_count(connection, table)
            print(f"{table}={count}")
            if count < minimum:
                failures.append(f"{table} has {count}, expected at least {minimum}")

    if failures:
        print("Demo readiness check failed:")
        for failure in failures:
            print(f"- {failure}")
        raise SystemExit(1)
    print(f"Demo readiness check passed: {database}")


if __name__ == "__main__":
    main()
