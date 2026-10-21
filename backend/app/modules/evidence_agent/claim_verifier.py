from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import re


@dataclass(frozen=True, slots=True)
class ClaimVerificationRequest:
    claim: str
    evidence: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ClaimVerificationResult:
    entailed: bool
    confidence_millis: int
    reason_code: str
    method: str = "deterministic_entailment_v1"


@dataclass(frozen=True, slots=True)
class _NumericFact:
    clause: str
    metric: str
    subject: str
    unit: str
    value: Decimal
    comparator: str
    context_numbers: frozenset[str]


class DeterministicClaimVerifier:
    """Fail-closed verifier for literals, polarity, and bounded numbers."""

    _NEGATIVE = ("不", "未", "无", "没有", "禁止", "禁用", "disabled", "disable", "not", "never", "without")
    _POSITIVE = ("支持", "启用", "开启", "允许", "可用", "enabled", "enable", "supports", "supported", "available")
    _DIRECTION_PAIRS = (("提高", "降低"), ("增加", "减少"), ("提升", "下降"), ("increase", "decrease"), ("higher", "lower"))
    _METRIC_PATTERN = re.compile(
        r"延迟|延时|latency|delay|吞吐量|throughput|成本|cost|保留|retention|支持|supports?",
        re.IGNORECASE,
    )
    _NUMBER_PATTERN = re.compile(r"(?<![A-Za-z0-9])\d+(?:\.\d+)?")
    _UNIT_PATTERN = re.compile(
        r"\s*(milliseconds?|msec|ms|毫秒|seconds?|秒|requests?\s+per\s+second|次每秒|名用户|用户|users?|人|人民币|yuan|元|days?|天|%)",
        re.IGNORECASE,
    )

    def verify(self, request: ClaimVerificationRequest) -> ClaimVerificationResult:
        claim = self._clean(request.claim)
        evidence = "\n".join(self._clean(item) for item in request.evidence if self._clean(item))
        if not claim or not evidence:
            return self._fail("unproven_entailment")
        proper_names = {
            item.casefold()
            for item in re.findall(r"(?<![A-Za-z0-9])[A-Z][A-Za-z0-9]*(?![A-Za-z0-9])", claim)
            if item.casefold() not in {"the", "a", "an"}
        }
        if any(name not in evidence.casefold() for name in proper_names):
            return self._fail("unproven_entailment")
        if self._numbers(claim):
            if any(claim.casefold() == item.casefold() for item in request.evidence):
                return ClaimVerificationResult(True, 1000, "literal_entailment")
            if re.search(r"\band\b|\bbut\b|且|并且|同时|而且", claim.casefold()):
                return self._fail("unproven_entailment")
            claim_facts = self._numeric_facts(claim)
            evidence_facts = self._numeric_facts(evidence)
            if not claim_facts or not evidence_facts:
                return self._fail("unproven_entailment")
            claim_clauses = tuple(
                clause.strip()
                for clause in re.split(r"[。；;\n]|(?<!\d)\.(?!\d)", claim)
                if clause.strip()
            )
            if any(not any(fact.clause == clause for fact in claim_facts) for clause in claim_clauses):
                return self._fail("unproven_entailment")
            if not all(
                any(self._fact_entails(source, target) for source in evidence_facts)
                for target in claim_facts
            ):
                return self._fail("quantity_conflict")
            bounded = any(item.comparator != "eq" for item in claim_facts)
            return ClaimVerificationResult(
                True, 900 if bounded else 780,
                "bounded_numeric_entailment" if bounded else "synonym_entailment",
            )
        if self._polarity(claim) != self._polarity(evidence) and self._polarity(claim) != "mixed":
            return self._fail("polarity_conflict")
        if self._direction_conflict(claim, evidence):
            return self._fail("predicate_conflict")
        canonical_claim = self._canonical_statement(claim)
        for clause in re.split(r"[。；;\n]|(?<!\d)\.(?!\d)", evidence):
            if canonical_claim and canonical_claim == self._canonical_statement(clause):
                literal = claim.casefold().strip(" .。") == clause.casefold().strip(" .。")
                return ClaimVerificationResult(
                    True,
                    1000 if literal else 780,
                    "literal_entailment" if literal else "synonym_entailment",
                )
        return self._fail("unproven_entailment")

    @staticmethod
    def _clean(value: str) -> str:
        return " ".join(value.strip().split())

    @staticmethod
    def _numbers(value: str) -> set[str]:
        return {item.replace(",", "") for item in re.findall(r"\d+(?:[.,]\d+)?", value)}

    @staticmethod
    def _canonical_statement(value: str) -> str:
        value = value.casefold()
        value = re.sub(r"(?:没有|未)(?=(?:启用|开启))", "不", value)
        value = value.replace("开启", "启用")
        value = re.sub(r"\b(?:enabled|enables|enable)\b", "enable", value)
        value = re.sub(r"\b(?:supports|supported)\b", "support", value)
        return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", value)

    @classmethod
    def _polarity(cls, value: str) -> str:
        folded = value.casefold()
        folded = re.sub(r"(?:不高于|不超过|不低于|不小于|at least|at most|below|under|less than|greater than)\s*\d+(?:\.\d+)?", "", folded)
        negative = any(term in folded for term in cls._NEGATIVE)
        positive = any(term in folded for term in cls._POSITIVE)
        if negative and positive:
            if any(f"不{term}" in folded for term in ("支持", "启用", "开启", "允许")) or "does not" in folded or "not" in folded:
                return "negative"
            return "mixed"
        return "negative" if negative else "positive"

    @classmethod
    def _direction_conflict(cls, claim: str, evidence: str) -> bool:
        return any((left in claim and right in evidence) or (right in claim and left in evidence) for left, right in cls._DIRECTION_PAIRS)

    @classmethod
    def _numeric_facts(cls, text: str) -> tuple[_NumericFact, ...]:
        facts: list[_NumericFact] = []
        for clause in re.split(r"[。；;，,\n]|(?<!\d)\.(?!\d)", text):
            clause = clause.strip()
            for number in cls._NUMBER_PATTERN.finditer(clause):
                preceding = tuple(cls._METRIC_PATTERN.finditer(clause[: number.start()]))
                if not preceding:
                    continue
                metric_match = preceding[-1]
                between = clause[metric_match.end() : number.start()].casefold()
                if len(between) > 36 or not cls._known_numeric_relation(between):
                    continue
                unit_match = cls._UNIT_PATTERN.match(clause[number.end() :])
                if unit_match is None:
                    continue
                if clause[number.end() + unit_match.end() :].strip():
                    continue
                metric = cls._metric(metric_match.group())
                unit = cls._unit(unit_match.group(1))
                if (metric, unit) not in {
                    ("latency", "ms"), ("latency", "s"),
                    ("throughput", "requests/s"), ("cost", "yuan"),
                    ("retention", "day"), ("users", "user"),
                }:
                    continue
                prefix = clause[: metric_match.start()].casefold().strip(" ，。:：")
                prefix = re.sub(r"^(?:the|a|an)\s+", "", prefix)
                prefix = re.sub(r"在\s*\d+\s*年\s*的?", "", prefix)
                prefix = re.sub(r"\s*事实\s*的?$", "", prefix)
                prefix = re.sub(r"\s*的$", "", prefix)
                prefix = re.sub(r"\s+", "", prefix)
                comparator = cls._comparator(between)
                context = cls._numbers(clause) - {number.group()}
                facts.append(
                    _NumericFact(
                        clause=clause,
                        metric=metric,
                        subject=prefix,
                        unit=unit,
                        value=Decimal(number.group()),
                        comparator=comparator,
                        context_numbers=frozenset(context),
                    )
                )
        return tuple(facts)

    @staticmethod
    def _metric(value: str) -> str:
        value = value.casefold()
        if value in {"延迟", "延时", "latency", "delay"}:
            return "latency"
        if value in {"吞吐量", "throughput"}:
            return "throughput"
        if value in {"成本", "cost"}:
            return "cost"
        if value in {"保留", "retention"}:
            return "retention"
        return "users"

    @staticmethod
    def _unit(value: str) -> str:
        value = value.casefold()
        if value in {"毫秒", "ms", "msec", "millisecond", "milliseconds"}:
            return "ms"
        if value in {"秒", "second", "seconds"}:
            return "s"
        if value in {"次每秒", "request per second", "requests per second"}:
            return "requests/s"
        if value in {"元", "人民币", "yuan"}:
            return "yuan"
        if value in {"天", "day", "days"}:
            return "day"
        if value in {"名用户", "用户", "user", "users", "人"}:
            return "user"
        return value

    @staticmethod
    def _comparator(between: str) -> str:
        if re.search(r"不是|不为|并非|\bnot\b|isn['’]t|wasn['’]t|≠", between):
            return "neq"
        if re.search(r"约|大约|预计|可能|approximately|about|roughly|might|may", between):
            return "approx"
        if re.search(r"不高于|不超过|at most|no more than", between):
            return "lte"
        if re.search(r"低于|小于|below|under|less than", between):
            return "lt"
        if re.search(r"至少|不低于|不小于|at least", between):
            return "gte"
        if re.search(r"高于|大于|above|greater than", between):
            return "gt"
        return "eq"

    @staticmethod
    def _known_numeric_relation(between: str) -> bool:
        return re.fullmatch(
            r"\s*(?:事实\s*)?(?:(?:在|in)\s*\d{4}\s*年?\s*)?"
            r"(?:为|是|=|\b(?:is|was|are|were|equals?)\b)?\s*"
            r"(?:不高于|不超过|低于|小于|至少|不低于|不小于|高于|大于|"
            r"at least|at most|no more than|above|greater than|below|under|less than)?\s*",
            between,
            re.IGNORECASE,
        ) is not None

    @staticmethod
    def _fact_entails(source: _NumericFact, target: _NumericFact) -> bool:
        if source.metric != target.metric or source.unit != target.unit:
            return False
        if source.subject != target.subject:
            return False
        # A narrower source (for example, "in 2024") cannot prove an
        # unqualified, all-period claim; neither side may silently drop scope.
        if target.context_numbers != source.context_numbers:
            return False
        if source.comparator != "eq" or target.comparator in {"neq", "approx"}:
            return False
        if target.comparator == "lt":
            return source.value < target.value
        if target.comparator == "lte":
            return source.value <= target.value
        if target.comparator == "gt":
            return source.value > target.value
        if target.comparator == "gte":
            return source.value >= target.value
        return source.value == target.value

    @staticmethod
    def _fail(reason_code: str) -> ClaimVerificationResult:
        return ClaimVerificationResult(False, 0, reason_code)
