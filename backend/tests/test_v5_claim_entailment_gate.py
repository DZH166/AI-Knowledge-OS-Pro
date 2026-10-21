from __future__ import annotations

import pytest

from app.modules.evidence_agent.claim_verifier import (
    ClaimVerificationRequest,
    DeterministicClaimVerifier,
)


@pytest.mark.parametrize(
    ("evidence", "claim"),
    [
        ("系统支持离线缓存。", "系统不支持离线缓存。"),
        ("The system supports offline caching.", "The system does not support offline caching."),
        ("吞吐量提高了 20%。", "吞吐量降低了 20%。"),
        ("The feature is enabled.", "The feature is disabled."),
        ("延迟不高于 50 毫秒。", "延迟至少为 80 毫秒。"),
        ("The supported range is between 10 and 20 ms.", "The latency is at least 30 ms."),
    ],
)
def test_deterministic_claim_verifier_rejects_polarity_predicate_and_range_conflicts(
    evidence: str,
    claim: str,
) -> None:
    result = DeterministicClaimVerifier().verify(
        ClaimVerificationRequest(claim=claim, evidence=(evidence,))
    )

    assert result.entailed is False
    assert result.confidence_millis == 0
    assert result.reason_code in {
        "polarity_conflict",
        "predicate_conflict",
        "quantity_conflict",
        "unproven_entailment",
    }


@pytest.mark.parametrize(
    ("evidence", "claim"),
    [
        ("Alpha 的延迟为 42 毫秒。", "Alpha 延时是 42ms。"),
        ("Alpha latency is 42 milliseconds.", "Alpha delay equals 42 ms."),
        ("延迟为 42 毫秒。", "延迟不高于 50 毫秒。"),
        ("The latency is 42 ms.", "The delay is below 50 milliseconds."),
        ("系统未启用远程上传。", "系统没有开启远程上传。"),
    ],
)
def test_deterministic_claim_verifier_proves_bounded_synonyms_and_ranges(
    evidence: str,
    claim: str,
) -> None:
    result = DeterministicClaimVerifier().verify(
        ClaimVerificationRequest(claim=claim, evidence=(evidence,))
    )

    assert result.entailed is True
    assert 1 <= result.confidence_millis <= 1000
    assert result.method == "deterministic_entailment_v1"


def test_deterministic_claim_verifier_fails_closed_for_an_unmodelled_paraphrase() -> None:
    result = DeterministicClaimVerifier().verify(
        ClaimVerificationRequest(
            claim="The architecture is operationally elegant.",
            evidence=("The service uses a durable SQL checkpoint.",),
        )
    )

    assert result.entailed is False
    assert result.confidence_millis == 0
    assert result.reason_code == "unproven_entailment"
