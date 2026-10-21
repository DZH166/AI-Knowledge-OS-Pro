from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def resolve_repo_path(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def format_duration(value: object) -> str:
    if isinstance(value, int | float):
        return f"{value:.2f}s"
    return "-"


def load_report(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Quality report must be a JSON object.")
    gates = payload.get("gates")
    if not isinstance(gates, list):
        raise ValueError("Quality report must include a gates list.")
    return payload


def gate_counts(gates: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"passed": 0, "failed": 0, "skipped": 0, "other": 0}
    for gate in gates:
        status = str(gate.get("status", "other"))
        if status in counts:
            counts[status] += 1
        else:
            counts["other"] += 1
    return counts


def git_summary(payload: dict[str, Any]) -> dict[str, object]:
    raw_git = payload.get("git")
    return raw_git if isinstance(raw_git, dict) else {}


def format_dirty(value: object) -> str:
    if value is True:
        return "yes"
    if value is False:
        return "no"
    return "unknown"


def render_next_actions(gates: list[dict[str, Any]], *, mode: str) -> list[str]:
    failed = [gate for gate in gates if gate.get("status") == "failed"]
    skipped = [gate for gate in gates if gate.get("status") == "skipped"]
    if failed:
        return [
            f"Fix `{gate.get('name', 'unknown')}`: {gate.get('next_step') or 'Review the failure output and rerun the gate.'}"
            for gate in failed
        ]
    if skipped:
        return [
            f"Re-run `{gate.get('name', 'unknown')}` when the skipped dependency or release scope is required."
            for gate in skipped
        ]
    return [
        "No failed gates were reported.",
        f"Use this report as the {mode} baseline, then run the next broader gate before publishing a release.",
    ]


def render_markdown(payload: dict[str, Any], *, source: Path) -> str:
    raw_gates = payload.get("gates", [])
    gates = [gate for gate in raw_gates if isinstance(gate, dict)]
    counts = gate_counts(gates)
    git = git_summary(payload)
    lines = [
        "# Quality Gate Summary",
        "",
        f"- Source: `{source.as_posix()}`",
        f"- Mode: `{payload.get('mode', 'unknown')}`",
        f"- Status: `{payload.get('status', 'unknown')}`",
        f"- Generated at: `{payload.get('generated_at', 'unknown')}`",
        f"- Git branch: `{git.get('branch', 'unknown')}`",
        f"- Git commit: `{git.get('short_commit') or git.get('commit') or 'unknown'}`",
        f"- Git dirty: `{format_dirty(git.get('dirty'))}`",
        f"- Gate count: {payload.get('gate_count', len(gates))}",
        f"- Passed: {counts['passed']}",
        f"- Failed: {counts['failed']}",
        f"- Skipped: {counts['skipped']}",
        "",
        "## Gate Results",
        "",
        "| Gate | Status | Duration | Failure Reason | Next Step |",
        "| --- | --- | ---: | --- | --- |",
    ]
    for gate in gates:
        lines.append(
            "| {name} | {status} | {duration} | {reason} | {next_step} |".format(
                name=gate.get("name", "unknown"),
                status=gate.get("status", "unknown"),
                duration=format_duration(gate.get("duration_sec")),
                reason=gate.get("failure_reason") or "-",
                next_step=gate.get("next_step") or "-",
            )
        )

    lines.extend(["", "## Optimization Focus", ""])
    lines.extend(f"- {item}" for item in render_next_actions(gates, mode=str(payload.get("mode", "unknown"))))
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize a check_all JSON quality gate report as Markdown.")
    parser.add_argument("--input", required=True, type=Path, help="Path to a check_all --json-report output file.")
    parser.add_argument("--output", type=Path, help="Optional Markdown output path.")
    args = parser.parse_args()

    input_path = resolve_repo_path(args.input)
    payload = load_report(input_path)
    markdown = render_markdown(payload, source=input_path.relative_to(ROOT) if input_path.is_relative_to(ROOT) else input_path)
    print(markdown)
    if args.output:
        output_path = resolve_repo_path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown, encoding="utf-8")
        print(f"summary_report={output_path}")
    print("quality_summary=passed")


if __name__ == "__main__":
    main()
