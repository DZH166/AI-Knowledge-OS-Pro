from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


def _repo_root() -> Path:
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "backend").exists() and (candidate / "frontend").exists():
            return candidate
    raise RuntimeError("Repository root not found.")


ROOT = _repo_root()
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"

REQUIRED_COMMANDS = (
    "python -m compileall backend/app scripts",
    "python -m ruff check backend/app backend/tests scripts",
    "python -m pytest backend/tests -q",
    "python -m alembic heads",
    "python -m alembic upgrade head",
    "python -m alembic current",
    "python scripts/verify_v5_migration.py --roundtrip",
    "python scripts/evaluate_agentic_rag.py --mode demo --database-path .pytest_tmp/v5_evaluation.db --output .pytest_tmp/v5_evaluation_report.json",
    "python scripts/check_v5_acceptance.py --report .pytest_tmp/v5_evaluation_report.json --json-output .pytest_tmp/v5_acceptance_gate.json",
    "npm run lint",
    "npm run typecheck",
    "npm run test:unit",
    "npm run build",
    "npm audit --omit=dev --audit-level=high",
    "python scripts/run_demo_e2e.py --strict --database-path .pytest_tmp/v5_ci_showcase_live_e2e.db",
    "python scripts/check_encoding.py",
    "python scripts/check_version.py",
    "python scripts/check_secrets.py",
    "python scripts/check_repo_clean.py",
    "python scripts/check_docs_links.py",
    "python scripts/check_readme_assets.py",
    "python scripts/check_frontend_smoke.py",
    "python scripts/check_ui_performance_budget.py",
    "python scripts/check_interaction_feedback.py",
    "python scripts/check_request_cache.py",
    "python scripts/check_e2e.py",
    "python scripts/evaluate_providers.py --dry-run",
    "python scripts/check_v5_acceptance.py --report .pytest_tmp/v5_evaluation_report.json",
    "python scripts/release.py --version V5.2 --dry-run",
    "python scripts/release.py --version V5.2",
    "python scripts/check_release.py --version V5.2",
)

REQUIRED_QUALITY_ARTIFACT_PATHS = (
    ".pytest_tmp/v5_evaluation_report.json",
    ".pytest_tmp/v5_acceptance_gate.json",
    "frontend/playwright-report/",
    "frontend/test-results/",
    "releases/AI-Knowledge-OS-Pro-V5.2-*.zip",
    "releases/AI-Knowledge-OS-Pro-V5.2-*.zip.sha256",
)

REQUIRED_WORKFLOW_SNIPPETS = (
    "actions: read",
    "contents: read",
    "needs: [backend, frontend, browser-e2e]",
    "actions/download-artifact@v4",
    "name: v5-evaluation-evidence",
    "name: playwright-v5-report",
    "name: suzhi-evidence-os-v5.2",
)

REQUIRED_RELEASE_DEPENDENCIES = ("backend", "frontend", "browser-e2e")

REQUIRED_RELEASE_JOB_SNIPPETS = (
    "actions/download-artifact@v4",
    "name: v5-evaluation-evidence",
    "path: .pytest_tmp",
    "python scripts/check_v5_acceptance.py --report .pytest_tmp/v5_evaluation_report.json",
)

REQUIRED_ORDERED_SNIPPETS = (
    (
        "python -m alembic heads",
        "python -m alembic upgrade head",
        "python -m alembic current",
        "python scripts/verify_v5_migration.py --roundtrip",
    ),
    (
        "python scripts/evaluate_agentic_rag.py --mode demo --database-path .pytest_tmp/v5_evaluation.db --output .pytest_tmp/v5_evaluation_report.json",
        "python scripts/check_v5_acceptance.py --report .pytest_tmp/v5_evaluation_report.json --json-output .pytest_tmp/v5_acceptance_gate.json",
        "name: v5-evaluation-evidence",
    ),
    (
        "npm run lint",
        "npm run typecheck",
        "npm run test:unit",
        "npm run build",
        "npm audit --omit=dev --audit-level=high",
    ),
    (
        "python scripts/run_demo_e2e.py --strict --database-path .pytest_tmp/v5_ci_showcase_live_e2e.db",
        "name: playwright-v5-report",
    ),
    (
        "needs: [backend, frontend, browser-e2e]",
        "actions/download-artifact@v4",
        "python scripts/check_v5_acceptance.py --report .pytest_tmp/v5_evaluation_report.json",
        "python scripts/release.py --version V5.2 --dry-run",
        "python scripts/release.py --version V5.2",
        "python scripts/check_release.py --version V5.2",
        "name: suzhi-evidence-os-v5.2",
    ),
)


def job_block(text: str, job_name: str) -> str | None:
    lines = text.splitlines()
    header = f"  {job_name}:"
    try:
        start = lines.index(header)
    except ValueError:
        return None
    end = len(lines)
    for index in range(start + 1, len(lines)):
        line = lines[index]
        if line.startswith("  ") and not line.startswith("    ") and line.rstrip().endswith(":"):
            end = index
            break
    return "\n".join(lines[start:end])


def workflow_step_containing(block: str, marker: str) -> str | None:
    lines = block.splitlines()
    try:
        marker_index = next(index for index, line in enumerate(lines) if marker in line)
    except StopIteration:
        return None

    start = marker_index
    while start >= 0 and not lines[start].startswith("      - "):
        start -= 1
    if start < 0:
        return None

    end = len(lines)
    for index in range(start + 1, len(lines)):
        if lines[index].startswith("      - "):
            end = index
            break
    return "\n".join(lines[start:end])


def validate_release_job(text: str) -> list[str]:
    block = job_block(text, "quality-and-release")
    if block is None:
        return ["CI workflow is missing the quality-and-release job."]

    failures: list[str] = []
    dependency_line = f"needs: [{', '.join(REQUIRED_RELEASE_DEPENDENCIES)}]"
    if dependency_line not in block:
        failures.append(
            "quality-and-release must need backend, frontend and browser-e2e before packaging."
        )
    for snippet in REQUIRED_RELEASE_JOB_SNIPPETS:
        if snippet not in block:
            failures.append(
                f"quality-and-release must download and validate v5-evaluation-evidence before packaging: {snippet}"
            )
    release_upload_step = workflow_step_containing(block, "name: suzhi-evidence-os-v5.2")
    release_conditions = (
        []
        if release_upload_step is None
        else [
            line.strip().removeprefix("if:").strip()
            for line in release_upload_step.splitlines()
            if line.strip().startswith("if:")
        ]
    )
    safe_release_conditions = {"success()", "${{ success() }}"}
    if any(condition not in safe_release_conditions for condition in release_conditions):
        failures.append("quality-and-release release artifact must not upload after a failed gate.")
    return failures


def resolve_repo_path(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def repo_display_path(path: Path) -> str:
    resolved = resolve_repo_path(path)
    return resolved.relative_to(ROOT).as_posix() if resolved.is_relative_to(ROOT) else resolved.as_posix()


def resolve_artifact_output_path(path: Path, *, label: str) -> Path:
    resolved = resolve_repo_path(path)
    try:
        relative = resolved.relative_to(ROOT)
    except ValueError as exc:
        raise ValueError(f"{label} output must stay inside the repository.") from exc
    if not relative.parts or relative.parts[0] != ".pytest_tmp":
        raise ValueError(f"{label} output must be written under .pytest_tmp.")
    return resolved


def validate_ordered_snippets(text: str) -> list[str]:
    failures: list[str] = []
    for ordered in REQUIRED_ORDERED_SNIPPETS:
        cursor = -1
        for snippet in ordered:
            position = text.find(snippet, cursor + 1)
            if position == -1:
                if snippet in text:
                    failures.append(f"CI workflow snippets must appear in order: {' -> '.join(ordered)}")
                break
            if position <= cursor:
                failures.append(f"CI workflow snippets must appear in order: {' -> '.join(ordered)}")
                break
            cursor = position
    return failures


def validate_workflow_text(text: str) -> list[str]:
    failures: list[str] = []
    for snippet in REQUIRED_WORKFLOW_SNIPPETS:
        if snippet not in text:
            failures.append(f"CI workflow is missing required workflow snippet: {snippet}")
    for command in REQUIRED_COMMANDS:
        if command not in text:
            failures.append(f"CI workflow is missing required quality command: {command}")
    for artifact_path in REQUIRED_QUALITY_ARTIFACT_PATHS:
        if artifact_path not in text:
            failures.append(f"CI quality artifact upload is missing path: {artifact_path}")
    failures.extend(validate_ordered_snippets(text))
    failures.extend(validate_release_job(text))
    return failures


def build_report(workflow: Path, failures: list[str]) -> dict[str, Any]:
    return {
        "schema_version": "1",
        "result": "failed" if failures else "passed",
        "workflow": repo_display_path(workflow),
        "required_commands": len(REQUIRED_COMMANDS),
        "required_artifact_paths": len(REQUIRED_QUALITY_ARTIFACT_PATHS),
        "required_workflow_snippets": len(REQUIRED_WORKFLOW_SNIPPETS),
        "required_ordered_groups": len(REQUIRED_ORDERED_SNIPPETS),
        "failure_count": len(failures),
        "failures": failures,
    }


def write_json_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_markdown_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# CI Artifact Contract",
        "",
        f"- Result: `{report['result']}`",
        f"- Workflow: `{report['workflow']}`",
        f"- Required commands: {report['required_commands']}",
        f"- Required artifact paths: {report['required_artifact_paths']}",
        f"- Required workflow snippets: {report['required_workflow_snippets']}",
        f"- Required ordered groups: {report['required_ordered_groups']}",
        f"- Failures: {report['failure_count']}",
        "",
        "## Failures",
        "",
    ]
    if report["failures"]:
        for failure in report["failures"]:
            lines.append(f"- {failure}")
    else:
        lines.append("- None")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def validate_report_artifact(path: Path, markdown: Path | None = None) -> None:
    command = [sys.executable, "scripts/check_ci_artifacts_report.py", "--report-json", str(path)]
    if markdown:
        command.extend(["--markdown", str(markdown)])
    print(">", " ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate GitHub Actions self-check artifact coverage.")
    parser.add_argument("--workflow", type=Path, default=WORKFLOW, help="Path to .github/workflows/ci.yml.")
    parser.add_argument("--json-output", type=Path, help="Write a machine-readable contract report under .pytest_tmp.")
    parser.add_argument("--markdown-output", type=Path, help="Write a human-readable contract report under .pytest_tmp.")
    args = parser.parse_args()

    try:
        json_output = resolve_artifact_output_path(args.json_output, label="JSON") if args.json_output else None
        markdown_output = resolve_artifact_output_path(args.markdown_output, label="Markdown") if args.markdown_output else None
    except ValueError as exc:
        print("ci_artifacts=checked")
        print("failures=1")
        print("result=failed")
        print(f"failure: {exc}")
        raise SystemExit(1) from exc

    workflow = resolve_repo_path(args.workflow)
    failures = validate_workflow_text(workflow.read_text(encoding="utf-8"))
    report = build_report(workflow, failures)
    if json_output:
        write_json_report(json_output, report)
    if markdown_output:
        write_markdown_report(markdown_output, report)
    if json_output:
        validate_report_artifact(json_output, markdown_output)
    print("ci_artifacts=checked")
    print(f"workflow={workflow}")
    print(f"required_commands={len(REQUIRED_COMMANDS)}")
    print(f"required_artifact_paths={len(REQUIRED_QUALITY_ARTIFACT_PATHS)}")
    print(f"required_workflow_snippets={len(REQUIRED_WORKFLOW_SNIPPETS)}")
    print(f"required_ordered_groups={len(REQUIRED_ORDERED_SNIPPETS)}")
    print(f"failures={len(failures)}")
    if json_output:
        print(f"json_output={json_output}")
    if markdown_output:
        print(f"markdown_output={markdown_output}")
    if failures:
        print("result=failed")
        for failure in failures:
            print(f"failure: {failure}")
        raise SystemExit(1)
    print("result=passed")


if __name__ == "__main__":
    main()
