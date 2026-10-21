from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from typing import Literal

from app.modules.agent_policy.config import RetrievalPolicyConfig
from app.modules.agent_policy.contracts import (
    PolicySimulation,
    PolicySimulationDecision,
    RequirementKind,
)
from app.modules.agent_policy.decision import RetrievalDecisionPolicy


_BOUNDARY = (
    "Counterfactual policy projection over persisted decisions only; "
    "no model, retrieval, evidence query, tool, provider, or write was executed."
)


@dataclass(frozen=True, slots=True)
class RecordedPolicyDecision:
    sequence: int
    tool: Literal["search_evidence", "read_neighbors"]
    requirement_kind: RequirementKind | None = None
    top_k: int | None = None
    before: int | None = None
    after: int | None = None

    def __post_init__(self) -> None:
        if type(self.sequence) is not int or self.sequence <= 0:
            raise ValueError("Recorded policy sequence must be a positive integer.")
        if self.tool == "search_evidence":
            if self.requirement_kind not in {"factual", "comparative", "temporal"}:
                raise ValueError("Recorded search decisions require a known requirement kind.")
            if type(self.top_k) is not int or self.top_k <= 0:
                raise ValueError("Recorded search decisions require a positive top_k.")
            if self.before is not None or self.after is not None:
                raise ValueError("Recorded search decisions cannot include neighbor fields.")
        elif self.tool == "read_neighbors":
            if (
                type(self.before) is not int
                or type(self.after) is not int
                or self.before < 0
                or self.after < 0
            ):
                raise ValueError("Recorded neighbor decisions require non-negative windows.")
            if self.requirement_kind is not None or self.top_k is not None:
                raise ValueError("Recorded neighbor decisions cannot include search fields.")
        else:
            raise ValueError(f"Unsupported recorded policy tool: {self.tool}")


def simulate_policy_decisions(
    *,
    run_id: str,
    policy_id: str,
    policy_version: int,
    config: RetrievalPolicyConfig,
    recorded: tuple[RecordedPolicyDecision, ...],
) -> PolicySimulation:
    ordered = tuple(sorted(recorded, key=lambda item: item.sequence))
    if len({item.sequence for item in ordered}) != len(ordered):
        raise ValueError("Recorded policy decision sequences must be unique.")
    policy = RetrievalDecisionPolicy(
        config,
        policy_id=policy_id,
        policy_version=policy_version,
    )
    decisions: list[PolicySimulationDecision] = []
    candidate_window_delta = 0
    neighbor_context_delta = 0
    for item in ordered:
        if item.tool == "search_evidence":
            candidate = policy.search_decision(item.requirement_kind)  # type: ignore[arg-type]
            changed = item.top_k != candidate.top_k
            candidate_window_delta += candidate.top_k - int(item.top_k or 0)
            decisions.append(
                PolicySimulationDecision(
                    sequence=item.sequence,
                    tool=item.tool,
                    changed=changed,
                    recorded_top_k=item.top_k,
                    candidate_top_k=candidate.top_k,
                )
            )
        else:
            candidate = policy.neighbor_decision()
            changed = item.before != candidate.before or item.after != candidate.after
            neighbor_context_delta += (
                candidate.before + candidate.after - int(item.before or 0) - int(item.after or 0)
            )
            decisions.append(
                PolicySimulationDecision(
                    sequence=item.sequence,
                    tool=item.tool,
                    changed=changed,
                    recorded_before=item.before,
                    candidate_before=candidate.before,
                    recorded_after=item.after,
                    candidate_after=candidate.after,
                )
            )
    digest_payload = {
        "run_id": run_id,
        "policy_id": policy_id,
        "policy_version": policy_version,
        "decisions": [asdict(item) for item in decisions],
    }
    digest = sha256(
        json.dumps(digest_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return PolicySimulation(
        run_id=run_id,
        policy_id=policy_id,
        policy_version=policy_version,
        changed_decision_count=sum(item.changed for item in decisions),
        projected_candidate_window_delta=candidate_window_delta,
        projected_neighbor_context_delta=neighbor_context_delta,
        digest=digest,
        boundary=_BOUNDARY,
        decisions=tuple(decisions),
    )
