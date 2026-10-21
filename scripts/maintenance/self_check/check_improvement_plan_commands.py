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
SUPPORTED_SELF_CHECK_MODES = {"quick", "release", "full"}


def resolve_repo_path(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def load_plan(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Improvement plan must be a JSON object.")
    return payload


def split_command(command: str) -> list[str]:
    return [part for part in command.strip().split(" ") if part]


def safe_artifact_path(value: str) -> bool:
    normalized = value.replace("\\", "/")
    if not normalized or normalized.startswith(("/", "-", "~")) or ":" in normalized:
        return False
    parts = [part for part in normalized.split("/") if part]
    return bool(parts) and parts[0] == ".pytest_tmp" and ".." not in parts


def option_value(tokens: list[str], option: str) -> str | None:
    if option not in tokens:
        return None
    index = tokens.index(option)
    if index + 1 >= len(tokens):
        return None
    return tokens[index + 1]


def validate_run_self_check(tokens: list[str]) -> str | None:
    if len(tokens) < 8 or tokens[:2] != ["python", "scripts/run_self_check.py"]:
        return "run_self_check command must start with `python scripts/run_self_check.py`."
    mode = option_value(tokens, "--mode")
    output_dir = option_value(tokens, "--output-dir")
    if mode not in SUPPORTED_SELF_CHECK_MODES:
        return "run_self_check command must use --mode quick, --mode release or --mode full."
    if not output_dir or not safe_artifact_path(output_dir):
        return "run_self_check command must write to a relative .pytest_tmp output directory."
    allowed = {
        "python",
        "scripts/run_self_check.py",
        "--mode",
        mode,
        "--output-dir",
        output_dir,
        "--compare-latest",
        "--write-index",
        "--write-plan",
        "--fail-on-regression",
    }
    unexpected = [token for token in tokens if token not in allowed]
    if unexpected:
        return f"run_self_check command contains unsupported token(s): {', '.join(unexpected)}."
    if "--write-index" not in tokens or "--write-plan" not in tokens:
        return "run_self_check command suggestions must include --write-index and --write-plan."
    if "--fail-on-regression" in tokens and "--compare-latest" not in tokens:
        return "--fail-on-regression requires --compare-latest in command suggestions."
    return None


def validate_check_all(tokens: list[str]) -> str | None:
    if tokens[:2] != ["python", "scripts/check_all.py"]:
        return "check_all command must start with `python scripts/check_all.py`."
    expected_length = 5
    if len(tokens) != expected_length or tokens[2] != "--full" or tokens[3] != "--json-report":
        return "check_all command suggestions may only run --full with --json-report."
    if not safe_artifact_path(tokens[4]):
        return "check_all --json-report must write to a relative .pytest_tmp path."
    return None


def validate_command(command: str) -> str | None:
    if not command:
        return None
    tokens = split_command(command)
    if not tokens:
        return None
    if tokens[:2] == ["python", "scripts/run_self_check.py"]:
        return validate_run_self_check(tokens)
    if tokens[:2] == ["python", "scripts/check_all.py"]:
        return validate_check_all(tokens)
    return "Command is not in the self-check allowlist."


def validate_plan(payload: dict[str, Any]) -> tuple[list[str], list[str]]:
    failures: list[str] = []
    commands: list[str] = []
    items = payload.get("items")
    if not isinstance(items, list):
        return ["Improvement plan must include an items list."], []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            failures.append(f"Item {index} must be an object.")
            continue
        command = item.get("command", "")
        if command is None:
            command = ""
        if not isinstance(command, str):
            failures.append(f"Item {index} command must be a string.")
            continue
        reason = validate_command(command)
        if reason:
            failures.append(f"Item {index} command is unsafe: {reason}")
        elif command:
            commands.append(command)
    return failures, commands


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate executable command suggestions in self-check improvement plans.")
    parser.add_argument("--plan-json", required=True, type=Path, help="Path to self_check_improvement_plan.json.")
    args = parser.parse_args()

    plan_path = resolve_repo_path(args.plan_json)
    failures, commands = validate_plan(load_plan(plan_path))
    print("improvement_plan_commands=checked")
    print(f"plan_json={plan_path}")
    print(f"command_count={len(commands)}")
    if commands:
        print(f"next_command={commands[0]}")
    print(f"failures={len(failures)}")
    if failures:
        print("result=failed")
        for failure in failures:
            print(f"failure: {failure}")
        raise SystemExit(1)
    print("result=passed")


if __name__ == "__main__":
    main()
