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
    "python scripts/check_ci_artifacts.py --json-output .pytest_tmp/ci_artifacts_contract.json --markdown-output .pytest_tmp/ci_artifacts_contract.md",
    "python scripts/check_ci_artifacts_report.py --report-json .pytest_tmp/ci_artifacts_contract.json --markdown .pytest_tmp/ci_artifacts_contract.md",
    "python scripts/run_self_check.py --mode quick --output-dir .pytest_tmp --write-index --write-plan",
    "python scripts/run_next_self_check.py --next-command-json .pytest_tmp/self_check_next_command.json --json-output .pytest_tmp/next_self_check.json --markdown-output .pytest_tmp/next_self_check.md",
    "python scripts/check_next_self_check_report.py --report-json .pytest_tmp/next_self_check.json",
    "python scripts/run_self_check_loop.py --mode quick --output-dir .pytest_tmp/self_check_loop --max-steps 1 --dry-run --json-output .pytest_tmp/self_check_loop.json --markdown-output .pytest_tmp/self_check_loop.md",
    "python scripts/check_self_check_loop_report.py --loop-json .pytest_tmp/self_check_loop.json",
    "python scripts/run_self_check.py --mode release --output-dir .pytest_tmp/self_check_release --write-index --write-plan",
    "python scripts/run_self_check.py --mode release --output-dir .pytest_tmp/self_check_release --compare-latest --write-index --write-plan --fail-on-regression",
    "python scripts/run_next_self_check.py --next-command-json .pytest_tmp/self_check_release/self_check_next_command.json --json-output .pytest_tmp/self_check_release/next_self_check_full_ready.json --markdown-output .pytest_tmp/self_check_release/next_self_check_full_ready.md",
    "python scripts/check_next_self_check_report.py --report-json .pytest_tmp/self_check_release/next_self_check_full_ready.json",
    "python scripts/check_github_actions.py --json-output .pytest_tmp/github_actions_status.json --markdown-output .pytest_tmp/github_actions_status.md",
    "python scripts/check_github_actions_report.py --report-json .pytest_tmp/github_actions_status.json --markdown .pytest_tmp/github_actions_status.md",
)

REQUIRED_QUALITY_ARTIFACT_PATHS = (
    ".pytest_tmp/check_all_*.json",
    ".pytest_tmp/check_all_*.md",
    ".pytest_tmp/self_check_index.json",
    ".pytest_tmp/self_check_index.md",
    ".pytest_tmp/self_check_improvement_plan.json",
    ".pytest_tmp/self_check_improvement_plan.md",
    ".pytest_tmp/self_check_next_command.json",
    ".pytest_tmp/self_check_next_command.md",
    ".pytest_tmp/next_self_check.json",
    ".pytest_tmp/next_self_check.md",
    ".pytest_tmp/self_check_loop.json",
    ".pytest_tmp/self_check_loop.md",
    ".pytest_tmp/self_check_loop/next_self_check_step_*.json",
    ".pytest_tmp/self_check_loop/next_self_check_step_*.md",
    ".pytest_tmp/self_check_manifest.json",
    ".pytest_tmp/self_check_manifest.md",
    ".pytest_tmp/self_check_release/check_all_*.json",
    ".pytest_tmp/self_check_release/check_all_*.md",
    ".pytest_tmp/self_check_release/self_check_index.json",
    ".pytest_tmp/self_check_release/self_check_index.md",
    ".pytest_tmp/self_check_release/self_check_improvement_plan.json",
    ".pytest_tmp/self_check_release/self_check_improvement_plan.md",
    ".pytest_tmp/self_check_release/self_check_next_command.json",
    ".pytest_tmp/self_check_release/self_check_next_command.md",
    ".pytest_tmp/self_check_release/next_self_check_full_ready.json",
    ".pytest_tmp/self_check_release/next_self_check_full_ready.md",
    ".pytest_tmp/self_check_release/self_check_manifest.json",
    ".pytest_tmp/self_check_release/self_check_manifest.md",
    ".pytest_tmp/github_actions_status.json",
    ".pytest_tmp/github_actions_status.md",
    ".pytest_tmp/ci_artifacts_contract.json",
    ".pytest_tmp/ci_artifacts_contract.md",
)

REQUIRED_WORKFLOW_SNIPPETS = (
    "actions: read",
    "GITHUB_TOKEN: ${{ github.token }}",
)

REQUIRED_ORDERED_SNIPPETS = (
    (
        "python scripts/run_self_check.py --mode quick --output-dir .pytest_tmp --write-index --write-plan",
        "python scripts/run_next_self_check.py --next-command-json .pytest_tmp/self_check_next_command.json --json-output .pytest_tmp/next_self_check.json --markdown-output .pytest_tmp/next_self_check.md",
        "python scripts/check_next_self_check_report.py --report-json .pytest_tmp/next_self_check.json",
    ),
    (
        "python scripts/run_self_check_loop.py --mode quick --output-dir .pytest_tmp/self_check_loop --max-steps 1 --dry-run --json-output .pytest_tmp/self_check_loop.json --markdown-output .pytest_tmp/self_check_loop.md",
        "python scripts/check_self_check_loop_report.py --loop-json .pytest_tmp/self_check_loop.json",
    ),
    (
        "python scripts/run_self_check.py --mode release --output-dir .pytest_tmp/self_check_release --write-index --write-plan",
        "python scripts/run_self_check.py --mode release --output-dir .pytest_tmp/self_check_release --compare-latest --write-index --write-plan --fail-on-regression",
        "python scripts/run_next_self_check.py --next-command-json .pytest_tmp/self_check_release/self_check_next_command.json --json-output .pytest_tmp/self_check_release/next_self_check_full_ready.json --markdown-output .pytest_tmp/self_check_release/next_self_check_full_ready.md",
        "python scripts/check_next_self_check_report.py --report-json .pytest_tmp/self_check_release/next_self_check_full_ready.json",
    ),
    (
        "python scripts/check_github_actions.py --json-output .pytest_tmp/github_actions_status.json --markdown-output .pytest_tmp/github_actions_status.md",
        "python scripts/check_github_actions_report.py --report-json .pytest_tmp/github_actions_status.json --markdown .pytest_tmp/github_actions_status.md",
    ),
    (
        "python scripts/check_github_actions_report.py --report-json .pytest_tmp/github_actions_status.json --markdown .pytest_tmp/github_actions_status.md",
        "name: quality-gate-json",
    ),
    (
        "python scripts/check_ci_artifacts.py --json-output .pytest_tmp/ci_artifacts_contract.json --markdown-output .pytest_tmp/ci_artifacts_contract.md",
        "python scripts/check_ci_artifacts_report.py --report-json .pytest_tmp/ci_artifacts_contract.json --markdown .pytest_tmp/ci_artifacts_contract.md",
        "name: quality-gate-json",
    ),
)


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
            position = text.find(snippet)
            if position == -1:
                break
            if position <= cursor:
                failures.append(f"CI workflow snippets must appear in order: {' -> '.join(ordered)}")
                break
            cursor = position
    return failures


def validate_workflow_text(text: str) -> list[str]:
    failures: list[str] = []
    if "name: quality-gate-json" not in text:
        failures.append("CI workflow must upload a quality-gate-json artifact.")
    if "python scripts/check_ci_artifacts.py" not in text:
        failures.append("CI workflow must run scripts/check_ci_artifacts.py.")
    for snippet in REQUIRED_WORKFLOW_SNIPPETS:
        if snippet not in text:
            failures.append(f"CI workflow is missing required workflow snippet: {snippet}")
    for command in REQUIRED_COMMANDS:
        if command not in text:
            failures.append(f"CI workflow is missing self-check command: {command}")
    for artifact_path in REQUIRED_QUALITY_ARTIFACT_PATHS:
        if artifact_path not in text:
            failures.append(f"CI quality artifact upload is missing path: {artifact_path}")
    failures.extend(validate_ordered_snippets(text))
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
