from __future__ import annotations

from typing import Protocol, overload

from app.modules.evidence_index.contracts import (
    EvidenceCommand,
    EvidenceCommandResult,
    EvidenceSearchResult,
    GetRevision,
    GetSourceState,
    RevisionView,
    SearchEvidence,
    SourceState,
)


class EvidenceIndex(Protocol):
    """Deep-module seam for evidence lifecycle commands and projections."""

    def command(self, command: EvidenceCommand) -> EvidenceCommandResult: ...

    @overload
    def query(self, query: GetRevision) -> RevisionView: ...

    @overload
    def query(self, query: GetSourceState) -> SourceState: ...

    def query(self, query: GetRevision | GetSourceState) -> RevisionView | SourceState: ...

    def search(self, request: SearchEvidence) -> EvidenceSearchResult: ...
