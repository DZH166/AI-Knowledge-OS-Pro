from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    from check_improvement_plan_commands import safe_artifact_path, validate_command
except ModuleNotFoundError:  # Allows importing as scripts.check_next_self_check_report in tests.
    from scripts.check_improvement_plan_commands import safe_artifact_path, validate_command


ROOT = Path(__file__).resolve().parents[1]
VALID_STATUSES = {"available", "none", "invalid"}
VALID_RESULTS = {"ready", "executed", "none", "failed"}


def resolve_repo_path(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def load_report(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Next self-check report must be a JSON object.")
    return payload


def safe_report_path(value: Any) -> bool:
    return isinstance(value, str) and safe_artifact_path(value)


def real_path(value: str) -> Path:
    return ROOT / Path(value)


def validate_report(payload: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if payload.get("schema_version") != "1":
        failures.append("schema_version must be `1`.")
    status = payload.get("status")
    result = payload.get("result")
    if status not in VALID_STATUSES:
        failures.append(f"status must be one of {sorted(VALID_STATUSES)}, got {status!r}.")
    if result not in VALID_RESULTS:
        failures.append(f"result must be one of {sorted(VALID_RESULTS)}, got {result!r}.")
    if not safe_report_path(payload.get("next_command_json")):
        failures.append(f"next_command_json must be a relative .pytest_tmp path, got {payload.get('next_command_json')!r}.")
    markdown_output = payload.get("markdown_output", "")
    if markdown_output:
        if not safe_report_path(markdown_output):
            failures.append(f"markdown_output must be a relative .pytest_tmp path, got {markdown_output!r}.")
        elif not real_path(markdown_output).exists():
            failures.append(f"markdown_output does not exist: {markdown_output}.")

    for field in ("priority", "title", "failure"):
        if not isinstance(payload.get(field, ""), str):
            failures.append(f"{field} must be a string.")

    command = payload.get("command", "")
    if command is None:
        command = ""
    if not isinstance(command, str):
        failures.append("command must be a string.")
        return failures
    if result in {"ready", "executed"} and status != "available":
        failures.append(f"result={result!r} requires status='available'.")
    if result in {"ready", "executed"} and not command:
        failures.append(f"result={result!r} requires a command.")
    if result == "none" and status != "none":
        failures.append("result='none' requires status='none'.")
    if result == "none" and command:
        failures.append("result='none' must not include a command.")
    if result == "failed" and not payload.get("failure"):
        failures.append("result='failed' requires failure text.")
    reason = validate_command(command)
    if reason:
        failures.append(f"command is unsafe: {reason}")
    return failures


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate next self-check readiness reports.")
    parser.add_argument("--report-json", required=True, type=Path, help="Path to next_self_check.json.")
    args = parser.parse_args()

    report_path = resolve_repo_path(args.report_json)
    failures = validate_report(load_report(report_path))
    print("next_self_check_report=checked")
    print(f"report_json={report_path}")
    print(f"failures={len(failures)}")
    if failures:
        print("result=failed")
        for failure in failures:
            print(f"failure: {failure}")
        raise SystemExit(1)
    print("result=passed")


if __name__ == "__main__":
    main()
