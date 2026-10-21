from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def resolve_repo_path(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def load_report(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Quality report must be a JSON object.")
    gates = payload.get("gates")
    if not isinstance(gates, list):
        raise ValueError("Quality report must include a gates list.")
    return payload


def gate_map(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    gates: dict[str, dict[str, Any]] = {}
    occurrences: dict[str, int] = {}
    for gate in report.get("gates", []):
        if isinstance(gate, dict) and gate.get("name"):
            name = str(gate["name"])
            occurrences[name] = occurrences.get(name, 0) + 1
            key = name if occurrences[name] == 1 else f"{name} #{occurrences[name]}"
            gates[key] = gate
    return gates


def duration(value: object) -> float | None:
    if isinstance(value, int | float):
        return float(value)
    return None


def compare_reports(base: dict[str, Any], current: dict[str, Any], *, slow_threshold_sec: float) -> dict[str, Any]:
    base_gates = gate_map(base)
    current_gates = gate_map(current)
    status_changes: list[dict[str, str]] = []
    slower_gates: list[dict[str, float | str]] = []
    missing_gates = sorted(set(base_gates) - set(current_gates))
    new_gates = sorted(set(current_gates) - set(base_gates))

    for name in sorted(set(base_gates) & set(current_gates)):
        old_status = str(base_gates[name].get("status", "unknown"))
        new_status = str(current_gates[name].get("status", "unknown"))
        if old_status != new_status:
            status_changes.append({"gate": name, "from": old_status, "to": new_status})

        old_duration = duration(base_gates[name].get("duration_sec"))
        new_duration = duration(current_gates[name].get("duration_sec"))
        if old_duration is not None and new_duration is not None:
            delta = new_duration - old_duration
            if delta >= slow_threshold_sec:
                slower_gates.append({"gate": name, "base_sec": old_duration, "current_sec": new_duration, "delta_sec": delta})

    regression_count = len(missing_gates) + sum(1 for change in status_changes if change["to"] == "failed")
    return {
        "base_mode": base.get("mode"),
        "current_mode": current.get("mode"),
        "base_status": base.get("status"),
        "current_status": current.get("status"),
        "base_gate_count": len(base_gates),
        "current_gate_count": len(current_gates),
        "missing_gates": missing_gates,
        "new_gates": new_gates,
        "status_changes": status_changes,
        "slower_gates": slower_gates,
        "regression_count": regression_count,
    }


def render_markdown(comparison: dict[str, Any], *, base_path: Path, current_path: Path) -> str:
    lines = [
        "# Quality Gate Comparison",
        "",
        f"- Base: `{base_path.as_posix()}`",
        f"- Current: `{current_path.as_posix()}`",
        f"- Base mode/status: `{comparison['base_mode']}` / `{comparison['base_status']}`",
        f"- Current mode/status: `{comparison['current_mode']}` / `{comparison['current_status']}`",
        f"- Base gates: {comparison['base_gate_count']}",
        f"- Current gates: {comparison['current_gate_count']}",
        f"- Regression count: {comparison['regression_count']}",
        "",
        "## Status Changes",
        "",
    ]
    status_changes = comparison["status_changes"]
    if status_changes:
        lines.extend(f"- `{item['gate']}`: `{item['from']}` -> `{item['to']}`" for item in status_changes)
    else:
        lines.append("- No status changes.")

    lines.extend(["", "## Gate Set Changes", ""])
    missing = comparison["missing_gates"]
    new = comparison["new_gates"]
    lines.append(f"- Missing gates: {', '.join(f'`{gate}`' for gate in missing) if missing else 'none'}")
    lines.append(f"- New gates: {', '.join(f'`{gate}`' for gate in new) if new else 'none'}")

    lines.extend(["", "## Slower Gates", ""])
    slower = comparison["slower_gates"]
    if slower:
        for item in slower:
            lines.append(
                "- `{gate}`: {base:.2f}s -> {current:.2f}s (+{delta:.2f}s)".format(
                    gate=item["gate"],
                    base=item["base_sec"],
                    current=item["current_sec"],
                    delta=item["delta_sec"],
                )
            )
    else:
        lines.append("- No gate exceeded the configured slowdown threshold.")

    lines.extend(["", "## Optimization Focus", ""])
    if comparison["regression_count"]:
        lines.append("- Fix failed or missing gates before treating the current run as release evidence.")
    elif slower:
        lines.append("- Review slower gates and decide whether the increase is expected or needs optimization.")
    else:
        lines.append("- No regression was detected by this comparison.")
    lines.append("")
    return "\n".join(lines)


def repo_display(path: Path) -> Path:
    resolved = resolve_repo_path(path)
    return resolved.relative_to(ROOT) if resolved.is_relative_to(ROOT) else resolved


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare two check_all JSON quality reports.")
    parser.add_argument("--base", required=True, type=Path, help="Older/baseline quality JSON report.")
    parser.add_argument("--current", required=True, type=Path, help="Newer/current quality JSON report.")
    parser.add_argument("--output", type=Path, help="Optional Markdown comparison output path.")
    parser.add_argument("--json-output", type=Path, help="Optional machine-readable comparison output path.")
    parser.add_argument("--slow-threshold-sec", type=float, default=5.0, help="Minimum duration increase to list as slower.")
    parser.add_argument("--fail-on-regression", action="store_true", help="Exit non-zero if failed or missing gates are detected.")
    args = parser.parse_args()

    base_path = resolve_repo_path(args.base)
    current_path = resolve_repo_path(args.current)
    comparison = compare_reports(load_report(base_path), load_report(current_path), slow_threshold_sec=args.slow_threshold_sec)
    markdown = render_markdown(comparison, base_path=repo_display(args.base), current_path=repo_display(args.current))
    print(markdown)

    if args.output:
        output_path = resolve_repo_path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown, encoding="utf-8")
        print(f"comparison_report={output_path}")
    if args.json_output:
        json_output_path = resolve_repo_path(args.json_output)
        json_output_path.parent.mkdir(parents=True, exist_ok=True)
        json_output_path.write_text(json.dumps(comparison, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"comparison_json={json_output_path}")

    print(f"regression_count={comparison['regression_count']}")
    if args.fail_on_regression and comparison["regression_count"]:
        print("quality_comparison=failed")
        raise SystemExit(1)
    print("quality_comparison=passed")


if __name__ == "__main__":
    main()
