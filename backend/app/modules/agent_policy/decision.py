from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import math

from app.modules.agent_policy.config import RetrievalPolicyConfig
from app.modules.agent_policy.contracts import (
    NeighborPolicyDecision,
    RequirementKind,
    SearchPolicyDecision,
)


@dataclass(frozen=True, slots=True)
class PolicyHit:
    identity: str
    source_id: int
    score: float


class RetrievalDecisionPolicy:
    def __init__(self, config: RetrievalPolicyConfig, *, policy_id: str, policy_version: int) -> None:
        if not policy_id.strip() or policy_version <= 0:
            raise ValueError("Policy identity and version must be positive and non-empty.")
        self.config = config
        self.policy_id = policy_id
        self.policy_version = policy_version

    def search_decision(self, requirement_kind: RequirementKind) -> SearchPolicyDecision:
        top_k_by_kind = {
            "factual": self.config.factual_top_k,
            "comparative": self.config.comparative_top_k,
            "temporal": self.config.temporal_top_k,
        }
        try:
            top_k = top_k_by_kind[requirement_kind]
        except KeyError as exc:
            raise ValueError(f"Unsupported requirement kind: {requirement_kind}") from exc
        return SearchPolicyDecision(
            policy_id=self.policy_id,
            policy_version=self.policy_version,
            requirement_kind=requirement_kind,
            top_k=top_k,
            minimum_score_millis=self.config.minimum_score_millis,
            max_hits_per_source=self.config.max_hits_per_source,
        )

    def neighbor_decision(self) -> NeighborPolicyDecision:
        return NeighborPolicyDecision(
            policy_id=self.policy_id,
            policy_version=self.policy_version,
            before=self.config.neighbor_before,
            after=self.config.neighbor_after,
        )

    def filter_hits(self, hits: tuple[PolicyHit, ...]) -> tuple[PolicyHit, ...]:
        return filter_policy_hits(
            hits,
            minimum_score_millis=self.config.minimum_score_millis,
            max_hits_per_source=self.config.max_hits_per_source,
        )


def filter_policy_hits(
    hits: tuple[PolicyHit, ...],
    *,
    minimum_score_millis: int,
    max_hits_per_source: int,
) -> tuple[PolicyHit, ...]:
    threshold = minimum_score_millis / 1_000
    source_counts: Counter[int] = Counter()
    accepted: list[PolicyHit] = []
    seen: set[str] = set()
    for hit in hits:
        if hit.identity in seen or not math.isfinite(hit.score) or hit.score < threshold:
            continue
        if source_counts[hit.source_id] >= max_hits_per_source:
            continue
        seen.add(hit.identity)
        source_counts[hit.source_id] += 1
        accepted.append(hit)
    return tuple(accepted)
