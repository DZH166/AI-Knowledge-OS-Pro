"""Recognize conflicts only between simple, equally scoped numeric assertions."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import re


_Context = tuple[tuple[str, ...], str, str, tuple[str, ...]]


@dataclass(frozen=True, slots=True)
class _Assertion:
    context: _Context
    dimension: str
    value: Decimal


_MEASUREMENT = re.compile(
    r"(?<![A-Za-z0-9_.])(?P<value>[+-]?\d+(?:\.\d+)?)\s*"
    r"(?P<unit>milliseconds?|msec|ms|毫秒|seconds?|秒|s|万元|元|yuan|%|％|个|次)"
    r"(?![A-Za-z])",
    re.IGNORECASE,
)
_NON_EXACT = re.compile(
    r"至少|最多|最少|不超过|不高于|不低于|不小于|不是|不为|并非|小于|大于|超过|大约|约|预计|可能|以内|以上|以下|左右|至|到|"
    r"\b(?:between|about|approximately|roughly|under|below|above|over|might|may|not|never)\b|"
    r"\b(?:at least|at most|less than|greater than|no more than)\b|"
    r"\d\s*[-–—~～]\s*\d|[<>≤≥≠]",
    re.IGNORECASE,
)
_BEFORE_ASSERTION_QUALIFIER = re.compile(r"(?:" + _NON_EXACT.pattern + r"|不|未)\s*$", re.IGNORECASE)
# Common metric labels also form simple Chinese assertions without a copula.
# Keep this bounded to nominal labels: arbitrary verb/value phrases could be
# negations, inequalities or qualified measurements rather than exact facts.
_COMPACT_METRIC = re.compile(r"(?:延迟|耗时|超时|成本|金额)$")
# Preserve the known nominal compound 合约金额 while treating a separate 约
# before a metric as approximate; this remains a bounded lexical rule.
_BEFORE_COMPACT_METRIC_QUALIFIER = re.compile(
    r"(?:不|未|无|没(?:有)?|可能|也许|或许|预计|预估|估计|大约|大概|大致|近似|(?<!合)约|至少|最多|最少)"
    r"(?:会|能|曾|应|将|需)?\s*$"
)
_UNIT_SCALE = {
    "milliseconds": ("duration", Decimal("0.001")),
    "millisecond": ("duration", Decimal("0.001")),
    "msec": ("duration", Decimal("0.001")),
    "ms": ("duration", Decimal("0.001")),
    "毫秒": ("duration", Decimal("0.001")),
    "seconds": ("duration", Decimal(1)),
    "second": ("duration", Decimal(1)),
    "s": ("duration", Decimal(1)),
    "秒": ("duration", Decimal(1)),
    "万元": ("yuan", Decimal(10_000)),
    "元": ("yuan", Decimal(1)),
    "yuan": ("yuan", Decimal(1)),
    "%": ("percent", Decimal(1)),
    "％": ("percent", Decimal(1)),
    "个": ("items", Decimal(1)),
    "次": ("occurrences", Decimal(1)),
}


def _assertions(text: str) -> tuple[_Assertion, ...]:
    result: list[_Assertion] = []
    # Multiple measurements can represent independent facts or ranges. Do not
    # infer which surrounding sentences scope which fact in a complex excerpt.
    if len(tuple(_MEASUREMENT.finditer(text))) != 1:
        return ()
    clauses = tuple(clause.strip() for clause in re.split(r"[。；;\n]|(?<!\d)\.(?!\d)", text) if clause.strip())
    normalized_clauses = tuple(" ".join(clause.split()).casefold() for clause in clauses)
    for index, clause in enumerate(clauses):
        measurements = tuple(_MEASUREMENT.finditer(clause))
        if len(measurements) != 1:
            continue
        measurement = measurements[0]
        prefix = clause[:measurement.start()].strip()
        suffix = clause[measurement.end():].strip()
        assertion = re.search(r"(?:为|是|等于|=|:|：|\b(?:is|are|equals?)\b)\s*(?:exactly\s*)?$", prefix, re.IGNORECASE)
        if assertion is None:
            metric = _COMPACT_METRIC.search(prefix)
            if metric is None or _BEFORE_COMPACT_METRIC_QUALIFIER.search(prefix[:metric.start()]):
                continue
            subject_and_scope = prefix
        else:
            subject_and_scope = prefix[:assertion.start()]
        # Qualifiers must touch the assertion/value, not occur inside the
        # subject (for example 合约金额 or 到账耗时) or an earlier load scope.
        if _BEFORE_ASSERTION_QUALIFIER.search(subject_and_scope) or _NON_EXACT.match(suffix):
            continue
        subject_context = " ".join(subject_and_scope.split()).casefold()
        suffix_context = " ".join(suffix.split()).casefold()
        if not subject_context and not suffix_context:
            continue
        # Headings, load conditions, dates and other nonnumeric sentences all
        # participate in the identity, with word boundaries and order intact.
        context = (normalized_clauses[:index], subject_context, suffix_context, normalized_clauses[index + 1:])
        dimension, scale = _UNIT_SCALE[measurement["unit"].casefold()]
        result.append(_Assertion(context, dimension, Decimal(measurement["value"]) * scale))
    return tuple(result)


def classify_quantitative_relations(excerpts: list[str]) -> list[str]:
    """A new excerpt contradicts only a different value for a known same-context fact."""
    known: dict[tuple[_Context, str], set[Decimal]] = {}
    relations: list[str] = []
    for excerpt in excerpts:
        assertions = _assertions(excerpt)
        conflicts = any(
            any(value != assertion.value for value in known.get((assertion.context, assertion.dimension), set()))
            for assertion in assertions
        )
        relations.append("contradicts" if conflicts else "supports")
        for assertion in assertions:
            known.setdefault((assertion.context, assertion.dimension), set()).add(assertion.value)
    return relations
