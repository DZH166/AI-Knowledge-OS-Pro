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
    lines.extend(
        _table(
            ["metric", "direction"] + list(columns) + ["best"],
            (
                [row["metric"], row["direction"], *row["values"], row["best"]]
                for row in metric_rows
            ),
        )
    )
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
                ["category", *[f"pass_rate {column}" for column in columns[:2]] + ["verdict"]]
                if len(columns) >= 2
                else ["category", "verdict"],
                (
                    [row["category"], *row["pass_rates"], row["verdict"]]
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

    return "\n".join(lines).rstrip() + "\n"


__all__ = ["render_comparison_markdown"]
