from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def resolve_repo_path(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def quality_reports(input_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in input_dir.rglob("check_all_*.json")
        if not path.name.endswith("_comparison.json") and not any(part.startswith("test_") for part in path.relative_to(input_dir).parts)
    )


def comparison_for(report_path: Path) -> Path | None:
    candidate = report_path.with_name(report_path.stem + "_comparison.json")
    return candidate if candidate.exists() else None


def git_metadata(report: dict[str, Any]) -> dict[str, Any]:
    raw_git = report.get("git")
    if not isinstance(raw_git, dict):
        return {"branch": None, "commit": None, "short_commit": None, "dirty": None}
    return {
        "branch": raw_git.get("branch"),
        "commit": raw_git.get("commit"),
        "short_commit": raw_git.get("short_commit"),
        "dirty": raw_git.get("dirty"),
    }


def format_dirty(value: object) -> str:
    if value is True:
        return "yes"
    if value is False:
        return "no"
    return "unknown"


def format_git_label(git: dict[str, Any]) -> str:
    branch = git.get("branch") or "-"
    commit = git.get("short_commit") or git.get("commit") or "-"
    return f"{branch}@{commit}" if branch != "-" or commit != "-" else "-"


def build_run_record(report_path: Path) -> dict[str, Any]:
    report = load_json(report_path)
    comparison_path = comparison_for(report_path)
    comparison = load_json(comparison_path) if comparison_path else None
    return {
        "path": report_path.relative_to(ROOT).as_posix() if report_path.is_relative_to(ROOT) else report_path.as_posix(),
        "mode": report.get("mode"),
        "status": report.get("status"),
        "generated_at": report.get("generated_at"),
        "git": git_metadata(report),
        "gate_count": report.get("gate_count"),
        "failed_gates": [gate.get("name") for gate in report.get("gates", []) if isinstance(gate, dict) and gate.get("status") == "failed"],
        "comparison_path": comparison_path.relative_to(ROOT).as_posix() if comparison_path and comparison_path.is_relative_to(ROOT) else (comparison_path.as_posix() if comparison_path else None),
        "regression_count": comparison.get("regression_count") if comparison else None,
    }


def build_index(input_dir: Path) -> dict[str, Any]:
    reports = quality_reports(input_dir)
    runs = [build_run_record(path) for path in reports]
    failed_runs = [run for run in runs if run["status"] != "passed"]
    regressions = [run for run in runs if isinstance(run.get("regression_count"), int) and run["regression_count"] > 0]
    latest = max(runs, key=lambda run: str(run.get("generated_at") or "")) if runs else None
    return {
        "input_dir": input_dir.relative_to(ROOT).as_posix() if input_dir.is_relative_to(ROOT) else input_dir.as_posix(),
        "run_count": len(runs),
        "passed_runs": sum(1 for run in runs if run["status"] == "passed"),
        "failed_runs": len(failed_runs),
        "regression_runs": len(regressions),
        "latest_run": latest,
        "runs": runs,
    }


def render_markdown(index: dict[str, Any]) -> str:
    lines = [
        "# Self-Check History Index",
        "",
        f"- Input dir: `{index['input_dir']}`",
        f"- Runs: {index['run_count']}",
        f"- Passed runs: {index['passed_runs']}",
        f"- Failed runs: {index['failed_runs']}",
        f"- Regression runs: {index['regression_runs']}",
        "",
        "## Latest Run",
        "",
    ]
    latest = index.get("latest_run")
    if latest:
        lines.extend(
            [
                f"- Path: `{latest['path']}`",
                f"- Mode: `{latest['mode']}`",
                f"- Status: `{latest['status']}`",
                f"- Generated at: `{latest['generated_at']}`",
                f"- Git: `{format_git_label(latest['git'])}`",
                f"- Git dirty: `{format_dirty(latest['git'].get('dirty'))}`",
                f"- Gate count: {latest['gate_count']}",
                f"- Regression count: {latest['regression_count'] if latest['regression_count'] is not None else 'not compared'}",
            ]
        )
    else:
        lines.append("- No self-check runs found.")

    lines.extend(
        [
            "",
            "## Runs",
            "",
            "| Generated At | Mode | Status | Git | Dirty | Gates | Failed Gates | Regressions |",
            "| --- | --- | --- | --- | --- | ---: | --- | ---: |",
        ]
    )
    for run in index["runs"]:
        failed = ", ".join(f"`{gate}`" for gate in run["failed_gates"]) if run["failed_gates"] else "-"
        regressions = run["regression_count"] if run["regression_count"] is not None else "-"
        lines.append(
            f"| {run['generated_at'] or '-'} | {run['mode'] or '-'} | {run['status'] or '-'} | {format_git_label(run['git'])} | {format_dirty(run['git'].get('dirty'))} | {run['gate_count'] or '-'} | {failed} | {regressions} |"
        )

    lines.extend(["", "## Optimization Focus", ""])
    if index["failed_runs"]:
        lines.append("- Inspect failed runs before promoting the current branch.")
    elif index["regression_runs"]:
        lines.append("- Review comparison reports with regressions before release.")
    elif index["run_count"]:
        lines.append("- No failed or regressed self-check runs were found in this index.")
    else:
        lines.append("- Generate at least one self-check run before using trend evidence.")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Index self-check JSON artifacts into trend-friendly JSON and Markdown.")
    parser.add_argument("--input-dir", required=True, type=Path, help="Directory containing check_all_*.json artifacts.")
    parser.add_argument("--output", type=Path, help="Optional JSON index output path.")
    parser.add_argument("--markdown-output", type=Path, help="Optional Markdown index output path.")
    args = parser.parse_args()

    input_dir = resolve_repo_path(args.input_dir)
    index = build_index(input_dir)
    markdown = render_markdown(index)
    print(markdown)
    if args.output:
        output_path = resolve_repo_path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"self_check_index={output_path}")
    if args.markdown_output:
        markdown_path = resolve_repo_path(args.markdown_output)
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(markdown, encoding="utf-8")
        print(f"self_check_index_markdown={markdown_path}")
    print("self_check_index=passed")


if __name__ == "__main__":
    main()
