from __future__ import annotations

from dataclasses import dataclass
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


class DeterministicClaimVerifier:
    """Fail-closed verifier for literals, polarity, and bounded numbers."""

    _NEGATIVE = ("不", "未", "无", "没有", "禁止", "禁用", "disabled", "disable", "not", "never", "without")
    _POSITIVE = ("支持", "启用", "开启", "允许", "可用", "enabled", "enable", "supports", "supported", "available")
    _DIRECTION_PAIRS = (("提高", "降低"), ("增加", "减少"), ("提升", "下降"), ("increase", "decrease"), ("higher", "lower"))
    _STOP = {"the", "a", "an", "is", "are", "was", "were", "of", "to", "and", "or", "for", "with", "system", "系统", "为", "是", "的", "了"}

    def verify(self, request: ClaimVerificationRequest) -> ClaimVerificationResult:
        claim = self._clean(request.claim)
        evidence = "\n".join(self._clean(item) for item in request.evidence if self._clean(item))
        if not claim or not evidence:
            return self._fail("unproven_entailment")
        claim_numbers = self._numbers(claim)
        evidence_numbers = self._numbers(evidence)
        if claim_numbers and not claim_numbers.issubset(evidence_numbers):
            if not self._bounded_numeric_claim(claim, evidence_numbers):
                return self._fail("quantity_conflict")
        if self._bounded_numeric_claim(claim, evidence_numbers):
            return ClaimVerificationResult(True, 900, "bounded_numeric_entailment")
        if self._polarity(claim) != self._polarity(evidence) and self._polarity(claim) != "mixed":
            return self._fail("polarity_conflict")
        if self._direction_conflict(claim, evidence):
            return self._fail("predicate_conflict")
        claim_tokens = self._tokens(claim)
        evidence_tokens = self._tokens(evidence)
        proper_names = {
            item.casefold()
            for item in re.findall(r"(?<![A-Za-z0-9])[A-Z][A-Za-z0-9]*(?![A-Za-z0-9])", claim)
            if item.casefold() not in {"The", "A", "An"}
        }
        if any(name not in evidence.casefold() for name in proper_names):
            return self._fail("unproven_entailment")
        if not claim_tokens or not self._concept_overlap(claim, evidence, claim_tokens, evidence_tokens):
            return self._fail("unproven_entailment")
        if claim.casefold() in evidence.casefold() or evidence.casefold() in claim.casefold():
            return ClaimVerificationResult(True, 1000, "literal_entailment")
        return ClaimVerificationResult(True, 780, "synonym_entailment")

    @staticmethod
    def _clean(value: str) -> str:
        return " ".join(value.strip().split())

    @staticmethod
    def _numbers(value: str) -> set[str]:
        return {item.replace(",", "") for item in re.findall(r"\d+(?:[.,]\d+)?", value)}

    @classmethod
    def _tokens(cls, value: str) -> set[str]:
        tokens = set(re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]{2,}", value.casefold()))
        return {token for token in tokens if token not in cls._STOP}

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
    def _concept_overlap(cls, claim: str, evidence: str, claim_tokens: set[str], evidence_tokens: set[str]) -> bool:
        if claim_tokens & evidence_tokens:
            return True
        synonyms = (("延迟", "延时", "latency", "delay"), ("开启", "启用", "enabled", "enable"), ("支持", "允许", "supports", "support"), ("缓存", "caching", "cache"), ("上传", "upload"))
        return any(any(item in claim.casefold() for item in group) and any(item in evidence.casefold() for item in group) for group in synonyms)

    @staticmethod
    def _bounded_numeric_claim(claim: str, evidence_numbers: set[str]) -> bool:
        if not evidence_numbers:
            return False
        value = float(next(iter(evidence_numbers)))
        folded = claim.casefold()
        match = re.search(r"(?:不高于|不超过|低于|小于|below|under|less than)\s*(\d+(?:\.\d+)?)", folded)
        if match:
            return value <= float(match.group(1))
        match = re.search(r"(?:至少|不低于|不小于|高于|大于|at least|above|greater than)\s*(\d+(?:\.\d+)?)", folded)
        if match:
            return value >= float(match.group(1))
        return False

    @staticmethod
    def _fail(reason_code: str) -> ClaimVerificationResult:
        return ClaimVerificationResult(False, 0, reason_code)
