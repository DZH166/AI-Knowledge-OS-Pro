"""Per-category win/tie/lose analysis between two trials.

Pure module: database, queue, and web framework imports are forbidden here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from app.modules.agent_control.report import EXPECTED_CATEGORY_COUNTS
from app.modules.agent_policy_optimizer.contracts import OptimizerInputError


@dataclass(frozen=True, slots=True)
class CaseResult:
    case_id: str
    category: str
    passed: bool
    source_recall: float
    latency_ms: float

    def __post_init__(self) -> None:
        if not self.case_id or not self.category:
            raise OptimizerInputError("OPTIMIZER_CASE_INVALID", "Case id and category are required.")
        for name, value in (
            ("source_recall", self.source_recall),
            ("latency_ms", self.latency_ms),
        ):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise OptimizerInputError("OPTIMIZER_CASE_INVALID", f"{name} must be a number.")
            number = float(value)
            if number != number or number in (float("inf"), float("-inf")):
                raise OptimizerInputError("OPTIMIZER_CASE_INVALID", f"{name} must be finite.")


@dataclass(frozen=True, slots=True)
class CategoryRow:
    category: str
    case_count: int
    pass_rate_left: float
    pass_rate_right: float
    mean_source_recall_left: float
    mean_source_recall_right: float
    wins: int
    ties: int
    losses: int
    verdict: str


def _group(cases: Iterable[CaseResult]) -> dict[str, list[CaseResult]]:
    grouped: dict[str, list[CaseResult]] = {category: [] for category in EXPECTED_CATEGORY_COUNTS}
    for item in cases:
        if item.category not in grouped:
            raise OptimizerInputError(
                "OPTIMIZER_CASE_INVALID",
                f"Unknown case category: {item.category}.",
            )
        grouped[item.category].append(item)
    return grouped


def _validate_complete(cases: Iterable[CaseResult]) -> dict[str, list[CaseResult]]:
    grouped = _group(cases)
    for category, expected in EXPECTED_CATEGORY_COUNTS.items():
        if len(grouped[category]) != expected:
            raise OptimizerInputError(
                "OPTIMIZER_CASE_INVALID",
                f"Category {category} must contain exactly {expected} cases.",
            )
    return grouped


def compare_categories(left: Iterable[CaseResult], right: Iterable[CaseResult]) -> tuple[CategoryRow, ...]:
    """Compare two complete 60-case results per category.

    left is the reference (typically the baseline trial); right is the
    candidate. verdict compares per-category pass rates.
    """

    left_groups = _validate_complete(left)
    right_groups = _validate_complete(right)
    rows: list[CategoryRow] = []
    for category in sorted(EXPECTED_CATEGORY_COUNTS):
        left_cases = left_groups[category]
        right_cases = right_groups[category]
        wins = 0
        ties = 0
        losses = 0
        for left_case, right_case in zip(left_cases, right_cases, strict=True):
            if right_case.passed and not left_case.passed:
                wins += 1
            elif left_case.passed and not right_case.passed:
                losses += 1
            else:
                ties += 1
        left_rate = sum(1 for item in left_cases if item.passed) / len(left_cases)
        right_rate = sum(1 for item in right_cases if item.passed) / len(right_cases)
        left_recall = sum(float(item.source_recall) for item in left_cases) / len(left_cases)
        right_recall = sum(float(item.source_recall) for item in right_cases) / len(right_cases)
        if right_rate > left_rate:
            verdict = "improved"
        elif right_rate < left_rate:
            verdict = "regressed"
        else:
            verdict = "tied"
        rows.append(
            CategoryRow(
                category=category,
                case_count=len(left_cases),
                pass_rate_left=left_rate,
                pass_rate_right=right_rate,
                mean_source_recall_left=left_recall,
                mean_source_recall_right=right_recall,
                wins=wins,
                ties=ties,
                losses=losses,
                verdict=verdict,
            )
        )
    return tuple(rows)


def summarize_categories(left: Iterable[CaseResult], right: Iterable[CaseResult]) -> dict[str, object]:
    """Render a compact rationale fragment for the recommendation payload."""

    rows = compare_categories(left, right)
    improved = tuple(row.category for row in rows if row.verdict == "improved")
    regressed = tuple(row.category for row in rows if row.verdict == "regressed")
    tied = tuple(row.category for row in rows if row.verdict == "tied")
    parts: list[str] = []
    if improved:
        parts.append(f"improved categories: {', '.join(improved)}")
    if regressed:
        parts.append(f"regressed categories: {', '.join(regressed)}")
    if tied and not improved and not regressed:
        parts.append("all categories tied with the baseline")
    sentence = ("Category-level comparison - " + "; ".join(parts) + ".") if parts else ""
    return {
        "improved": improved,
        "regressed": regressed,
        "tied": tied,
        "sentence": sentence,
    }


__all__ = ["CaseResult", "CategoryRow", "compare_categories", "summarize_categories"]
