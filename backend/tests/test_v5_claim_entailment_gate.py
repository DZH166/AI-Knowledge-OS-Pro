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


def test_chinese_bounded_claim_cannot_change_the_subject() -> None:
    result = DeterministicClaimVerifier().verify(
        ClaimVerificationRequest(
            claim="乙方案延迟不高于 50 毫秒。",
            evidence=("甲方案延迟为 42 毫秒。",),
        )
    )

    assert result.entailed is False


@pytest.mark.parametrize(
    ("evidence", "claim"),
    [
        ("Alpha latency is 42 ms.", "latency is 42 ms."),
        ("beta 目标延迟是 18 毫秒。", "目标延迟为 18 毫秒。"),
    ],
)
def test_named_evidence_does_not_prove_an_unqualified_numeric_claim(
    evidence: str, claim: str
) -> None:
    result = DeterministicClaimVerifier().verify(
        ClaimVerificationRequest(claim=claim, evidence=(evidence,))
    )

    assert result.entailed is False


@pytest.mark.parametrize(
    ("evidence", "claim"),
    [
        ("系统目标延迟为 100 毫秒。", "系统延迟为 100 毫秒。"),
        ("系统延迟为 100 毫秒。", "系统目标延迟为 100 毫秒。"),
    ],
)
def test_target_latency_does_not_prove_observed_latency_or_vice_versa(
    evidence: str, claim: str
) -> None:
    result = DeterministicClaimVerifier().verify(
        ClaimVerificationRequest(claim=claim, evidence=(evidence,))
    )

    assert result.entailed is False


@pytest.mark.parametrize(
    ("evidence", "claim"),
    [
        ("接口延迟为 100 毫秒。", "接口延迟低于 100 毫秒。"),
        ("The latency is 100 ms.", "The delay is below 100 milliseconds."),
        ("接口延迟为 100 毫秒。", "接口延迟高于 100 毫秒。"),
    ],
)
def test_strict_comparison_does_not_accept_equality(evidence: str, claim: str) -> None:
    result = DeterministicClaimVerifier().verify(
        ClaimVerificationRequest(claim=claim, evidence=(evidence,))
    )

    assert result.entailed is False


@pytest.mark.parametrize(
    ("evidence", "claim"),
    [
        ("Alpha 延迟 42 毫秒，吞吐量 60 次每秒。", "Alpha 延迟为 60 毫秒。"),
        ("Alpha 延迟为 42 毫秒。", "Alpha 延迟为 42 名用户。"),
        ("旧版日志最多保留 60 天。", "系统支持至少 50 名用户。"),
        ("The latency is 42 ms; throughput is 60 requests per second.", "The latency is 60 ms."),
    ],
)
def test_number_must_belong_to_the_same_metric_and_unit(evidence: str, claim: str) -> None:
    result = DeterministicClaimVerifier().verify(
        ClaimVerificationRequest(claim=claim, evidence=(evidence,))
    )

    assert result.entailed is False


@pytest.mark.parametrize(
    ("evidence", "claim"),
    [
        ("甲方案支持离线缓存。", "乙方案支持离线缓存。"),
        ("系统支持离线缓存。", "系统支持远程上传。"),
        ("The system supports offline caching.", "The system supports remote upload."),
    ],
)
def test_shared_predicate_does_not_prove_a_different_subject_or_object(
    evidence: str, claim: str
) -> None:
    result = DeterministicClaimVerifier().verify(
        ClaimVerificationRequest(claim=claim, evidence=(evidence,))
    )

    assert result.entailed is False


@pytest.mark.parametrize(
    ("evidence", "claim"),
    [
        ("Alpha latency is 42 ms.", "Alpha latency is not 42 ms."),
        ("Alpha latency is not 42 ms.", "Alpha latency is 42 ms."),
        ("接口延迟不是 42 毫秒。", "接口延迟为 42 毫秒。"),
        ("接口延迟为 42 毫秒。", "接口延迟不是 42 毫秒。"),
    ],
)
def test_numeric_negation_never_proves_the_opposite(evidence: str, claim: str) -> None:
    result = DeterministicClaimVerifier().verify(
        ClaimVerificationRequest(claim=claim, evidence=(evidence,))
    )

    assert result.entailed is False


@pytest.mark.parametrize(
    ("evidence", "claim"),
    [
        ("旧版日志最多保留 60 天。", "旧版日志保留 60 天。"),
        ("The latency is at most 60 ms.", "The delay is 60 milliseconds."),
        ("Alpha latency is 42 ms.", "Alpha latency isn't 42 ms."),
        ("Alpha latency is 42 ms.", "Alpha latency is 42 ms and supports remote upload."),
        ("Alpha latency is 42 ms.", "Alpha latency is 42 ms and service supports remote upload."),
        ("Alpha latency is 42 ms.", "Alpha latency is 42 ms; remote upload is enabled."),
        ("Alpha latency is approximately 42 ms.", "Alpha latency is 42 ms."),
        ("Alpha latency might be 42 ms.", "Alpha latency is 42 ms."),
        ("Alpha latency is 42 ms before optimization.", "Alpha latency is 42 ms after optimization."),
        ("Alpha latency is 42 ms.", "Alpha latency on sunday is 42 ms."),
        ("Alpha latency in 2024 is 42 ms.", "Alpha latency is 42 ms."),
    ],
)
def test_numeric_claim_declines_unproven_qualifiers_and_extra_facts(
    evidence: str, claim: str
) -> None:
    result = DeterministicClaimVerifier().verify(
        ClaimVerificationRequest(claim=claim, evidence=(evidence,))
    )

    assert result.entailed is False


@pytest.mark.parametrize(
    ("evidence", "claim"),
    [
        ("Alpha 延迟为 42 毫秒，吞吐量为 60 次每秒。", "Alpha 延时是 42ms。"),
        ("Alpha latency is 42 milliseconds.", "Alpha delay is below 50 ms."),
        ("接口延迟为 42 毫秒。", "接口延迟不高于 42 毫秒。"),
        ("系统目标延迟为 100 毫秒。", "系统目标延时是 100ms。"),
        ("Beta 目标延迟在 2024 年是 18 毫秒。", "Beta 在 2024 年的目标延时为 18ms。"),
        ("系统未启用远程上传。", "系统没有开启远程上传。"),
    ],
)
def test_supported_finite_paraphrases_still_pass(evidence: str, claim: str) -> None:
    result = DeterministicClaimVerifier().verify(
        ClaimVerificationRequest(claim=claim, evidence=(evidence,))
    )

    assert result.entailed is True
