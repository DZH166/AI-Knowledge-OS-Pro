from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable

try:
    from check_improvement_plan_commands import safe_artifact_path, split_command, validate_command
except ModuleNotFoundError:  # Allows importing as scripts.run_next_self_check in tests.
    from scripts.check_improvement_plan_commands import safe_artifact_path, split_command, validate_command


def _repo_root() -> Path:
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "backend").exists() and (candidate / "frontend").exists():
            return candidate
    raise RuntimeError("Repository root not found.")


ROOT = _repo_root()
DEFAULT_NEXT_COMMAND_JSON = Path(".pytest_tmp/self_check_next_command.json")


@dataclass(frozen=True)
class NextSelfCheckCommand:
    status: str
    priority: str
    title: str
    command: str


Runner = Callable[..., subprocess.CompletedProcess[Any]]


def resolve_repo_path(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def repo_display_path(path: Path) -> str:
    resolved = path if path.is_absolute() else ROOT / path
    return resolved.relative_to(ROOT).as_posix() if resolved.is_relative_to(ROOT) else resolved.as_posix()


def resolve_artifact_output_path(path: Path, *, label: str) -> Path:
    resolved = resolve_repo_path(path)
    try:
        repo_relative = resolved.relative_to(ROOT).as_posix()
    except ValueError as exc:
        raise ValueError(f"{label} output must stay inside the repository.") from exc
    if not safe_artifact_path(repo_relative):
        raise ValueError(f"{label} output must be a relative .pytest_tmp path.")
    return resolved


def load_payload(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Next-command artifact must be a JSON object.")
    return payload


def validate_payload(payload: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    status = payload.get("status")
    command = payload.get("command", "")
    if status not in {"available", "none"}:
        failures.append(f"status must be `available` or `none`, got {status!r}.")
    if command is None:
        command = ""
    if not isinstance(command, str):
        failures.append("command must be a string.")
        return failures
    if status == "available" and not command:
        failures.append("available next-command artifacts must include a command.")
    if status == "none" and command:
        failures.append("none next-command artifacts must not include a command.")
    reason = validate_command(command)
    if reason:
        failures.append(f"command is unsafe: {reason}")
    return failures


def parse_next_command(payload: dict[str, Any]) -> NextSelfCheckCommand:
    failures = validate_payload(payload)
    if failures:
        raise ValueError("\n".join(failures))
    return NextSelfCheckCommand(
        status=str(payload.get("status") or ""),
        priority=str(payload.get("priority") or ""),
        title=str(payload.get("title") or ""),
        command=str(payload.get("command") or ""),
    )


def command_tokens(command: str) -> list[str]:
    tokens = split_command(command)
    if tokens and tokens[0] == "python":
        return [sys.executable, *tokens[1:]]
    return tokens


def run_next_command(
    next_command: NextSelfCheckCommand,
    *,
    execute: bool,
    runner: Runner = subprocess.run,
) -> str:
    if next_command.status == "none":
        return "none"
    tokens = command_tokens(next_command.command)
    if not execute:
        return "ready"
    print(">", " ".join(tokens), flush=True)
    runner(tokens, cwd=ROOT, check=True)
    return "executed"


def build_report(
    *,
    path: Path,
    result: str,
    next_command: NextSelfCheckCommand | None = None,
    failure: str = "",
    markdown_output: Path | None = None,
) -> dict[str, str]:
    return {
        "schema_version": "1",
        "status": next_command.status if next_command else "invalid",
        "result": result,
        "priority": next_command.priority if next_command else "",
        "title": next_command.title if next_command else "",
        "command": next_command.command if next_command else "",
        "next_command_json": repo_display_path(path),
        "markdown_output": repo_display_path(markdown_output) if markdown_output else "",
        "failure": failure,
    }


def write_json_report(path: Path, payload: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_markdown_report(path: Path, payload: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Next Self-Check Command",
        "",
        f"- Status: `{payload['status']}`",
        f"- Result: `{payload['result']}`",
        f"- Priority: `{payload['priority']}`",
        f"- Title: `{payload['title']}`",
        f"- Source: `{payload['next_command_json']}`",
        "",
        "## Command",
        "",
    ]
    if payload["command"]:
        lines.extend(["```powershell", payload["command"], "```", ""])
    else:
        lines.append("- No command available.")
    if payload["failure"]:
        lines.extend(["", "## Failure", "", f"`{payload['failure']}`", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def validate_report_artifact(path: Path) -> None:
    command = [sys.executable, "scripts/check_next_self_check_report.py", "--report-json", str(path)]
    print(">", " ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate and optionally execute the next safe self-check command.")
    parser.add_argument(
        "--next-command-json",
        type=Path,
        default=DEFAULT_NEXT_COMMAND_JSON,
        help="Path to self_check_next_command.json.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute the validated command. Without this flag the script only checks readiness.",
    )
    parser.add_argument("--json-output", type=Path, help="Write a machine-readable result report under .pytest_tmp.")
    parser.add_argument("--markdown-output", type=Path, help="Write a human-readable result report under .pytest_tmp.")
    args = parser.parse_args()

    path = resolve_repo_path(args.next_command_json)
    json_output: Path | None = None
    markdown_output: Path | None = None
    if args.json_output:
        try:
            json_output = resolve_artifact_output_path(args.json_output, label="JSON")
        except ValueError as exc:
            print("next_self_check=checked")
            print(f"next_command_json={path}")
            print("result=failed")
            print(f"failure: {exc}")
            raise SystemExit(1) from exc
    if args.markdown_output:
        try:
            markdown_output = resolve_artifact_output_path(args.markdown_output, label="Markdown")
        except ValueError as exc:
            print("next_self_check=checked")
            print(f"next_command_json={path}")
            print("result=failed")
            print(f"failure: {exc}")
            raise SystemExit(1) from exc
    try:
        next_command = parse_next_command(load_payload(path))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        failed_report = build_report(path=path, result="failed", failure=str(exc), markdown_output=markdown_output)
        if json_output:
            write_json_report(json_output, failed_report)
        if markdown_output:
            write_markdown_report(markdown_output, failed_report)
        if json_output:
            validate_report_artifact(json_output)
        print("next_self_check=checked")
        print(f"next_command_json={path}")
        if json_output:
            print(f"json_output={json_output}")
        if markdown_output:
            print(f"markdown_output={markdown_output}")
        print("result=failed")
        print(f"failure: {exc}")
        raise SystemExit(1) from exc

    print("next_self_check=checked")
    print(f"next_command_json={path}")
    print(f"status={next_command.status}")
    if next_command.priority:
        print(f"priority={next_command.priority}")
    if next_command.title:
        print(f"title={next_command.title}")
    if next_command.command:
        print(f"command={next_command.command}")
    try:
        result = run_next_command(next_command, execute=args.execute)
    except subprocess.CalledProcessError as exc:
        failure = f"command failed with exit code {exc.returncode}"
        failed_report = build_report(path=path, result="failed", next_command=next_command, failure=failure, markdown_output=markdown_output)
        if json_output:
            write_json_report(json_output, failed_report)
        if markdown_output:
            write_markdown_report(markdown_output, failed_report)
        if json_output:
            validate_report_artifact(json_output)
        if json_output:
            print(f"json_output={json_output}")
        if markdown_output:
            print(f"markdown_output={markdown_output}")
        print("result=failed")
        print(f"failure: {failure}")
        raise SystemExit(exc.returncode) from exc
    report = build_report(path=path, result=result, next_command=next_command, markdown_output=markdown_output)
    if json_output:
        write_json_report(json_output, report)
    if markdown_output:
        write_markdown_report(markdown_output, report)
    if json_output:
        validate_report_artifact(json_output)
        print(f"json_output={json_output}")
    if markdown_output:
        print(f"markdown_output={markdown_output}")
    print(f"result={result}")


if __name__ == "__main__":
    main()
