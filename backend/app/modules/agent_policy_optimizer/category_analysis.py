"""Per-category win/tie/lose analysis between two trials.

Pure module: database, queue, and web framework imports are forbidden here.
"""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Iterable, Mapping

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
    materialized = tuple(cases)
    if len({item.case_id for item in materialized}) != len(materialized):
        raise OptimizerInputError("OPTIMIZER_CASE_INVALID", "Case ids must be unique.")
    grouped = _group(materialized)
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
        left_cases = {item.case_id: item for item in left_groups[category]}
        right_cases = {item.case_id: item for item in right_groups[category]}
        if set(left_cases) != set(right_cases):
            raise OptimizerInputError(
                "OPTIMIZER_CASE_INVALID",
                f"Category {category} must compare the same case ids.",
            )
        wins = 0
        ties = 0
        losses = 0
        for case_id in sorted(left_cases):
            left_case = left_cases[case_id]
            right_case = right_cases[case_id]
            if right_case.passed and not left_case.passed:
                wins += 1
            elif left_case.passed and not right_case.passed:
                losses += 1
            else:
                ties += 1
        left_rate = sum(1 for item in left_cases.values() if item.passed) / len(left_cases)
        right_rate = sum(1 for item in right_cases.values() if item.passed) / len(right_cases)
        left_recall = sum(float(item.source_recall) for item in left_cases.values()) / len(left_cases)
        right_recall = sum(float(item.source_recall) for item in right_cases.values()) / len(right_cases)
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


def serialize_case_results(cases: Iterable[CaseResult]) -> dict[str, object]:
    materialized = tuple(cases)
    grouped = _validate_complete(materialized)
    categories = {
        category: {
            "passed": sum(1 for item in items if item.passed),
            "total": len(items),
            "mean_source_recall": round(
                sum(float(item.source_recall) for item in items) / len(items),
                4,
            ),
        }
        for category, items in sorted(grouped.items())
    }
    return {
        "schema_version": 1,
        "categories": categories,
        "cases": [
            {
                "case_id": item.case_id,
                "category": item.category,
                "passed": item.passed,
                "source_recall": float(item.source_recall),
                "latency_ms": float(item.latency_ms),
            }
            for item in sorted(materialized, key=lambda value: (value.category, value.case_id))
        ],
    }


def deserialize_case_results(payload: Mapping[str, object]) -> tuple[CaseResult, ...]:
    if payload.get("schema_version") != 1 or not isinstance(payload.get("cases"), list):
        raise OptimizerInputError(
            "OPTIMIZER_CASE_INVALID",
            "Persisted category statistics do not contain exact case facts.",
        )
    cases: list[CaseResult] = []
    for raw in payload["cases"]:
        if not isinstance(raw, Mapping) or set(raw) != {
            "case_id",
            "category",
            "passed",
            "source_recall",
            "latency_ms",
        }:
            raise OptimizerInputError("OPTIMIZER_CASE_INVALID", "Persisted case facts are malformed.")
        if type(raw["passed"]) is not bool:
            raise OptimizerInputError("OPTIMIZER_CASE_INVALID", "Persisted case passed state must be boolean.")
        cases.append(
            CaseResult(
                case_id=str(raw["case_id"]),
                category=str(raw["category"]),
                passed=raw["passed"],
                source_recall=float(raw["source_recall"]),
                latency_ms=float(raw["latency_ms"]),
            )
        )
    _validate_complete(cases)
    return tuple(cases)


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


__all__ = [
    "CaseResult",
    "CategoryRow",
    "compare_categories",
    "deserialize_case_results",
    "serialize_case_results",
    "summarize_categories",
]
