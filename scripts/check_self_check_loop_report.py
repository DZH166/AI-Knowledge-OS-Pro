from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    from check_improvement_plan_commands import safe_artifact_path, validate_command
except ModuleNotFoundError:  # Allows importing as scripts.check_self_check_loop_report in tests.
    from scripts.check_improvement_plan_commands import safe_artifact_path, validate_command


ROOT = Path(__file__).resolve().parents[1]
VALID_STATUSES = {"planned", "passed"}
VALID_MODES = {"quick", "release", "full"}
VALID_STEP_RESULTS = {"ready", "executed", "none", "failed"}


def resolve_repo_path(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def load_report(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Self-check loop report must be a JSON object.")
    return payload


def safe_report_path(value: Any) -> bool:
    return isinstance(value, str) and safe_artifact_path(value)


def real_path(value: str) -> Path:
    return ROOT / Path(value)


def validate_loop_report(payload: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if payload.get("schema_version") != "1":
        failures.append("schema_version must be `1`.")
    if payload.get("status") not in VALID_STATUSES:
        failures.append(f"status must be one of {sorted(VALID_STATUSES)}, got {payload.get('status')!r}.")
    if payload.get("mode") not in VALID_MODES:
        failures.append(f"mode must be quick, release or full, got {payload.get('mode')!r}.")
    if not safe_report_path(payload.get("output_dir")):
        failures.append(f"output_dir must be a relative .pytest_tmp path, got {payload.get('output_dir')!r}.")
    markdown_output = payload.get("markdown_output")
    if markdown_output is not None:
        if not safe_report_path(markdown_output):
            failures.append(f"markdown_output must be a relative .pytest_tmp path, got {markdown_output!r}.")
        elif not real_path(markdown_output).exists():
            failures.append(f"markdown_output does not exist: {markdown_output}.")
    max_steps = payload.get("max_steps")
    if not isinstance(max_steps, int) or max_steps < 0:
        failures.append(f"max_steps must be a non-negative integer, got {max_steps!r}.")
    if not isinstance(payload.get("execute_next"), bool):
        failures.append("execute_next must be a boolean.")
    if not isinstance(payload.get("dry_run"), bool):
        failures.append("dry_run must be a boolean.")

    initial_command = payload.get("initial_command")
    if not isinstance(initial_command, str) or not initial_command:
        failures.append("initial_command must be a non-empty string.")
    else:
        reason = validate_command(initial_command)
        if reason:
            failures.append(f"initial_command is unsafe: {reason}")

    steps = payload.get("steps")
    if not isinstance(steps, list):
        return [*failures, "steps must be a list."]
    step_count = payload.get("step_count")
    if step_count is not None and step_count != len(steps):
        failures.append(f"step_count={step_count!r} does not match steps length {len(steps)}.")
    if payload.get("status") == "planned":
        if payload.get("dry_run") is not True:
            failures.append("planned loop reports must have dry_run=true.")
        if steps:
            failures.append("planned loop reports must not include executed steps.")
    if payload.get("status") == "passed":
        if step_count != len(steps):
            failures.append("passed loop reports must include a matching step_count.")
        if len(steps) > max_steps if isinstance(max_steps, int) else False:
            failures.append("steps length must not exceed max_steps.")

    for index, step in enumerate(steps, start=1):
        if not isinstance(step, dict):
            failures.append(f"Step {index} must be an object.")
            continue
        if step.get("index") != index:
            failures.append(f"Step {index} has invalid index {step.get('index')!r}.")
        result = step.get("result")
        if result not in VALID_STEP_RESULTS:
            failures.append(f"Step {index} result is invalid: {result!r}.")
        next_command_json = step.get("next_command_json")
        if not safe_report_path(next_command_json):
            failures.append(f"Step {index} next_command_json has invalid path {next_command_json!r}.")
        readiness_json = step.get("readiness_json")
        if not safe_report_path(readiness_json):
            failures.append(f"Step {index} readiness_json has invalid path {readiness_json!r}.")
        elif not real_path(readiness_json).exists():
            failures.append(f"Step {index} readiness_json does not exist: {readiness_json}.")
        readiness_markdown = step.get("readiness_markdown")
        if readiness_markdown is not None:
            if not safe_report_path(readiness_markdown):
                failures.append(f"Step {index} readiness_markdown has invalid path {readiness_markdown!r}.")
            elif not real_path(readiness_markdown).exists():
                failures.append(f"Step {index} readiness_markdown does not exist: {readiness_markdown}.")
        command = step.get("command", "")
        if command is None:
            command = ""
        if not isinstance(command, str):
            failures.append(f"Step {index} command must be a string.")
        else:
            if result in {"ready", "executed"} and not command:
                failures.append(f"Step {index} with result={result!r} must include a command.")
            reason = validate_command(command)
            if reason:
                failures.append(f"Step {index} command is unsafe: {reason}")
        failure = step.get("failure", "")
        if failure is None:
            failure = ""
        if not isinstance(failure, str):
            failures.append(f"Step {index} failure must be a string.")
        if result == "failed" and not failure:
            failures.append(f"Step {index} with result='failed' must include failure text.")
    return failures


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate bounded self-check loop reports.")
    parser.add_argument("--loop-json", required=True, type=Path, help="Path to self_check_loop.json.")
    args = parser.parse_args()

    loop_path = resolve_repo_path(args.loop_json)
    failures = validate_loop_report(load_report(loop_path))
    print("self_check_loop_report=checked")
    print(f"loop_json={loop_path}")
    print(f"failures={len(failures)}")
    if failures:
        print("result=failed")
        for failure in failures:
            print(f"failure: {failure}")
        raise SystemExit(1)
    print("result=passed")


if __name__ == "__main__":
    main()
