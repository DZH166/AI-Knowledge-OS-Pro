from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


ConfidenceBand = Literal["low", "medium", "high"]
ResolutionStatus = Literal["not_applicable", "unresolved"]


@dataclass(frozen=True, slots=True)
class ClaimDecision:
    resolution_status: ResolutionStatus
    confidence_millis: int
    confidence_band: ConfidenceBand
    calibration_method: str
    calibration_reason: str

    def public_payload(self) -> dict[str, object]:
        return {
            "resolution_status": self.resolution_status,
            "confidence_millis": self.confidence_millis,
            "confidence_band": self.confidence_band,
            "calibration_method": self.calibration_method,
            "calibration_reason": self.calibration_reason,
        }


class ConservativeEvidenceDecisionPolicy:
    """Resolve conflicts by abstaining and calibrate confidence with hard caps."""

    _CONFLICT_CAP = 250
    _SINGLE_SOURCE_CAP = 700
    _CORROBORATED_CAP = 850

    def decide_claim(
        self,
        *,
        relations: tuple[str, ...],
        supporting_confidences: tuple[int, ...],
        supporting_source_ids: tuple[int, ...],
    ) -> ClaimDecision:
        if "contradicts" in relations:
            return ClaimDecision(
                resolution_status="unresolved",
                confidence_millis=self._CONFLICT_CAP,
                confidence_band="low",
                calibration_method="conflict_abstention_v1",
                calibration_reason="conflicting_evidence_unresolved",
            )

        raw_confidence = min(supporting_confidences, default=0)
        if len(set(supporting_source_ids)) >= 2:
            confidence = min(raw_confidence, self._CORROBORATED_CAP)
            method = "corroborated_support_cap_v1"
            reason = "independent_support_capped"
        else:
            confidence = min(raw_confidence, self._SINGLE_SOURCE_CAP)
            method = "single_source_cap_v1"
            reason = "single_source_support_capped"
        return ClaimDecision(
            resolution_status="not_applicable",
            confidence_millis=confidence,
            confidence_band=self._band(confidence),
            calibration_method=method,
            calibration_reason=reason,
        )

    @staticmethod
    def _band(confidence_millis: int) -> ConfidenceBand:
        if confidence_millis < 400:
            return "low"
        if confidence_millis < 750:
            return "medium"
        return "high"
