from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path
import sqlite3
import sys
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.check_frontend_smoke import evaluate_frontend  # noqa: E402

DEFAULT_DEMO_DATABASE = ROOT / "backend" / "data" / "demo_showcase.db"

REQUIRED_BACKEND_ROUTES = (
    "backend/app/api/routes_dashboard.py",
    "backend/app/api/routes_documents.py",
    "backend/app/api/routes_media.py",
    "backend/app/api/routes_code_repositories.py",
    "backend/app/api/routes_chat.py",
    "backend/app/api/routes_learning.py",
    "backend/app/api/routes_portfolio.py",
    "backend/app/api/routes_ingestion_jobs.py",
    "backend/app/api/routes_system.py",
)

REQUIRED_FRONTEND_ROUTES = (
    "/dashboard",
    "/upload",
    "/tasks",
    "/chat",
    "/system",
    "/learning",
    "/portfolio",
    "/portfolio/interview",
)

REQUIRED_SCRIPTS = (
    "scripts/setup_demo.py",
    "scripts/seed_demo_data.py",
    "scripts/check_demo_ready.py",
    "scripts/evaluate_rag.py",
    "scripts/check_frontend_smoke.py",
    "scripts/release.py",
    "scripts/check_secrets.py",
    "scripts/check_repo_clean.py",
)

REQUIRED_DOCS = (
    "README.md",
    "docs/quickstart.md",
    "docs/demo_mode.md",
    "docs/rag_evaluation.md",
    "docs/media_pipeline.md",
    "docs/task_queue_flow.md",
    "docs/citation_locator.md",
    "docs/learning_system.md",
    "docs/portfolio_system.md",
    "docs/interview_system.md",
    "docs/release_process.md",
)


@dataclass
class RegressionReport:
    database: Path
    checks: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    metrics: dict[str, int | str] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return not self.failures

    def record(self, name: str) -> None:
        self.checks.append(name)

    def fail(self, message: str) -> None:
        self.failures.append(message)


def require_paths(report: RegressionReport, paths: Iterable[str], *, label: str) -> None:
    for relative in paths:
        path = ROOT / relative
        report.record(f"{label}:{relative}")
        if not path.exists():
            report.fail(f"Missing {label} file: {relative}")


def route_to_page(route: str) -> Path:
    if route == "/":
        return ROOT / "frontend" / "app" / "page.tsx"
    return ROOT / "frontend" / "app" / route.strip("/") / "page.tsx"


def count_table(connection: sqlite3.Connection, table: str) -> int:
    return int(connection.execute(f"select count(*) from {table}").fetchone()[0])


def grouped_counts(connection: sqlite3.Connection, table: str, column: str) -> dict[str, int]:
    rows = connection.execute(f"select {column}, count(*) from {table} group by {column}").fetchall()
    return {str(key): int(value) for key, value in rows}


def check_frontend(report: RegressionReport) -> None:
    frontend = evaluate_frontend()
    report.metrics["frontend_required_routes"] = frontend.checked_routes
    report.metrics["frontend_nav_targets"] = frontend.nav_targets
    report.record("frontend:static-smoke")
    for warning in frontend.warnings:
        report.fail(f"Frontend smoke warning should be resolved before release: {warning}")
    for failure in frontend.failures:
        report.fail(f"Frontend smoke failure: {failure}")
    for route in REQUIRED_FRONTEND_ROUTES:
        page = route_to_page(route)
        report.record(f"frontend:e2e-route:{route}")
        if not page.exists():
            report.fail(f"Required V4.2 smoke route is missing: {route}")


def check_demo_database(report: RegressionReport) -> None:
    database = report.database
    report.record("demo:database-present")
    if not database.exists():
        report.fail(f"Demo database is missing: {database}")
        return

    with sqlite3.connect(database) as connection:
        connection.row_factory = sqlite3.Row
        table_minimums = {
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
            "learning_cards": 1,
            "knowledge_points": 3,
            "quiz_questions": 3,
            "learning_notes": 1,
            "version_learning_packages": 1,
        }
        for table, minimum in table_minimums.items():
            report.record(f"demo:table:{table}")
            count = count_table(connection, table)
            report.metrics[table] = count
            if count < minimum:
                report.fail(f"Demo table {table} has {count}, expected at least {minimum}")

        source_counts = grouped_counts(connection, "sources", "source_type")
        job_statuses = grouped_counts(connection, "ingestion_jobs", "status")
        qa_statuses = grouped_counts(connection, "qa_logs", "retrieval_status")
        report.metrics["source_types"] = ",".join(sorted(source_counts))
        report.metrics["job_statuses"] = ",".join(sorted(job_statuses))
        report.metrics["qa_statuses"] = ",".join(sorted(qa_statuses))

        for source_type in ("image", "audio", "video", "code_repository"):
            report.record(f"demo:source-type:{source_type}")
            if source_counts.get(source_type, 0) <= 0:
                report.fail(f"Demo is missing source_type={source_type}")
        for status in ("completed", "running", "failed"):
            report.record(f"demo:task-status:{status}")
            if job_statuses.get(status, 0) <= 0:
                report.fail(f"Demo is missing ingestion job status={status}")
        for status in ("grounded", "insufficient_context"):
            report.record(f"demo:qa-status:{status}")
            if qa_statuses.get(status, 0) <= 0:
                report.fail(f"Demo is missing QA retrieval_status={status}")

        failed_provider_rows = connection.execute(
            "select count(*) from ingestion_jobs where status='failed' and error_code like '%NOT_CONFIGURED'"
        ).fetchone()[0]
        report.record("demo:not-configured-failure")
        if int(failed_provider_rows) <= 0:
            report.fail("Demo should include a failed NOT_CONFIGURED task to show provider boundaries.")

        code_locators = connection.execute(
            """
            select count(*)
            from citation_locators
            where locator_json like '%code_repository%'
              and locator_json like '%file_path%'
              and locator_json like '%line_start%'
            """
        ).fetchone()[0]
        report.record("demo:code-locators")
        if int(code_locators) <= 0:
            report.fail("Demo code repository source has no file/line CitationLocator.")

        timestamp_locators = connection.execute(
            """
            select count(*)
            from citation_locators
            where locator_json like '%start_ms%' and locator_json like '%end_ms%'
            """
        ).fetchone()[0]
        report.record("demo:timestamp-locators")
        if int(timestamp_locators) <= 0:
            report.fail("Demo audio/video sources have no timestamp locators.")


def build_report(database: Path) -> RegressionReport:
    report = RegressionReport(database=database.resolve())
    require_paths(report, REQUIRED_BACKEND_ROUTES, label="backend-route")
    require_paths(report, REQUIRED_SCRIPTS, label="script")
    require_paths(report, REQUIRED_DOCS, label="doc")
    check_frontend(report)
    check_demo_database(report)
    return report


def write_markdown(report: RegressionReport, output: Path) -> None:
    try:
        database_label = report.database.relative_to(ROOT).as_posix()
    except ValueError:
        database_label = "<external demo database>"
    lines = [
        "# V4.2 Full Regression Report",
        "",
        f"- Database: `{database_label}`",
        f"- Result: `{'passed' if report.passed else 'failed'}`",
        f"- Checks executed: {len(report.checks)}",
        "",
        "## Metrics",
        "",
    ]
    for key, value in sorted(report.metrics.items()):
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Failures", ""])
    if report.failures:
        lines.extend(f"- {failure}" for failure in report.failures)
    else:
        lines.append("- None.")
    lines.extend(
        [
            "",
            "## Checklist Scope",
            "",
            "- Backend route files for dashboard, documents, media, code repositories, chat, learning, portfolio, tasks and system.",
            "- Frontend smoke routes for Dashboard, Upload, Tasks, Chat, System, Learning, Portfolio and Interview.",
            "- Synthetic demo data for document, image, audio, video, code repository, RAG, refusal, learning and task-center flows.",
            "- Release-support scripts and documentation entry points required for README-driven verification.",
            "",
        ]
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the V4.2 full regression checklist against synthetic demo data.")
    parser.add_argument("--database-path", type=Path, default=DEFAULT_DEMO_DATABASE)
    parser.add_argument("--write-report", type=Path)
    args = parser.parse_args()

    report = build_report(args.database_path)
    print("full_regression=checked")
    print(f"database={report.database}")
    print(f"checks={len(report.checks)}")
    for key, value in sorted(report.metrics.items()):
        print(f"{key}={value}")
    if args.write_report:
        write_markdown(report, args.write_report)
        print(f"report={args.write_report}")
    if report.failures:
        print("result=failed")
        for failure in report.failures:
            print(f"failure: {failure}")
        raise SystemExit(1)
    print("result=passed")


if __name__ == "__main__":
    main()
