from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable

try:
    from check_improvement_plan_commands import option_value, safe_artifact_path, split_command
except ModuleNotFoundError:  # Allows importing as scripts.run_self_check_loop in tests.
    from scripts.check_improvement_plan_commands import option_value, safe_artifact_path, split_command


def _repo_root() -> Path:
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "backend").exists() and (candidate / "frontend").exists():
            return candidate
    raise RuntimeError("Repository root not found.")


ROOT = _repo_root()
SUPPORTED_MODES = {"quick", "release", "full"}
Runner = Callable[..., subprocess.CompletedProcess[Any]]


def resolve_repo_path(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def repo_display_path(path: Path) -> str:
    resolved = path if path.is_absolute() else ROOT / path
    return resolved.relative_to(ROOT).as_posix() if resolved.is_relative_to(ROOT) else resolved.as_posix()


def safe_output_path(path: Path) -> Path:
    resolved = resolve_repo_path(path)
    try:
        repo_relative = resolved.relative_to(ROOT).as_posix()
    except ValueError as exc:
        raise ValueError("Loop output must stay inside the repository.") from exc
    if not safe_artifact_path(repo_relative):
        raise ValueError("Loop output must be a relative .pytest_tmp path.")
    return resolved


def build_initial_command(
    *,
    mode: str,
    output_dir: Path,
    compare_latest: bool,
    fail_on_regression: bool,
) -> list[str]:
    command = [
        sys.executable,
        "scripts/run_self_check.py",
        "--mode",
        mode,
        "--output-dir",
        repo_display_path(output_dir),
        "--write-index",
        "--write-plan",
    ]
    if compare_latest:
        command.append("--compare-latest")
    if fail_on_regression:
        command.append("--fail-on-regression")
    return command


def run_command(command: list[str], *, dry_run: bool, runner: Runner) -> None:
    print(">", " ".join(command), flush=True)
    if not dry_run:
        runner(command, cwd=ROOT, check=True)


def next_artifact_from_command(command: str) -> Path | None:
    tokens = split_command(command)
    if tokens[:2] != ["python", "scripts/run_self_check.py"]:
        return None
    output_dir = option_value(tokens, "--output-dir")
    if not output_dir or not safe_artifact_path(output_dir):
        return None
    return resolve_repo_path(Path(output_dir)) / "self_check_next_command.json"


def load_readiness(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Next self-check readiness report must be a JSON object.")
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Self-Check Loop Report",
        "",
        f"- Status: `{report['status']}`",
        f"- Mode: `{report['mode']}`",
        f"- Output dir: `{report['output_dir']}`",
        f"- Max steps: `{report['max_steps']}`",
        f"- Execute next: `{str(report['execute_next']).lower()}`",
        f"- Dry run: `{str(report['dry_run']).lower()}`",
        f"- Step count: `{len(report['steps'])}`",
        "",
        "## Initial Command",
        "",
        "```powershell",
        str(report["initial_command"]),
        "```",
        "",
        "## Steps",
        "",
    ]
    steps = report.get("steps", [])
    if not steps:
        lines.append("- No next-command steps were executed or inspected.")
    else:
        lines.extend(
            [
                "| Step | Result | Priority | Title | Readiness Report | Readiness Markdown | Next Command Artifact |",
                "| ---: | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for step in steps:
            lines.append(
                f"| {step['index']} | `{step['result']}` | `{step['priority']}` | {step['title']} | "
                f"`{step['readiness_json']}` | `{step.get('readiness_markdown', '')}` | `{step['next_command_json']}` |"
            )
        for step in steps:
            command = step.get("command")
            if command:
                lines.extend(
                    [
                        "",
                        f"### Step {step['index']} Command",
                        "",
                        "```powershell",
                        str(command),
                        "```",
                    ]
                )
            failure = step.get("failure")
            if failure:
                lines.extend(["", f"- Step {step['index']} failure: `{failure}`"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def validate_loop_report_artifact(path: Path) -> None:
    command = [sys.executable, "scripts/check_self_check_loop_report.py", "--loop-json", str(path)]
    print(">", " ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def run_loop(
    *,
    mode: str,
    output_dir: Path,
    max_steps: int,
    execute_next: bool,
    compare_latest: bool,
    fail_on_regression: bool,
    json_output: Path,
    markdown_output: Path | None = None,
    dry_run: bool,
    runner: Runner = subprocess.run,
) -> dict[str, Any]:
    resolved_output_dir = safe_output_path(output_dir)
    resolved_json_output = safe_output_path(json_output)
    resolved_markdown_output = safe_output_path(markdown_output) if markdown_output else None
    initial_command = build_initial_command(
        mode=mode,
        output_dir=resolved_output_dir,
        compare_latest=compare_latest,
        fail_on_regression=fail_on_regression,
    )
    report: dict[str, Any] = {
        "schema_version": "1",
        "status": "planned" if dry_run else "running",
        "mode": mode,
        "output_dir": repo_display_path(resolved_output_dir),
        "max_steps": max_steps,
        "execute_next": execute_next,
        "dry_run": dry_run,
        "initial_command": " ".join(["python", *initial_command[1:]]),
        "steps": [],
    }
    if resolved_markdown_output:
        report["markdown_output"] = repo_display_path(resolved_markdown_output)
    if dry_run:
        write_json(resolved_json_output, report)
        if resolved_markdown_output:
            write_markdown(resolved_markdown_output, report)
        return report

    run_command(initial_command, dry_run=False, runner=runner)
    next_command_json = resolved_output_dir / "self_check_next_command.json"
    for step_index in range(1, max_steps + 1):
        readiness_json = resolved_output_dir / f"next_self_check_step_{step_index}.json"
        readiness_markdown = resolved_output_dir / f"next_self_check_step_{step_index}.md"
        next_runner_command = [
            sys.executable,
            "scripts/run_next_self_check.py",
            "--next-command-json",
            repo_display_path(next_command_json),
            "--json-output",
            repo_display_path(readiness_json),
            "--markdown-output",
            repo_display_path(readiness_markdown),
        ]
        if execute_next:
            next_runner_command.append("--execute")
        run_command(next_runner_command, dry_run=False, runner=runner)
        readiness = load_readiness(readiness_json)
        step = {
            "index": step_index,
            "next_command_json": repo_display_path(next_command_json),
            "readiness_json": repo_display_path(readiness_json),
            "readiness_markdown": repo_display_path(readiness_markdown),
            "result": readiness.get("result", ""),
            "priority": readiness.get("priority", ""),
            "title": readiness.get("title", ""),
            "command": readiness.get("command", ""),
            "failure": readiness.get("failure", ""),
        }
        report["steps"].append(step)
        if readiness.get("result") in {"none", "failed"}:
            break
        if readiness.get("result") == "ready" and not execute_next:
            break
        if readiness.get("result") != "executed":
            break
        next_artifact = next_artifact_from_command(str(readiness.get("command") or ""))
        if not next_artifact:
            break
        next_command_json = next_artifact

    report["status"] = "passed"
    report["step_count"] = len(report["steps"])
    write_json(resolved_json_output, report)
    if resolved_markdown_output:
        write_markdown(resolved_markdown_output, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a bounded self-check loop from generated next-command artifacts.")
    parser.add_argument("--mode", choices=sorted(SUPPORTED_MODES), default="quick", help="Initial self-check mode.")
    parser.add_argument("--output-dir", type=Path, default=Path(".pytest_tmp/self_check_loop"), help="Initial loop artifact directory under .pytest_tmp.")
    parser.add_argument("--max-steps", type=int, default=1, help="Maximum next-command steps to inspect or execute.")
    parser.add_argument("--execute-next", action="store_true", help="Execute validated next-command artifacts up to --max-steps.")
    parser.add_argument("--compare-latest", action="store_true", help="Run the initial self-check with --compare-latest.")
    parser.add_argument("--fail-on-regression", action="store_true", help="Fail compared self-check runs when regressions are found.")
    parser.add_argument("--json-output", type=Path, default=Path(".pytest_tmp/self_check_loop.json"), help="Loop report path under .pytest_tmp.")
    parser.add_argument("--markdown-output", type=Path, default=Path(".pytest_tmp/self_check_loop.md"), help="Markdown loop report path under .pytest_tmp.")
    parser.add_argument("--dry-run", action="store_true", help="Write the planned loop report without running commands.")
    args = parser.parse_args()

    if args.max_steps < 0:
        raise SystemExit("--max-steps must be 0 or greater.")
    if args.fail_on_regression and not args.compare_latest:
        raise SystemExit("--fail-on-regression requires --compare-latest.")

    try:
        report = run_loop(
            mode=args.mode,
            output_dir=args.output_dir,
            max_steps=args.max_steps,
            execute_next=args.execute_next,
            compare_latest=args.compare_latest,
            fail_on_regression=args.fail_on_regression,
            json_output=args.json_output,
            markdown_output=args.markdown_output,
            dry_run=args.dry_run,
        )
        validate_loop_report_artifact(resolve_repo_path(args.json_output))
    except ValueError as exc:
        print("self_check_loop=checked")
        print("result=failed")
        print(f"failure: {exc}")
        raise SystemExit(1) from exc

    print("self_check_loop=checked")
    print(f"status={report['status']}")
    print(f"mode={report['mode']}")
    print(f"step_count={len(report['steps'])}")
    print(f"json_output={repo_display_path(resolve_repo_path(args.json_output))}")
    print(f"markdown_output={repo_display_path(resolve_repo_path(args.markdown_output))}")
    print("result=passed" if report["status"] in {"planned", "passed"} else "result=failed")


if __name__ == "__main__":
    main()
