from __future__ import annotations

from dataclasses import replace
import math

import pytest

from app.modules.agent_policy.comparison import compare_policy_configs
from app.modules.agent_policy.config import (
    RetrievalPolicyConfig,
    canonical_policy_json,
    policy_fingerprint,
)
from app.modules.agent_policy.decision import PolicyHit, RetrievalDecisionPolicy
from app.modules.agent_policy.simulation import RecordedPolicyDecision, simulate_policy_decisions


DEFAULT_FINGERPRINT = "1f6f3b9ca28a2619d1efa22d6a79250306764719403d7092792aad45e130a7a3"


def test_default_policy_has_portable_canonical_identity() -> None:
    config = RetrievalPolicyConfig()

    assert canonical_policy_json(config) == (
        '{"comparative_top_k":14,"factual_top_k":8,"max_hits_per_source":3,'
        '"minimum_score_millis":0,"neighbor_after":1,"neighbor_before":1,'
        '"schema_version":1,"temporal_top_k":12}'
    )
    assert policy_fingerprint(config) == DEFAULT_FINGERPRINT


@pytest.mark.parametrize(
    "changes",
    [
        {"schema_version": 2},
        {"factual_top_k": True},
        {"factual_top_k": 0},
        {"comparative_top_k": 51},
        {"temporal_top_k": 2.5},
        {"minimum_score_millis": -1},
        {"minimum_score_millis": 1_001},
        {"max_hits_per_source": 0},
        {"neighbor_before": -1},
        {"neighbor_after": 4},
    ],
)
def test_policy_config_rejects_non_integer_unknown_version_and_out_of_range_values(
    changes: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        RetrievalPolicyConfig(**{**RetrievalPolicyConfig().as_dict(), **changes})


def test_adaptive_decision_uses_requirement_kind_score_and_source_diversity() -> None:
    config = replace(
        RetrievalPolicyConfig(),
        minimum_score_millis=500,
        max_hits_per_source=2,
        neighbor_before=2,
        neighbor_after=1,
    )
    policy = RetrievalDecisionPolicy(config, policy_id="policy-2", policy_version=2)
    hits = (
        PolicyHit(identity="s1-a", source_id=1, score=0.90),
        PolicyHit(identity="s1-b", source_id=1, score=0.80),
        PolicyHit(identity="s1-c", source_id=1, score=0.70),
        PolicyHit(identity="s2-a", source_id=2, score=0.85),
        PolicyHit(identity="s3-low", source_id=3, score=0.49),
        PolicyHit(identity="s4-nan", source_id=4, score=math.nan),
    )

    assert policy.search_decision("factual").top_k == 8
    assert policy.search_decision("comparative").top_k == 14
    assert policy.search_decision("temporal").top_k == 12
    assert policy.neighbor_decision().before == 2
    assert policy.neighbor_decision().after == 1
    assert [item.identity for item in policy.filter_hits(hits)] == ["s1-a", "s1-b", "s2-a"]
    assert policy.search_decision("factual").audit_payload() == {
        "policy_id": "policy-2",
        "policy_version": 2,
        "reason_code": "requirement_kind:factual",
        "top_k": 8,
        "minimum_score_millis": 500,
        "max_hits_per_source": 2,
    }


def test_policy_comparison_returns_only_changed_known_fields() -> None:
    left = RetrievalPolicyConfig()
    right = replace(left, factual_top_k=12, neighbor_before=2)

    comparison = compare_policy_configs(left, right)

    assert comparison.compatible is True
    assert [(item.field, item.left, item.right) for item in comparison.changes] == [
        ("factual_top_k", 8, 12),
        ("neighbor_before", 1, 2),
    ]


def test_counterfactual_simulation_is_stable_bounded_and_explicitly_non_executing() -> None:
    candidate = replace(RetrievalPolicyConfig(), neighbor_before=2)
    recorded = (
        RecordedPolicyDecision(sequence=1, tool="search_evidence", requirement_kind="factual", top_k=10),
        RecordedPolicyDecision(sequence=2, tool="search_evidence", requirement_kind="comparative", top_k=10),
        RecordedPolicyDecision(sequence=3, tool="read_neighbors", before=1, after=1),
    )

    first = simulate_policy_decisions(
        run_id="run-1",
        policy_id="candidate-1",
        policy_version=2,
        config=candidate,
        recorded=recorded,
    )
    second = simulate_policy_decisions(
        run_id="run-1",
        policy_id="candidate-1",
        policy_version=2,
        config=candidate,
        recorded=tuple(reversed(recorded)),
    )

    assert first == second
    assert first.changed_decision_count == 3
    assert first.projected_candidate_window_delta == 2
    assert first.projected_neighbor_context_delta == 1
    assert len(first.digest) == 64
    assert first.boundary == (
        "Counterfactual policy projection over persisted decisions only; "
        "no model, retrieval, evidence query, tool, provider, or write was executed."
    )
    assert [item.sequence for item in first.decisions] == [1, 2, 3]
