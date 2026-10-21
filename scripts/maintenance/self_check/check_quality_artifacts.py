from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "backend").exists() and (candidate / "frontend").exists():
            return candidate
    raise RuntimeError("Repository root not found.")


ROOT = _repo_root()
VALID_STATUSES = {"passed", "failed", "skipped"}
REQUIRED_GATE_FIELDS = {"name", "status", "duration_sec", "next_step", "failure_reason"}
REQUIRED_GIT_FIELDS = {"branch", "commit", "short_commit", "dirty"}


def resolve_repo_path(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON report: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("Quality report must be a JSON object.")
    return payload


def validate_json_report(payload: dict[str, Any], *, expected_mode: str | None, require_passed: bool) -> list[str]:
    failures: list[str] = []
    mode = payload.get("mode")
    status = payload.get("status")
    gates = payload.get("gates")
    git = payload.get("git")

    if expected_mode and mode != expected_mode:
        failures.append(f"Expected mode={expected_mode}, got {mode!r}.")
    if status not in {"passed", "failed"}:
        failures.append(f"Report status must be passed or failed, got {status!r}.")
    if require_passed and status != "passed":
        failures.append(f"Report status must be passed when --require-passed is used, got {status!r}.")
    if not isinstance(gates, list) or not gates:
        failures.append("Report must include a non-empty gates list.")
        return failures

    if not isinstance(git, dict):
        failures.append("Report must include a git metadata object.")
    else:
        missing_git = sorted(REQUIRED_GIT_FIELDS - set(git))
        if missing_git:
            failures.append(f"Git metadata is missing fields: {', '.join(missing_git)}.")
        for field in ("branch", "commit", "short_commit"):
            if field in git and not isinstance(git.get(field), str):
                failures.append(f"Git metadata field {field} must be a string.")
        if "dirty" in git and git.get("dirty") is not None and not isinstance(git.get("dirty"), bool):
            failures.append("Git metadata field dirty must be a boolean or null.")

    gate_count = payload.get("gate_count")
    if gate_count != len(gates):
        failures.append(f"gate_count={gate_count!r} does not match gates length {len(gates)}.")

    for index, gate in enumerate(gates):
        if not isinstance(gate, dict):
            failures.append(f"Gate at index {index} must be an object.")
            continue
        missing = sorted(REQUIRED_GATE_FIELDS - set(gate))
        if missing:
            failures.append(f"Gate {index} is missing fields: {', '.join(missing)}.")
        gate_status = gate.get("status")
        if gate_status not in VALID_STATUSES:
            failures.append(f"Gate {gate.get('name', index)!r} has invalid status {gate_status!r}.")
        if require_passed and gate_status == "failed":
            failures.append(f"Gate {gate.get('name', index)!r} failed while --require-passed is active.")
        duration = gate.get("duration_sec")
        if not isinstance(duration, int | float) or duration < 0:
            failures.append(f"Gate {gate.get('name', index)!r} has invalid duration_sec {duration!r}.")

    return failures


def validate_summary(path: Path, payload: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    text = path.read_text(encoding="utf-8")
    required_snippets = [
        "# Quality Gate Summary",
        "## Gate Results",
        "## Optimization Focus",
        f"- Mode: `{payload.get('mode')}`",
        f"- Status: `{payload.get('status')}`",
        "- Git branch:",
        "- Git commit:",
        "- Git dirty:",
    ]
    for snippet in required_snippets:
        if snippet not in text:
            failures.append(f"Summary is missing required text: {snippet}")
    return failures


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate check_all JSON and Markdown quality gate artifacts.")
    parser.add_argument("--json", required=True, type=Path, help="Path to check_all --json-report output.")
    parser.add_argument("--summary", type=Path, help="Optional Markdown summary generated from the JSON report.")
    parser.add_argument("--expected-mode", help="Require a specific check_all mode, for example quick or release.")
    parser.add_argument("--require-passed", action="store_true", help="Fail unless the report status is passed and no gate failed.")
    args = parser.parse_args()

    json_path = resolve_repo_path(args.json)
    payload = load_json(json_path)
    failures = validate_json_report(payload, expected_mode=args.expected_mode, require_passed=args.require_passed)

    if args.summary:
        summary_path = resolve_repo_path(args.summary)
        if not summary_path.exists():
            failures.append(f"Summary file does not exist: {summary_path}")
        else:
            failures.extend(validate_summary(summary_path, payload))

    print("quality_artifacts=checked")
    print(f"json={json_path}")
    if args.summary:
        print(f"summary={resolve_repo_path(args.summary)}")
    print(f"failures={len(failures)}")
    if failures:
        print("result=failed")
        for failure in failures:
            print(f"failure: {failure}")
        raise SystemExit(1)
    print("result=passed")


if __name__ == "__main__":
    main()
