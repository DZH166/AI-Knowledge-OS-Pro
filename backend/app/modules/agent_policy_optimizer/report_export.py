"""Deterministic Markdown rendering for trial comparison reports.

Pure module: database, queue, web framework imports, clock access, and user
free-text are forbidden here — only structured field values are rendered, so
the same inputs always produce byte-identical output.
"""

from __future__ import annotations

from typing import Iterable, Mapping, Sequence


def _row(cells: Sequence[object]) -> str:
    return "| " + " | ".join(str(cell) for cell in cells) + " |"


def _table(header: Sequence[str], rows: Iterable[Sequence[object]]) -> list[str]:
    lines = [_row(header), _row(["---"] * len(header))]
    lines.extend(_row(row) for row in rows)
    return lines


def render_comparison_markdown(
    *,
    title: str,
    columns: Sequence[str],
    metric_rows: Sequence[Mapping[str, object]],
    gate_rows: Sequence[Mapping[str, object]],
    category_rows: Sequence[Mapping[str, object]] | None = None,
    failure_rows: Sequence[Mapping[str, object]] | None = None,
) -> str:
    """Render the fixed-section comparison report.

    Sections: title, trials, metrics (with direction and best column), hard
    gates, optional category win/tie/lose table, optional failed-case lists.
    """

    lines: list[str] = [f"# {title}", ""]
    lines.append("## Trials")
    lines.extend(_table(["#", "trial"], list(enumerate(columns, start=1))))
    lines.append("")

    lines.append("## Metrics")
    delta_headers = [f"delta vs trial 1 ({column})" for column in columns[1:]]
    lines.extend(
        _table(
            ["metric", "direction"] + list(columns) + delta_headers + ["best"],
            (
                [
                    row["metric"],
                    row["direction"],
                    *row["values"],
                    *row.get("deltas", ()),
                    row["best"],
                ]
                for row in metric_rows
            ),
        )
    )
    lines.append("")

    lines.append("## Gate changes")
    changed_gates = [row for row in gate_rows if row.get("changed")]
    if changed_gates:
        lines.extend(
            _table(
                ["gate", *columns],
                ([row["gate"], *row["values"]] for row in changed_gates),
            )
        )
    else:
        lines.append("No Hard Gate changes.")
    lines.append("")

    lines.append("## Hard gates")
    lines.extend(
        _table(
            ["gate", *columns],
            ([row["gate"], *row["values"]] for row in gate_rows),
        )
    )
    lines.append("")

    if category_rows:
        lines.append("## Categories (vs first column)")
        lines.extend(
            _table(
                [
                    "category",
                    *[f"pass_rate {column}" for column in columns[:2]],
                    "wins",
                    "ties",
                    "losses",
                    "verdict",
                ]
                if len(columns) >= 2
                else ["category", "verdict"],
                (
                    [
                        row["category"],
                        *row["pass_rates"],
                        row["wins"],
                        row["ties"],
                        row["losses"],
                        row["verdict"],
                    ]
                    if len(columns) >= 2
                    else [row["category"], row["verdict"]]
                    for row in category_rows
                ),
            )
        )
        lines.append("")

    if failure_rows:
        lines.append("## Failed cases")
        for row in failure_rows:
            failed = row["failed_case_ids"]
            rendered = ", ".join(str(item) for item in failed) if failed else "(none)"
            lines.append(f"- {row['trial']}: {rendered}")
        lines.append("")
        baseline_failures = set(failure_rows[0]["failed_case_ids"])
        lines.append("## New failures")
        for row in failure_rows[1:]:
            added = sorted(set(row["failed_case_ids"]) - baseline_failures)
            lines.append(f"- {row['trial']}: {', '.join(added) if added else '(none)'}")
        lines.append("")
        lines.append("## Resolved failures")
        for row in failure_rows[1:]:
            resolved = sorted(baseline_failures - set(row["failed_case_ids"]))
            lines.append(f"- {row['trial']}: {', '.join(resolved) if resolved else '(none)'}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


__all__ = ["render_comparison_markdown"]
