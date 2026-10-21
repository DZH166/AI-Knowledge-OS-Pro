from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
SUPPORTED_MODES = {"quick", "release", "full"}


@dataclass(frozen=True)
class SelfCheckPaths:
    output_dir: Path
    json_report: Path
    markdown_summary: Path
    comparison_report: Path
    comparison_json: Path
    history_index: Path
    history_markdown: Path
    improvement_plan: Path
    improvement_json: Path
    next_command_json: Path
    next_command_markdown: Path
    manifest_json: Path
    manifest_markdown: Path


def resolve_repo_path(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def build_paths(output_dir: Path, mode: str) -> SelfCheckPaths:
    root = resolve_repo_path(output_dir)
    return SelfCheckPaths(
        output_dir=root,
        json_report=root / f"check_all_{mode}.json",
        markdown_summary=root / f"check_all_{mode}_summary.md",
        comparison_report=root / f"check_all_{mode}_comparison.md",
        comparison_json=root / f"check_all_{mode}_comparison.json",
        history_index=root / "self_check_index.json",
        history_markdown=root / "self_check_index.md",
        improvement_plan=root / "self_check_improvement_plan.md",
        improvement_json=root / "self_check_improvement_plan.json",
        next_command_json=root / "self_check_next_command.json",
        next_command_markdown=root / "self_check_next_command.md",
        manifest_json=root / "self_check_manifest.json",
        manifest_markdown=root / "self_check_manifest.md",
    )


def latest_baseline_path(paths: SelfCheckPaths, mode: str) -> Path:
    output_key = hashlib.sha256(str(paths.output_dir.resolve()).encode("utf-8")).hexdigest()[:16]
    return Path(tempfile.gettempdir()) / "ai_knowledge_os_self_check_baselines" / output_key / f"baseline_check_all_{mode}.json"


def prepare_latest_baseline(paths: SelfCheckPaths, mode: str, *, dry_run: bool) -> Path | None:
    if not paths.json_report.exists():
        return None
    baseline = latest_baseline_path(paths, mode)
    if not dry_run:
        baseline.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(paths.json_report, baseline)
    return baseline


def build_commands(
    mode: str,
    paths: SelfCheckPaths,
    *,
    require_passed: bool,
    compare_to: Path | None = None,
    fail_on_regression: bool = False,
    write_index: bool = False,
    write_plan: bool = False,
) -> list[list[str]]:
    mode_flag = f"--{mode}"
    artifact_command = [
        sys.executable,
        "scripts/check_quality_artifacts.py",
        "--json",
        str(paths.json_report),
        "--summary",
        str(paths.markdown_summary),
        "--expected-mode",
        mode,
    ]
    if require_passed:
        artifact_command.append("--require-passed")

    commands = [
        [sys.executable, "scripts/check_all.py", mode_flag, "--json-report", str(paths.json_report)],
        [
            sys.executable,
            "scripts/summarize_quality_report.py",
            "--input",
            str(paths.json_report),
            "--output",
            str(paths.markdown_summary),
        ],
        artifact_command,
    ]
    if compare_to:
        comparison_command = [
            sys.executable,
            "scripts/compare_quality_reports.py",
            "--base",
            str(resolve_repo_path(compare_to)),
            "--current",
            str(paths.json_report),
            "--output",
            str(paths.comparison_report),
            "--json-output",
            str(paths.comparison_json),
        ]
        if fail_on_regression:
            comparison_command.append("--fail-on-regression")
        commands.append(comparison_command)
    if write_index or write_plan:
        commands.append(
            [
                sys.executable,
                "scripts/index_self_checks.py",
                "--input-dir",
                str(paths.output_dir),
                "--output",
                str(paths.history_index),
                "--markdown-output",
                str(paths.history_markdown),
            ]
        )
    if write_plan:
        plan_command = [
            sys.executable,
            "scripts/plan_self_check_improvements.py",
            "--index",
            str(paths.history_index),
            "--output",
            str(paths.improvement_plan),
            "--json-output",
            str(paths.improvement_json),
        ]
        if compare_to:
            plan_command.extend(["--comparison", str(paths.comparison_json)])
        commands.append(plan_command)
        commands.append(
            [
                sys.executable,
                "scripts/check_improvement_plan_commands.py",
                "--plan-json",
                str(paths.improvement_json),
            ]
        )
    return commands


def run_commands(commands: list[list[str]], *, dry_run: bool) -> None:
    for command in commands:
        print(">", " ".join(command), flush=True)
        if not dry_run:
            subprocess.run(command, cwd=ROOT, check=True)


def next_command_from_plan(plan_path: Path) -> dict[str, str] | None:
    if not plan_path.exists():
        return None
    payload = json.loads(plan_path.read_text(encoding="utf-8"))
    items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        return None
    for item in items:
        if not isinstance(item, dict):
            continue
        command = item.get("command")
        if isinstance(command, str) and command:
            return {
                "priority": str(item.get("priority") or ""),
                "title": str(item.get("title") or ""),
                "command": command,
            }
    return None


def repo_display_path(path: Path) -> str:
    resolved = path if path.is_absolute() else ROOT / path
    return resolved.relative_to(ROOT).as_posix() if resolved.is_relative_to(ROOT) else resolved.as_posix()


def write_next_command_artifacts(paths: SelfCheckPaths, next_command: dict[str, str] | None) -> None:
    if next_command:
        payload = {
            "status": "available",
            "source_plan": repo_display_path(paths.improvement_json),
            "priority": next_command["priority"],
            "title": next_command["title"],
            "command": next_command["command"],
        }
        markdown = "\n".join(
            [
                "# Self-Check Next Command",
                "",
                "- Status: `available`",
                f"- Source plan: `{payload['source_plan']}`",
                f"- Priority: `{payload['priority']}`",
                f"- Title: `{payload['title']}`",
                "",
                "```powershell",
                payload["command"],
                "```",
                "",
            ]
        )
    else:
        payload = {
            "status": "none",
            "source_plan": repo_display_path(paths.improvement_json),
            "priority": "",
            "title": "",
            "command": "",
        }
        markdown = "\n".join(
            [
                "# Self-Check Next Command",
                "",
                "- Status: `none`",
                f"- Source plan: `{payload['source_plan']}`",
                "",
            ]
        )
    paths.next_command_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    paths.next_command_markdown.write_text(markdown, encoding="utf-8")


def artifact_entry(name: str, path: Path) -> dict[str, object]:
    return {"name": name, "path": repo_display_path(path), "exists": path.exists()}


def write_manifest_artifacts(
    paths: SelfCheckPaths,
    *,
    mode: str,
    compare_state: str,
    next_command: dict[str, str] | None,
) -> None:
    artifacts = [
        artifact_entry("quality_json", paths.json_report),
        artifact_entry("quality_summary", paths.markdown_summary),
        artifact_entry("comparison_markdown", paths.comparison_report),
        artifact_entry("comparison_json", paths.comparison_json),
        artifact_entry("history_index", paths.history_index),
        artifact_entry("history_markdown", paths.history_markdown),
        artifact_entry("improvement_plan", paths.improvement_plan),
        artifact_entry("improvement_json", paths.improvement_json),
        artifact_entry("next_command_json", paths.next_command_json),
        artifact_entry("next_command_markdown", paths.next_command_markdown),
    ]
    payload = {
        "status": "passed",
        "mode": mode,
        "compare_state": compare_state,
        "artifact_count": len(artifacts),
        "artifacts": artifacts,
        "next_command": next_command
        or {
            "priority": "",
            "title": "",
            "command": "",
        },
    }
    lines = [
        "# Self-Check Manifest",
        "",
        f"- Status: `{payload['status']}`",
        f"- Mode: `{mode}`",
        f"- Compare state: `{compare_state}`",
        f"- Artifact count: {len(artifacts)}",
        "",
        "## Artifacts",
        "",
        "| Name | Path | Exists |",
        "| --- | --- | --- |",
    ]
    for artifact in artifacts:
        lines.append(f"| {artifact['name']} | `{artifact['path']}` | {str(artifact['exists']).lower()} |")
    if next_command:
        lines.extend(
            [
                "",
                "## Next Command",
                "",
                f"- Priority: `{next_command['priority']}`",
                f"- Title: `{next_command['title']}`",
                "",
                "```powershell",
                next_command["command"],
                "```",
                "",
            ]
        )
    else:
        lines.extend(["", "## Next Command", "", "- None", ""])
    paths.manifest_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    paths.manifest_markdown.write_text("\n".join(lines), encoding="utf-8")


def validate_manifest_artifact(path: Path) -> None:
    command = [sys.executable, "scripts/check_self_check_manifest.py", "--manifest-json", str(path)]
    print(">", " ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the self-check evidence loop and validate its artifacts.")
    parser.add_argument("--mode", choices=sorted(SUPPORTED_MODES), default="quick", help="Quality gate mode to run.")
    parser.add_argument("--output-dir", type=Path, default=Path(".pytest_tmp/self_check"), help="Directory for JSON and Markdown artifacts.")
    comparison = parser.add_mutually_exclusive_group()
    comparison.add_argument("--compare-to", type=Path, help="Optional baseline JSON report for comparison against the new report.")
    comparison.add_argument(
        "--compare-latest",
        action="store_true",
        help="Compare against the existing check_all_<mode>.json in the output directory, when one exists.",
    )
    parser.add_argument("--fail-on-regression", action="store_true", help="Fail comparison when failed or missing gates are detected.")
    parser.add_argument("--write-index", action="store_true", help="Refresh self_check_index.json and self_check_index.md in the output directory.")
    parser.add_argument("--write-plan", action="store_true", help="Write a self-check improvement plan from the refreshed history index.")
    parser.add_argument("--allow-failed", action="store_true", help="Allow a failed check_all report to be summarized and validated structurally.")
    parser.add_argument("--dry-run", action="store_true", help="Print the planned commands without executing them.")
    args = parser.parse_args()

    paths = build_paths(args.output_dir, args.mode)
    paths.output_dir.mkdir(parents=True, exist_ok=True)
    compare_to = args.compare_to
    auto_compare_skipped = False
    if args.compare_latest:
        compare_to = prepare_latest_baseline(paths, args.mode, dry_run=args.dry_run)
        auto_compare_skipped = compare_to is None
    if compare_to and not args.dry_run:
        baseline = resolve_repo_path(compare_to)
        if not baseline.exists():
            raise SystemExit(f"Comparison baseline does not exist: {baseline}")
    commands = build_commands(
        args.mode,
        paths,
        require_passed=not args.allow_failed,
        compare_to=compare_to,
        fail_on_regression=args.fail_on_regression,
        write_index=args.write_index,
        write_plan=args.write_plan,
    )
    run_commands(commands, dry_run=args.dry_run)
    if args.compare_latest:
        compare_state = "skipped_no_previous_report" if auto_compare_skipped else "latest"
    elif compare_to:
        compare_state = "manual"
    else:
        compare_state = "not_requested"

    print("self_check=planned" if args.dry_run else "self_check=passed")
    print(f"mode={args.mode}")
    print(f"json_report={paths.json_report}")
    print(f"markdown_summary={paths.markdown_summary}")
    if args.compare_latest:
        if auto_compare_skipped:
            print("auto_compare=skipped reason=no_previous_report")
        else:
            print(f"auto_compare=enabled baseline={resolve_repo_path(compare_to)}")
    if compare_to:
        print(f"comparison_report={paths.comparison_report}")
        print(f"comparison_json={paths.comparison_json}")
    if args.write_index:
        print(f"history_index={paths.history_index}")
        print(f"history_markdown={paths.history_markdown}")
    if args.write_plan:
        print(f"improvement_plan={paths.improvement_plan}")
        print(f"improvement_json={paths.improvement_json}")
        next_command = None if args.dry_run else next_command_from_plan(paths.improvement_json)
        if next_command:
            print(f"next_command_priority={next_command['priority']}")
            print(f"next_command_title={next_command['title']}")
            print(f"next_command={next_command['command']}")
        elif args.dry_run:
            print("next_command=unavailable reason=dry_run")
        else:
            print("next_command=none")
        if not args.dry_run:
            write_next_command_artifacts(paths, next_command)
        print(f"next_command_json={paths.next_command_json}")
        print(f"next_command_markdown={paths.next_command_markdown}")
    else:
        next_command = None
    if not args.dry_run:
        write_manifest_artifacts(paths, mode=args.mode, compare_state=compare_state, next_command=next_command)
        validate_manifest_artifact(paths.manifest_json)
    print(f"manifest_json={paths.manifest_json}")
    print(f"manifest_markdown={paths.manifest_markdown}")


if __name__ == "__main__":
    main()
