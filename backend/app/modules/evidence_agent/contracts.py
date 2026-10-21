from __future__ import annotations

from dataclasses import dataclass, field, fields
from enum import StrEnum
from types import MappingProxyType
from typing import Literal, Mapping


class RunStatus(StrEnum):
    QUEUED = "queued"
    ROUTING = "routing"
    PLANNED = "planned"
    RUNNING = "running"
    AWAITING_INPUT = "awaiting_input"
    AWAITING_APPROVAL = "awaiting_approval"
    PAUSED = "paused"
    COMPLETED = "completed"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    CANCELLED = "cancelled"
    FAILED = "failed"


class RunPhase(StrEnum):
    ROUTE = "route"
    PLAN = "plan"
    RETRIEVE = "retrieve"
    ASSESS = "assess"
    SYNTHESIZE = "synthesize"
    VERIFY = "verify"
    PERSIST_ARTIFACT = "persist_artifact"


class RunMode(StrEnum):
    AUTO = "auto"
    FORCE_QUICK = "force_quick"
    FORCE_AGENT = "force_agent"


class SignalKind(StrEnum):
    PROVIDE_INPUT = "provide_input"
    APPROVE = "approve"
    REJECT = "reject"
    MODIFY = "modify"
    PAUSE = "pause"
    RESUME = "resume"
    CANCEL = "cancel"


@dataclass(frozen=True, slots=True)
class BudgetLimits:
    max_steps: int = 8
    max_tool_calls: int = 12
    max_model_calls: int = 6
    max_model_input_tokens: int = 24_000
    max_model_output_tokens: int = 6_000
    max_cost_micros: int = 1_000_000
    max_active_ms: int = 180_000
    max_no_new_evidence_rounds: int = 2
    max_query_rewrites: int = 3
    max_evidence_records: int = 40
    max_context_tokens: int = 16_000

    def __post_init__(self) -> None:
        if any(getattr(self, item.name) <= 0 for item in fields(self)):
            raise ValueError("Every budget limit must be positive.")


@dataclass(frozen=True, slots=True)
class PermissionPolicy:
    read_only: bool = True
    allow_scope_expansion: bool = False


@dataclass(frozen=True, slots=True)
class ScopeSelector:
    source_ids: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class DeliverableSpec:
    kind: str = "answer"
    title: str | None = None


@dataclass(frozen=True, slots=True)
class OpenRun:
    request_id: str
    space_id: int
    goal: str
    scope: ScopeSelector
    deliverable: DeliverableSpec
    mode: RunMode
    budget: BudgetLimits
    permissions: PermissionPolicy
    provider_mode: str = "real"


@dataclass(frozen=True, slots=True)
class ContinueRun:
    request_id: str
    source_run_id: str
    gap_artifact_id: str
    gap_ordinals: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        if (
            not self.request_id.strip()
            or not self.source_run_id.strip()
            or not self.gap_artifact_id.strip()
        ):
            raise ValueError("Continuation identifiers cannot be blank.")
        if any(
            isinstance(ordinal, bool) or ordinal <= 0
            for ordinal in self.gap_ordinals
        ):
            raise ValueError("Continuation gap ordinals must be positive integers.")
        if len(set(self.gap_ordinals)) != len(self.gap_ordinals):
            raise ValueError("Continuation gap ordinals must be unique.")


@dataclass(frozen=True, slots=True)
class SignalRun:
    request_id: str
    run_id: str
    expected_version: int
    signal: SignalKind
    response: Mapping[str, object] = field(default_factory=dict)
    proposal_digest: str | None = None


@dataclass(frozen=True, slots=True)
class Submission:
    command_id: str
    run_id: str
    run_version: int
    status: RunStatus
    cursor: int
    replayed: bool = False


@dataclass(frozen=True, slots=True)
class ScopedRevision:
    source_id: int
    revision_id: int
    index_revision_id: int
    content_hash: str


@dataclass(frozen=True, slots=True)
class ScopeSnapshot:
    space_id: int
    revisions: tuple[ScopedRevision, ...] = ()


@dataclass(frozen=True, slots=True)
class RunOrigin:
    kind: Literal["initial", "continuation"] = "initial"
    source_run_id: str | None = None
    gap_artifact_id: str | None = None
    gap_ordinals: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        continuation_fields = (self.source_run_id, self.gap_artifact_id)
        if self.kind == "initial" and (any(continuation_fields) or self.gap_ordinals):
            raise ValueError("Initial runs cannot carry continuation lineage.")
        if self.kind == "continuation" and not all(continuation_fields):
            raise ValueError("Continuation runs require source run and gap artifact lineage.")


@dataclass(frozen=True, slots=True)
class GetRun:
    run_id: str
    view: str = "workbench"


@dataclass(frozen=True, slots=True)
class GetArtifact:
    artifact_id: str


@dataclass(frozen=True, slots=True)
class GetEvidence:
    evidence_id: str


@dataclass(frozen=True, slots=True)
class ListRuns:
    space_id: int | None = None
    status: RunStatus | None = None
    limit: int = 50


@dataclass(frozen=True, slots=True)
class ListArtifacts:
    space_id: int | None = None
    source_id: int | None = None
    run_id: str | None = None
    limit: int = 50


@dataclass(frozen=True, slots=True)
class DecisionPolicyView:
    id: str
    version: int
    config_sha256: str


@dataclass(frozen=True, slots=True)
class RunView:
    id: str
    space_id: int
    goal: str
    requested_mode: RunMode
    effective_mode: RunMode | None
    status: RunStatus
    phase: RunPhase
    version: int
    execution_epoch: int
    scope_snapshot: ScopeSnapshot
    budget_limits: Mapping[str, int]
    budget_usage: Mapping[str, int]
    provider_mode: str
    last_event_cursor: int
    decision_policy: DecisionPolicyView | None = None
    origin: RunOrigin = field(default_factory=RunOrigin)
    final_artifact_id: str | None = None
    termination_reason: str | None = None
    cost_measurement: Literal["reported", "estimated", "unknown", "partial_unknown"] = (
        "unknown"
    )


@dataclass(frozen=True, slots=True)
class RunFrame:
    cursor: int
    event_type: str
    run_version: int
    payload: Mapping[str, object]
    schema_version: int = 1


@dataclass(frozen=True, slots=True)
class ArtifactClaimView:
    id: str
    ordinal: int
    text: str
    kind: str
    verification_status: str
    evidence_ids: tuple[str, ...]
    resolution_status: Literal["not_applicable", "unresolved"] = "not_applicable"
    confidence_millis: int = 0
    confidence_band: Literal["low", "medium", "high"] = "low"
    calibration_method: str = "legacy_uncalibrated"
    calibration_reason: str = "legacy_claim"


@dataclass(frozen=True, slots=True)
class ArtifactView:
    id: str
    producing_run_id: str
    kind: str
    title: str
    body_markdown: str
    status: str
    schema_version: int
    claims: tuple[ArtifactClaimView, ...]


@dataclass(frozen=True, slots=True)
class EvidenceView:
    id: str
    run_id: str
    source_id: int
    revision_id: int
    index_revision_id: int
    chunk_id: int
    source_type: str
    locator: Mapping[str, object]
    revision_content_hash: str
    content_hash: str
    excerpt_preview: str
    claim_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RunCatalog:
    items: tuple[RunView, ...]


@dataclass(frozen=True, slots=True)
class ArtifactSummary:
    id: str
    producing_run_id: str
    kind: str
    title: str
    status: str


@dataclass(frozen=True, slots=True)
class ArtifactCatalog:
    items: tuple[ArtifactSummary, ...]


AgentQuery = GetRun | GetArtifact | GetEvidence | ListRuns | ListArtifacts
AgentQueryResult = RunView | ArtifactView | EvidenceView | RunCatalog | ArtifactCatalog


@dataclass(frozen=True, slots=True)
class EvidenceRef:
    """Revision-complete identity suitable for durable citations.

    Scores and support/contradiction assessments intentionally live outside this
    value object so that retrieval cannot mutate evidence identity.
    """

    source_id: int
    revision_id: int
    index_revision_id: int
    chunk_id: int
    content_hash: str
    locator: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if min(self.source_id, self.revision_id, self.index_revision_id, self.chunk_id) <= 0:
            raise ValueError("Evidence identity fields must be positive integers.")
        if len(self.content_hash) != 64:
            raise ValueError("Evidence content_hash must be a SHA-256 hex digest.")
        try:
            int(self.content_hash, 16)
        except ValueError as exc:
            raise ValueError("Evidence content_hash must be hexadecimal.") from exc
        object.__setattr__(self, "locator", MappingProxyType(dict(self.locator)))
