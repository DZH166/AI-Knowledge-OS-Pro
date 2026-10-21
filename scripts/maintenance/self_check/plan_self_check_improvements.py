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


def resolve_repo_path(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def add_item(items: list[dict[str, str]], priority: str, title: str, evidence: str, action: str, command: str = "") -> None:
    items.append({"priority": priority, "title": title, "evidence": evidence, "action": action, "command": command})


def latest_mode(latest: dict[str, Any] | None) -> str:
    mode = latest.get("mode") if latest else None
    return str(mode) if mode in {"quick", "release", "full"} else "quick"


def source_output_dir(index: dict[str, Any]) -> str:
    value = index.get("input_dir")
    return str(value) if value else ".pytest_tmp/self_check"


def compare_latest_command(mode: str, output_dir: str) -> str:
    return f"python scripts/run_self_check.py --mode {mode} --output-dir {output_dir} --compare-latest --write-index --write-plan --fail-on-regression"


def broaden_scope_command(mode: str) -> str:
    if mode == "quick":
        return "python scripts/run_self_check.py --mode release --output-dir .pytest_tmp/self_check_release --write-index --write-plan"
    if mode == "release":
        return "python scripts/run_self_check.py --mode full --output-dir .pytest_tmp/self_check_full --write-index --write-plan"
    return ""


def broaden_scope_action(mode: str) -> str:
    if mode == "quick":
        return "Use the healthy quick baseline, then run release or full gates before publishing a release."
    if mode == "release":
        return "Use the healthy release baseline, then run the full gate before publishing a release."
    return "Use the healthy full baseline as release evidence; rerun with comparison after meaningful changes."


def build_plan(index: dict[str, Any], comparison: dict[str, Any] | None = None) -> dict[str, Any]:
    items: list[dict[str, str]] = []
    run_count = int(index.get("run_count") or 0)
    failed_runs = int(index.get("failed_runs") or 0)
    regression_runs = int(index.get("regression_runs") or 0)
    latest = index.get("latest_run") if isinstance(index.get("latest_run"), dict) else None
    mode = latest_mode(latest)
    output_dir = source_output_dir(index)

    if run_count == 0:
        add_item(
            items,
            "P0",
            "Generate the first self-check run",
            "The self-check history index has no runs.",
            "Run the one-command quick self-check and write both history index and improvement plan artifacts.",
            f"python scripts/run_self_check.py --mode quick --output-dir {output_dir} --write-index --write-plan",
        )
    if failed_runs:
        add_item(
            items,
            "P0",
            "Inspect failed self-check runs",
            f"The history index reports {failed_runs} failed run(s).",
            "Open the failed run JSON/Markdown artifacts and fix the first failed gate before release work.",
        )
    if regression_runs:
        add_item(
            items,
            "P0",
            "Review regression comparison reports",
            f"The history index reports {regression_runs} run(s) with regressions.",
            "Open comparison Markdown reports and resolve failed or missing gates before promoting the branch.",
        )
    if latest and latest.get("status") == "passed" and latest.get("regression_count") is None:
        add_item(
            items,
            "P2",
            "Add a comparison baseline",
            "The latest run passed but was not compared against a baseline.",
            "Rerun self-check with `--compare-latest` after at least one report exists in the output directory.",
            compare_latest_command(mode, output_dir),
        )

    if comparison:
        status_changes = comparison.get("status_changes") if isinstance(comparison.get("status_changes"), list) else []
        missing = comparison.get("missing_gates") if isinstance(comparison.get("missing_gates"), list) else []
        slower = comparison.get("slower_gates") if isinstance(comparison.get("slower_gates"), list) else []
        if status_changes:
            add_item(
                items,
                "P0",
                "Resolve gate status changes",
                f"Comparison reports {len(status_changes)} status change(s).",
                "Inspect each changed gate and fix failed-current gates before release evidence is accepted.",
            )
        if missing:
            add_item(
                items,
                "P1",
                "Restore missing quality gates",
                f"Comparison reports missing gates: {', '.join(str(gate) for gate in missing)}.",
                "Confirm whether gates were intentionally removed; otherwise restore them to the self-check flow.",
            )
        if slower:
            add_item(
                items,
                "P2",
                "Review slower quality gates",
                f"Comparison reports {len(slower)} slower gate(s).",
                "Check whether duration growth is expected; optimize or document the slow gate if it affects developer feedback.",
            )

    if not items:
        add_item(
            items,
            "P3",
            "Broaden validation scope",
            "The indexed self-check runs have no failures or regressions.",
            broaden_scope_action(mode),
            broaden_scope_command(mode),
        )

    return {
        "source_index": index.get("input_dir"),
        "run_count": run_count,
        "failed_runs": failed_runs,
        "regression_runs": regression_runs,
        "item_count": len(items),
        "items": items,
    }


def render_markdown(plan: dict[str, Any]) -> str:
    lines = [
        "# Self-Check Improvement Plan",
        "",
        f"- Source index: `{plan.get('source_index')}`",
        f"- Runs: {plan.get('run_count')}",
        f"- Failed runs: {plan.get('failed_runs')}",
        f"- Regression runs: {plan.get('regression_runs')}",
        f"- Items: {plan.get('item_count')}",
        "",
        "## Recommended Actions",
        "",
        "| Priority | Action | Evidence | Next Step | Command |",
        "| --- | --- | --- | --- | --- |",
    ]
    for item in plan["items"]:
        command = f"`{item['command']}`" if item.get("command") else "-"
        lines.append(f"| {item['priority']} | {item['title']} | {item['evidence']} | {item['action']} | {command} |")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a data-driven improvement plan from self-check artifacts.")
    parser.add_argument("--index", required=True, type=Path, help="Path to self_check_index.json.")
    parser.add_argument("--comparison", type=Path, help="Optional quality comparison JSON.")
    parser.add_argument("--output", type=Path, help="Optional Markdown output path.")
    parser.add_argument("--json-output", type=Path, help="Optional JSON output path.")
    args = parser.parse_args()

    index_path = resolve_repo_path(args.index)
    comparison = load_json(resolve_repo_path(args.comparison)) if args.comparison else None
    plan = build_plan(load_json(index_path), comparison)
    markdown = render_markdown(plan)
    print(markdown)

    if args.output:
        output_path = resolve_repo_path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown, encoding="utf-8")
        print(f"improvement_plan={output_path}")
    if args.json_output:
        json_output_path = resolve_repo_path(args.json_output)
        json_output_path.parent.mkdir(parents=True, exist_ok=True)
        json_output_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"improvement_plan_json={json_output_path}")
    print("self_check_improvement_plan=passed")


if __name__ == "__main__":
    main()
