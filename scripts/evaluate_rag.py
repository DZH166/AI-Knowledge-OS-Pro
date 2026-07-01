from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import sqlite3
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DEMO_DATABASE = ROOT / "backend" / "data" / "demo_showcase.db"


@dataclass
class EvaluationResult:
    qa_logs: int
    grounded_answers: int
    citation_count: int
    used_citation_count: int
    related_chunk_count: int
    timestamp_citation_count: int
    multimodal_chunk_count: int
    citation_locator_count: int
    failures: list[str]

    @property
    def passed(self) -> bool:
        return not self.failures


def parse_json_list(raw: str | None, *, field: str, qa_id: int, failures: list[str]) -> list[dict[str, Any]] | list[str]:
    if not raw:
        failures.append(f"qa_logs[{qa_id}].{field} is empty")
        return []
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        failures.append(f"qa_logs[{qa_id}].{field} is invalid JSON: {exc}")
        return []
    if not isinstance(value, list):
        failures.append(f"qa_logs[{qa_id}].{field} must be a list")
        return []
    return value


def count_table(connection: sqlite3.Connection, table: str) -> int:
    try:
        return int(connection.execute(f"select count(*) from {table}").fetchone()[0])
    except sqlite3.Error as exc:
        raise SystemExit(f"Missing or unreadable table `{table}`: {exc}") from exc


def evaluate_demo_database(database: Path) -> EvaluationResult:
    if not database.exists():
        raise SystemExit(f"Demo database is missing: {database}")

    failures: list[str] = []
    with sqlite3.connect(database) as connection:
        connection.row_factory = sqlite3.Row
        qa_rows = list(connection.execute("select * from qa_logs order by id"))
        multimodal_chunk_count = count_table(connection, "multimodal_chunks")
        citation_locator_count = count_table(connection, "citation_locators")

    grounded_answers = 0
    citation_count = 0
    used_citation_count = 0
    related_chunk_count = 0
    timestamp_citation_count = 0

    if not qa_rows:
        failures.append("No QA logs found for demo RAG evaluation.")

    if multimodal_chunk_count <= 0:
        failures.append("No multimodal chunks found.")
    if citation_locator_count <= 0:
        failures.append("No citation locators found.")

    for row in qa_rows:
        qa_id = int(row["id"])
        if row["runtime_mode"] != "demo":
            failures.append(f"qa_logs[{qa_id}] runtime_mode is {row['runtime_mode']!r}, expected 'demo'")
        if row["retrieval_status"] == "grounded":
            grounded_answers += 1
        else:
            failures.append(f"qa_logs[{qa_id}] retrieval_status is {row['retrieval_status']!r}, expected 'grounded'")

        citations = parse_json_list(row["citations_json"], field="citations_json", qa_id=qa_id, failures=failures)
        used_ids = parse_json_list(
            row["used_citation_ids_json"],
            field="used_citation_ids_json",
            qa_id=qa_id,
            failures=failures,
        )
        related_chunks = parse_json_list(
            row["related_chunks_json"],
            field="related_chunks_json",
            qa_id=qa_id,
            failures=failures,
        )

        citation_count += len(citations)
        used_citation_count += len(used_ids)
        related_chunk_count += len(related_chunks)

        citation_ids = {
            str(item.get("citation_id"))
            for item in citations
            if isinstance(item, dict) and item.get("citation_id") is not None
        }
        for citation_id in used_ids:
            normalized = str(citation_id).strip("[]")
            if normalized not in citation_ids:
                failures.append(f"qa_logs[{qa_id}] used citation {citation_id!r} has no matching citation")
            if f"[{normalized}]" not in row["answer"]:
                failures.append(f"qa_logs[{qa_id}] answer does not mention used citation [{normalized}]")

        for item in citations:
            if not isinstance(item, dict):
                failures.append(f"qa_logs[{qa_id}] citation entry is not an object")
                continue
            source_type = item.get("source_type")
            if source_type in {"audio", "video"}:
                if isinstance(item.get("start_ms"), int) and isinstance(item.get("end_ms"), int):
                    timestamp_citation_count += 1
                else:
                    failures.append(f"qa_logs[{qa_id}] media citation is missing integer start_ms/end_ms")
            if not item.get("content_preview"):
                failures.append(f"qa_logs[{qa_id}] citation is missing content_preview")

        for item in related_chunks:
            if not isinstance(item, dict):
                failures.append(f"qa_logs[{qa_id}] related chunk entry is not an object")
                continue
            if not item.get("content"):
                failures.append(f"qa_logs[{qa_id}] related chunk is missing content")

    if citation_count <= 0:
        failures.append("No citations found in QA logs.")
    if used_citation_count <= 0:
        failures.append("No used citations found in QA logs.")
    if related_chunk_count <= 0:
        failures.append("No related chunks found in QA logs.")
    if timestamp_citation_count <= 0:
        failures.append("No audio/video timestamp citations found.")

    return EvaluationResult(
        qa_logs=len(qa_rows),
        grounded_answers=grounded_answers,
        citation_count=citation_count,
        used_citation_count=used_citation_count,
        related_chunk_count=related_chunk_count,
        timestamp_citation_count=timestamp_citation_count,
        multimodal_chunk_count=multimodal_chunk_count,
        citation_locator_count=citation_locator_count,
        failures=failures,
    )


def print_report(result: EvaluationResult, database: Path) -> None:
    print("rag_evaluation_mode=demo")
    print(f"database={database}")
    print(f"qa_logs={result.qa_logs}")
    print(f"grounded_answers={result.grounded_answers}")
    print(f"citations={result.citation_count}")
    print(f"used_citations={result.used_citation_count}")
    print(f"related_chunks={result.related_chunk_count}")
    print(f"timestamp_citations={result.timestamp_citation_count}")
    print(f"multimodal_chunks={result.multimodal_chunk_count}")
    print(f"citation_locators={result.citation_locator_count}")
    if result.failures:
        print("result=failed")
        print("failures:")
        for failure in result.failures:
            print(f"- {failure}")
        raise SystemExit(1)
    print("result=passed")
    print("note=Demo evaluation checks deterministic seeded evidence and citation plumbing; it does not measure real LLM quality.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate demo RAG citation plumbing without provider calls.")
    parser.add_argument("--demo", action="store_true", help="Evaluate the isolated synthetic demo database.")
    parser.add_argument("--database-path", type=Path, default=DEFAULT_DEMO_DATABASE)
    args = parser.parse_args()

    if not args.demo:
        raise SystemExit("Only --demo evaluation is implemented. Real provider quality evaluation is planned for V4.0.")

    database = args.database_path.resolve()
    result = evaluate_demo_database(database)
    print_report(result, database)


if __name__ == "__main__":
    main()
