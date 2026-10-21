from __future__ import annotations

import argparse
import json
from pathlib import Path
import sqlite3


REQUIRED_TABLE_COUNTS = {
    "knowledge_spaces": 1,
    "documents": 1,
    "sources": 4,
    "source_revisions": 4,
    "multimodal_chunks": 9,
    "citation_locators": 9,
    "transcript_segments": 6,
    "visual_frames": 3,
    "media_assets": 6,
    "ingestion_jobs": 4,
    "job_events": 12,
    "qa_logs": 2,
    "chat_sessions": 1,
    "chat_messages": 4,
    "learning_cards": 1,
    "knowledge_points": 3,
    "quiz_questions": 3,
    "learning_notes": 1,
    "learning_logs": 1,
    "version_learning_packages": 1,
}

REQUIRED_SOURCE_TYPES = {"image", "audio", "video", "code_repository"}
REQUIRED_JOB_STATUSES = {"completed", "running", "failed"}
REQUIRED_QA_STATUSES = {"grounded", "insufficient_context"}


def table_count(connection: sqlite3.Connection, table: str) -> int:
    return int(connection.execute(f"select count(*) from {table}").fetchone()[0])


def grouped_counts(connection: sqlite3.Connection, table: str, column: str) -> dict[str, int]:
    rows = connection.execute(f"select {column}, count(*) from {table} group by {column}").fetchall()
    return {str(key): int(value) for key, value in rows}


def validate_json_objects(connection: sqlite3.Connection, failures: list[str]) -> None:
    rows = connection.execute("select id, locator_json from citation_locators").fetchall()
    for locator_id, raw in rows:
        try:
            value = json.loads(raw or "{}")
        except json.JSONDecodeError as exc:
            failures.append(f"citation_locators[{locator_id}] locator_json is invalid JSON: {exc}")
            continue
        if not isinstance(value, dict) or not value:
            failures.append(f"citation_locators[{locator_id}] locator_json must be a non-empty object")


def main() -> None:
    parser = argparse.ArgumentParser(description="Check whether the local V4.2 demo database is ready.")
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
        source_counts = grouped_counts(connection, "sources", "source_type")
        job_status_counts = grouped_counts(connection, "ingestion_jobs", "status")
        qa_status_counts = grouped_counts(connection, "qa_logs", "retrieval_status")
        print(f"source_types={source_counts}")
        print(f"job_statuses={job_status_counts}")
        print(f"qa_statuses={qa_status_counts}")
        missing_sources = REQUIRED_SOURCE_TYPES.difference(source_counts)
        missing_jobs = REQUIRED_JOB_STATUSES.difference(job_status_counts)
        missing_qa = REQUIRED_QA_STATUSES.difference(qa_status_counts)
        if missing_sources:
            failures.append(f"Missing demo source types: {sorted(missing_sources)}")
        if missing_jobs:
            failures.append(f"Missing demo task statuses: {sorted(missing_jobs)}")
        if missing_qa:
            failures.append(f"Missing demo QA statuses: {sorted(missing_qa)}")
        validate_json_objects(connection, failures)

    if failures:
        print("Demo readiness check failed:")
        for failure in failures:
            print(f"- {failure}")
        raise SystemExit(1)
    print(f"Demo readiness check passed: {database}")


if __name__ == "__main__":
    main()
