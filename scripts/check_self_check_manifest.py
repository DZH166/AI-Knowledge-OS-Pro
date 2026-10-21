from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    from check_improvement_plan_commands import safe_artifact_path, validate_command
except ModuleNotFoundError:  # Allows importing as scripts.check_self_check_manifest in tests.
    from scripts.check_improvement_plan_commands import safe_artifact_path, validate_command


ROOT = Path(__file__).resolve().parents[1]
VALID_STATUSES = {"passed"}
VALID_MODES = {"quick", "release", "full"}
VALID_COMPARE_STATES = {"not_requested", "manual", "latest", "skipped_no_previous_report"}
REQUIRED_ARTIFACTS = {"quality_json", "quality_summary"}


def resolve_repo_path(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def load_manifest(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Self-check manifest must be a JSON object.")
    return payload


def artifact_real_path(path_value: str) -> Path:
    return ROOT / Path(path_value)


def validate_artifacts(payload: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, list):
        return ["Manifest must include an artifacts list."]
    if payload.get("artifact_count") != len(artifacts):
        failures.append(f"artifact_count={payload.get('artifact_count')!r} does not match artifacts length {len(artifacts)}.")

    seen: set[str] = set()
    for index, artifact in enumerate(artifacts):
        if not isinstance(artifact, dict):
            failures.append(f"Artifact {index} must be an object.")
            continue
        name = artifact.get("name")
        path_value = artifact.get("path")
        exists = artifact.get("exists")
        if not isinstance(name, str) or not name:
            failures.append(f"Artifact {index} has invalid name.")
            continue
        seen.add(name)
        if not isinstance(path_value, str) or not safe_artifact_path(path_value):
            failures.append(f"Artifact {name} has invalid path {path_value!r}.")
        if not isinstance(exists, bool):
            failures.append(f"Artifact {name} has invalid exists value {exists!r}.")
            continue
        if isinstance(path_value, str) and safe_artifact_path(path_value):
            actual_exists = artifact_real_path(path_value).exists()
            if exists != actual_exists:
                failures.append(f"Artifact {name} exists={exists!r} but filesystem existence is {actual_exists!r}.")
        if name in REQUIRED_ARTIFACTS and exists is not True:
            failures.append(f"Required artifact {name} must exist.")

    missing_required = sorted(REQUIRED_ARTIFACTS - seen)
    if missing_required:
        failures.append(f"Manifest is missing required artifact(s): {', '.join(missing_required)}.")
    return failures


def validate_next_command(payload: dict[str, Any]) -> list[str]:
    next_command = payload.get("next_command")
    if not isinstance(next_command, dict):
        return ["Manifest must include a next_command object."]
    command = next_command.get("command", "")
    if command is None:
        command = ""
    if not isinstance(command, str):
        return ["next_command.command must be a string."]
    reason = validate_command(command)
    return [f"next_command.command is unsafe: {reason}"] if reason else []


def validate_manifest(payload: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if payload.get("status") not in VALID_STATUSES:
        failures.append(f"Manifest status must be one of {sorted(VALID_STATUSES)}, got {payload.get('status')!r}.")
    if payload.get("mode") not in VALID_MODES:
        failures.append(f"Manifest mode must be quick, release or full, got {payload.get('mode')!r}.")
    if payload.get("compare_state") not in VALID_COMPARE_STATES:
        failures.append(f"Manifest compare_state is invalid: {payload.get('compare_state')!r}.")
    failures.extend(validate_artifacts(payload))
    failures.extend(validate_next_command(payload))
    return failures


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate self-check manifest artifacts.")
    parser.add_argument("--manifest-json", required=True, type=Path, help="Path to self_check_manifest.json.")
    args = parser.parse_args()

    manifest_path = resolve_repo_path(args.manifest_json)
    failures = validate_manifest(load_manifest(manifest_path))
    print("self_check_manifest=checked")
    print(f"manifest_json={manifest_path}")
    print(f"failures={len(failures)}")
    if failures:
        print("result=failed")
        for failure in failures:
            print(f"failure: {failure}")
        raise SystemExit(1)
    print("result=passed")


if __name__ == "__main__":
    main()
