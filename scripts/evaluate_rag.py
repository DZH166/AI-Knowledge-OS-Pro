from __future__ import annotations

import argparse
from collections import Counter
from contextlib import closing, redirect_stdout
from dataclasses import dataclass
import io
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
DEFAULT_DEMO_DATABASE = ROOT / "backend" / "data" / "demo_showcase.db"


@dataclass
class EvaluationResult:
    qa_logs: int
    grounded_answers: int
    refusal_answers: int
    citation_count: int
    valid_citation_count: int
    used_citation_count: int
    related_chunk_count: int
    timestamp_citation_count: int
    multimodal_chunk_count: int
    citation_locator_count: int
    valid_locator_count: int
    code_locator_count: int
    citation_source_type_counts: dict[str, int]
    multimodal_source_type_counts: dict[str, int]
    locator_shape_counts: dict[str, int]
    qa_traces: list[dict[str, Any]]
    retrieval_hit_rate: float
    failures: list[str]

    @property
    def passed(self) -> bool:
        return not self.failures


def parse_json_list(raw: str | None, *, field: str, qa_id: int, failures: list[str]) -> list[Any]:
    if raw is None:
        failures.append(f"qa_logs[{qa_id}].{field} is null")
        return []
    try:
        value = json.loads(raw or "[]")
    except json.JSONDecodeError as exc:
        failures.append(f"qa_logs[{qa_id}].{field} is invalid JSON: {exc}")
        return []
    if not isinstance(value, list):
        failures.append(f"qa_logs[{qa_id}].{field} must be a list")
        return []
    return value


def parse_json_dict(raw: str | None, *, label: str, failures: list[str]) -> dict[str, Any]:
    try:
        value = json.loads(raw or "{}")
    except json.JSONDecodeError as exc:
        failures.append(f"{label} is invalid JSON: {exc}")
        return {}
    if not isinstance(value, dict):
        failures.append(f"{label} must be an object")
        return {}
    return value


def count_table(connection: sqlite3.Connection, table: str) -> int:
    try:
        return int(connection.execute(f"select count(*) from {table}").fetchone()[0])
    except sqlite3.Error as exc:
        raise SystemExit(f"Missing or unreadable table `{table}`: {exc}") from exc


def count_by_column(connection: sqlite3.Connection, table: str, column: str) -> dict[str, int]:
    try:
        rows = connection.execute(f"select {column}, count(*) as item_count from {table} group by {column}")
        return {str(row[0]): int(row[1]) for row in rows if row[0] is not None}
    except sqlite3.Error as exc:
        raise SystemExit(f"Missing or unreadable column `{table}.{column}`: {exc}") from exc


def load_locator_map(
    connection: sqlite3.Connection,
    failures: list[str],
) -> tuple[dict[int, sqlite3.Row], int, int, dict[str, int]]:
    rows = list(connection.execute("select * from citation_locators order by id"))
    locator_by_chunk: dict[int, sqlite3.Row] = {}
    locator_shape_counts: Counter[str] = Counter()
    valid_locator_count = 0
    code_locator_count = 0
    for row in rows:
        locator = parse_json_dict(
            row["locator_json"],
            label=f"citation_locators[{row['id']}].locator_json",
            failures=failures,
        )
        if locator:
            valid_locator_count += 1
        if locator.get("file_path") and isinstance(locator.get("line_start"), int):
            locator_shape_counts["code_file_line"] += 1
        elif isinstance(locator.get("start_ms"), int) and isinstance(locator.get("end_ms"), int):
            locator_shape_counts["media_timestamp"] += 1
        elif locator.get("region") or locator.get("type") == "image" or locator.get("asset"):
            locator_shape_counts["image_region"] += 1
        elif locator.get("source_id"):
            locator_shape_counts["source_reference"] += 1
        else:
            locator_shape_counts["unknown"] += 1
        if row["chunk_id"] is not None:
            locator_by_chunk[int(row["chunk_id"])] = row
        if locator.get("source_type") == "code_repository":
            if locator.get("file_path") and isinstance(locator.get("line_start"), int) and isinstance(locator.get("line_end"), int):
                code_locator_count += 1
            else:
                failures.append(f"citation_locators[{row['id']}] code locator is missing file_path/line_start/line_end")
    return locator_by_chunk, valid_locator_count, code_locator_count, dict(sorted(locator_shape_counts.items()))


def validate_multimodal_locators(connection: sqlite3.Connection, failures: list[str]) -> int:
    valid = 0
    rows = list(connection.execute("select * from multimodal_chunks order by id"))
    for row in rows:
        locator = parse_json_dict(
            row["locator_json"],
            label=f"multimodal_chunks[{row['id']}].locator_json",
            failures=failures,
        )
        source_type = row["source_type"]
        if source_type in {"audio", "video"}:
            if not isinstance(locator.get("start_ms"), int) or not isinstance(locator.get("end_ms"), int):
                failures.append(f"multimodal_chunks[{row['id']}] media locator is missing start_ms/end_ms")
                continue
        elif source_type == "image":
            if not locator.get("region") and not locator.get("source_id"):
                failures.append(f"multimodal_chunks[{row['id']}] image locator is missing region/source_id")
                continue
        elif source_type == "code_repository":
            if not locator.get("file_path") or not isinstance(locator.get("line_start"), int):
                failures.append(f"multimodal_chunks[{row['id']}] code locator is missing file_path/line_start")
                continue
        valid += 1
    return valid


def evaluate_demo_database(database: Path) -> EvaluationResult:
    if not database.exists():
        raise SystemExit(f"Demo database is missing: {database}")

    failures: list[str] = []
    with closing(sqlite3.connect(database)) as connection:
        connection.row_factory = sqlite3.Row
        qa_rows = list(connection.execute("select * from qa_logs order by id"))
        multimodal_chunk_count = count_table(connection, "multimodal_chunks")
        citation_locator_count = count_table(connection, "citation_locators")
        multimodal_source_type_counts = count_by_column(connection, "multimodal_chunks", "source_type")
        locator_by_chunk, valid_locator_count, code_locator_count, locator_shape_counts = load_locator_map(
            connection,
            failures,
        )
        valid_multimodal_locators = validate_multimodal_locators(connection, failures)

    grounded_answers = 0
    refusal_answers = 0
    citation_count = 0
    valid_citation_count = 0
    used_citation_count = 0
    related_chunk_count = 0
    timestamp_citation_count = 0
    citation_source_type_counts: Counter[str] = Counter()
    qa_traces: list[dict[str, Any]] = []

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

        status = row["retrieval_status"]
        trace_source_types: Counter[str] = Counter()
        has_timestamp_citation = False
        has_code_citation = False
        if status == "grounded":
            grounded_answers += 1
            if not citations:
                failures.append(f"qa_logs[{qa_id}] grounded answer has no citations")
            if not related_chunks:
                failures.append(f"qa_logs[{qa_id}] grounded answer has no related chunks")
            if not used_ids:
                failures.append(f"qa_logs[{qa_id}] grounded answer has no used citation ids")
        elif status == "insufficient_context":
            refusal_answers += 1
            if citations or used_ids or related_chunks:
                failures.append(f"qa_logs[{qa_id}] refusal should not include citations, used ids or related chunks")
            answer = str(row["answer"]).lower()
            if "not enough" not in answer and "do not have enough" not in answer and "insufficient" not in answer:
                failures.append(f"qa_logs[{qa_id}] refusal answer should clearly explain insufficient evidence")
            qa_traces.append(
                {
                    "qa_log_id": qa_id,
                    "question": row["question"],
                    "retrieval_status": status,
                    "runtime_mode": row["runtime_mode"],
                    "citation_count": len(citations),
                    "used_citation_count": len(used_ids),
                    "related_chunk_count": len(related_chunks),
                    "source_type_counts": {},
                    "has_timestamp_citation": False,
                    "has_code_citation": False,
                }
            )
            continue
        else:
            failures.append(f"qa_logs[{qa_id}] retrieval_status is {status!r}, expected grounded or insufficient_context")
            continue

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
            if isinstance(source_type, str) and source_type:
                citation_source_type_counts[source_type] += 1
                trace_source_types[source_type] += 1
            chunk_id = item.get("chunk_id")
            if isinstance(chunk_id, int) and chunk_id in locator_by_chunk:
                valid_citation_count += 1
            else:
                failures.append(f"qa_logs[{qa_id}] citation chunk_id {chunk_id!r} has no CitationLocator")
            if source_type in {"audio", "video"}:
                if isinstance(item.get("start_ms"), int) and isinstance(item.get("end_ms"), int):
                    timestamp_citation_count += 1
                    has_timestamp_citation = True
                else:
                    failures.append(f"qa_logs[{qa_id}] media citation is missing integer start_ms/end_ms")
            if source_type == "code_repository":
                has_code_citation = True
                if not item.get("file_path") or not isinstance(item.get("line_start"), int):
                    failures.append(f"qa_logs[{qa_id}] code citation is missing file_path/line_start")
            if not item.get("content_preview"):
                failures.append(f"qa_logs[{qa_id}] citation is missing content_preview")

        for item in related_chunks:
            if not isinstance(item, dict):
                failures.append(f"qa_logs[{qa_id}] related chunk entry is not an object")
                continue
            if not item.get("content"):
                failures.append(f"qa_logs[{qa_id}] related chunk is missing content")
            chunk_id = item.get("chunk_id")
            if isinstance(chunk_id, int) and chunk_id not in locator_by_chunk:
                failures.append(f"qa_logs[{qa_id}] related chunk {chunk_id} has no CitationLocator")

        qa_traces.append(
            {
                "qa_log_id": qa_id,
                "question": row["question"],
                "retrieval_status": status,
                "runtime_mode": row["runtime_mode"],
                "citation_count": len(citations),
                "used_citation_count": len(used_ids),
                "related_chunk_count": len(related_chunks),
                "source_type_counts": dict(sorted(trace_source_types.items())),
                "has_timestamp_citation": has_timestamp_citation,
                "has_code_citation": has_code_citation,
            }
        )

    if grounded_answers <= 0:
        failures.append("No grounded QA log found.")
    if refusal_answers <= 0:
        failures.append("No insufficient_context refusal QA log found.")
    if citation_count <= 0:
        failures.append("No citations found in grounded QA logs.")
    if used_citation_count <= 0:
        failures.append("No used citations found in grounded QA logs.")
    if related_chunk_count <= 0:
        failures.append("No related chunks found in grounded QA logs.")
    if timestamp_citation_count <= 0:
        failures.append("No audio/video timestamp citations found.")
    if code_locator_count <= 0:
        failures.append("No code repository locators found.")
    if valid_multimodal_locators < multimodal_chunk_count:
        failures.append("Not all multimodal chunks have valid source-specific locators.")

    retrieval_hit_rate = grounded_answers / max(grounded_answers + refusal_answers, 1)

    return EvaluationResult(
        qa_logs=len(qa_rows),
        grounded_answers=grounded_answers,
        refusal_answers=refusal_answers,
        citation_count=citation_count,
        valid_citation_count=valid_citation_count,
        used_citation_count=used_citation_count,
        related_chunk_count=related_chunk_count,
        timestamp_citation_count=timestamp_citation_count,
        multimodal_chunk_count=multimodal_chunk_count,
        citation_locator_count=citation_locator_count,
        valid_locator_count=valid_locator_count,
        code_locator_count=code_locator_count,
        citation_source_type_counts=dict(sorted(citation_source_type_counts.items())),
        multimodal_source_type_counts=dict(sorted(multimodal_source_type_counts.items())),
        locator_shape_counts=locator_shape_counts,
        qa_traces=qa_traces,
        retrieval_hit_rate=retrieval_hit_rate,
        failures=failures,
    )


def to_report_dict(result: EvaluationResult, database: Path, *, database_source: str = "explicit") -> dict[str, Any]:
    return {
        "mode": "demo",
        "database": str(database),
        "database_source": database_source,
        "result": "passed" if result.passed else "failed",
        "summary": {
            "qa_logs": result.qa_logs,
            "grounded_answers": result.grounded_answers,
            "refusal_answers": result.refusal_answers,
            "retrieval_hit_rate": result.retrieval_hit_rate,
            "citations": result.citation_count,
            "valid_citations": result.valid_citation_count,
            "used_citations": result.used_citation_count,
            "related_chunks": result.related_chunk_count,
            "timestamp_citations": result.timestamp_citation_count,
            "multimodal_chunks": result.multimodal_chunk_count,
            "citation_locators": result.citation_locator_count,
            "valid_locators": result.valid_locator_count,
            "code_locators": result.code_locator_count,
        },
        "coverage": {
            "citation_source_type_counts": result.citation_source_type_counts,
            "multimodal_source_type_counts": result.multimodal_source_type_counts,
            "locator_shape_counts": result.locator_shape_counts,
            "qa_traces": result.qa_traces,
        },
        "failures": result.failures,
        "boundary": (
            "Demo evaluation checks deterministic seeded retrieval status, refusal behavior, citation validity "
            "and multimodal locator plumbing; it does not measure real LLM quality."
        ),
    }


def print_report(result: EvaluationResult, database: Path, *, database_source: str = "explicit") -> None:
    print("rag_evaluation_mode=demo")
    print(f"database={database}")
    print(f"database_source={database_source}")
    print(f"qa_logs={result.qa_logs}")
    print(f"grounded_answers={result.grounded_answers}")
    print(f"refusal_answers={result.refusal_answers}")
    print(f"retrieval_hit_rate={result.retrieval_hit_rate:.2f}")
    print(f"citations={result.citation_count}")
    print(f"valid_citations={result.valid_citation_count}")
    print(f"used_citations={result.used_citation_count}")
    print(f"related_chunks={result.related_chunk_count}")
    print(f"timestamp_citations={result.timestamp_citation_count}")
    print(f"multimodal_chunks={result.multimodal_chunk_count}")
    print(f"citation_locators={result.citation_locator_count}")
    print(f"valid_locators={result.valid_locator_count}")
    print(f"code_locators={result.code_locator_count}")
    print(f"citation_source_types={json.dumps(result.citation_source_type_counts, ensure_ascii=False, sort_keys=True)}")
    print(f"multimodal_source_types={json.dumps(result.multimodal_source_type_counts, ensure_ascii=False, sort_keys=True)}")
    print(f"locator_shapes={json.dumps(result.locator_shape_counts, ensure_ascii=False, sort_keys=True)}")
    if result.failures:
        print("result=failed")
        print("failures:")
        for failure in result.failures:
            print(f"- {failure}")
        raise SystemExit(1)
    print("result=passed")
    print(
        "note=Demo evaluation checks deterministic seeded retrieval status, refusal behavior, "
        "citation validity and multimodal locator plumbing; it does not measure real LLM quality."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate demo RAG citation and locator plumbing without provider calls.")
    parser.add_argument("--demo", action="store_true", help="Evaluate a deterministic synthetic demo database.")
    parser.add_argument(
        "--database-path",
        type=Path,
        default=None,
        help="Evaluate an explicit database path. Omit it to seed a temporary, isolated showcase database.",
    )
    parser.add_argument("--fresh", action="store_true", help="Force a temporary seeded database even when a path is provided.")
    parser.add_argument("--output", type=Path, help="Optional JSON evidence report path.")
    args = parser.parse_args()

    if not args.demo:
        raise SystemExit("Only --demo evaluation is implemented. Real provider quality evaluation requires configured providers.")

    with tempfile.TemporaryDirectory(prefix="evidence-rag-eval-") as temp_raw:
        if args.fresh or args.database_path is None:
            database = Path(temp_raw) / "demo_showcase.db"
            from scripts.seed_showcase import seed

            with redirect_stdout(io.StringIO()):
                seed(database, reset=True)
            database_source = "isolated_seed"
        else:
            database = args.database_path.resolve()
            database_source = "explicit"
        result = evaluate_demo_database(database)
        if args.output:
            output = args.output.resolve()
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(
                json.dumps(
                    to_report_dict(result, database, database_source=database_source),
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            print(f"report={output}")
        print_report(result, database, database_source=database_source)


if __name__ == "__main__":
    main()
