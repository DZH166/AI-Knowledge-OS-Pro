from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
from typing import Any


def _repo_root() -> Path:
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "backend").exists() and (candidate / "frontend").exists():
            return candidate
    raise RuntimeError("Repository root not found.")


ROOT = _repo_root()
VALID_RESULTS = {"passed", "failed"}
REQUIRED_FIELDS = {
    "schema_version",
    "result",
    "workflow",
    "required_commands",
    "required_artifact_paths",
    "required_workflow_snippets",
    "required_ordered_groups",
    "failure_count",
    "failures",
}


def resolve_repo_path(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def repo_display_path(path: Path) -> str:
    resolved = resolve_repo_path(path)
    return resolved.relative_to(ROOT).as_posix() if resolved.is_relative_to(ROOT) else resolved.as_posix()


def load_report(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("CI artifact contract report must be a JSON object.")
    return payload


def is_non_negative_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def is_safe_repo_display_path(value: object) -> bool:
    if not isinstance(value, str) or not value:
        return False
    if "\\" in value or "\x00" in value:
        return False
    path = PurePosixPath(value)
    return not path.is_absolute() and ".." not in path.parts


def validate_report(payload: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    missing = sorted(REQUIRED_FIELDS - set(payload))
    if missing:
        failures.append(f"Report is missing fields: {', '.join(missing)}.")

    if payload.get("schema_version") != "1":
        failures.append("schema_version must be `1`.")
    result = payload.get("result")
    if result not in VALID_RESULTS:
        failures.append(f"result must be one of {sorted(VALID_RESULTS)}, got {result!r}.")
    if not is_safe_repo_display_path(payload.get("workflow")):
        failures.append(f"workflow must be a safe repository-relative path, got {payload.get('workflow')!r}.")

    for field_name in (
        "required_commands",
        "required_artifact_paths",
        "required_workflow_snippets",
        "required_ordered_groups",
        "failure_count",
    ):
        if not is_non_negative_int(payload.get(field_name)):
            failures.append(f"{field_name} must be a non-negative integer.")

    report_failures = payload.get("failures")
    if not isinstance(report_failures, list) or not all(isinstance(item, str) for item in report_failures):
        failures.append("failures must be a list of strings.")
        report_failures = []

    failure_count = payload.get("failure_count")
    if isinstance(failure_count, int) and not isinstance(failure_count, bool) and failure_count != len(report_failures):
        failures.append("failure_count must match the number of failure entries.")
    if result == "passed" and failure_count != 0:
        failures.append("result='passed' requires failure_count=0.")
    if result == "failed" and failure_count == 0:
        failures.append("result='failed' requires at least one failure.")
    return failures


def validate_markdown(path: Path, payload: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    text = path.read_text(encoding="utf-8")
    required_snippets = [
        "# CI Artifact Contract",
        f"- Result: `{payload.get('result')}`",
        f"- Workflow: `{payload.get('workflow')}`",
        f"- Required commands: {payload.get('required_commands')}",
        f"- Required artifact paths: {payload.get('required_artifact_paths')}",
        f"- Required workflow snippets: {payload.get('required_workflow_snippets')}",
        f"- Required ordered groups: {payload.get('required_ordered_groups')}",
        f"- Failures: {payload.get('failure_count')}",
        "## Failures",
    ]
    for snippet in required_snippets:
        if snippet not in text:
            failures.append(f"Markdown report is missing required text: {snippet}")

    report_failures = payload.get("failures") if isinstance(payload.get("failures"), list) else []
    if report_failures:
        for failure in report_failures:
            if isinstance(failure, str) and failure not in text:
                failures.append(f"Markdown report is missing failure text: {failure}")
    elif "- None" not in text:
        failures.append("Markdown report must include '- None' when no failures exist.")
    return failures


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate CI artifact contract JSON and Markdown reports.")
    parser.add_argument("--report-json", required=True, type=Path, help="Path to ci_artifacts_contract.json.")
    parser.add_argument("--markdown", type=Path, help="Optional ci_artifacts_contract.md report.")
    args = parser.parse_args()

    report_path = resolve_repo_path(args.report_json)
    try:
        payload = load_report(report_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        payload = {}
        failures = [f"JSON report is invalid: {exc}"]
    else:
        failures = validate_report(payload)

    markdown_path: Path | None = None
    if args.markdown:
        markdown_path = resolve_repo_path(args.markdown)
        if not markdown_path.exists():
            failures.append(f"Markdown report does not exist: {repo_display_path(markdown_path)}.")
        elif payload:
            failures.extend(validate_markdown(markdown_path, payload))

    print("ci_artifacts_report=checked")
    print(f"report_json={report_path}")
    if markdown_path:
        print(f"markdown={markdown_path}")
    print(f"failures={len(failures)}")
    if failures:
        print("result=failed")
        for failure in failures:
            print(f"failure: {failure}")
        raise SystemExit(1)
    print("result=passed")


if __name__ == "__main__":
    main()
