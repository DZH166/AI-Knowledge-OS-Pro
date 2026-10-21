from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, status
from fastapi.responses import StreamingResponse

from app.modules.evidence_agent.contracts import (
    BudgetLimits,
    DeliverableSpec,
    GetRun,
    ListRuns,
    OpenRun,
    PermissionPolicy,
    RunMode,
    RunStatus,
    ScopeSelector,
    SignalKind,
    SignalRun,
)
from app.modules.evidence_agent.interface import EvidenceAgent
from app.modules.evidence_agent.wiring import ensure_agent_provider_available, get_evidence_agent
from app.schemas.agent_schema import OpenRunSchema, RunCatalogSchema, RunViewSchema, SignalRunSchema, SubmissionSchema


router = APIRouter(prefix="/v1/evidence-runs", tags=["evidence-agent"])
AgentDependency = Annotated[EvidenceAgent, Depends(get_evidence_agent)]


@router.post("", response_model=SubmissionSchema, status_code=status.HTTP_201_CREATED)
def open_run(payload: OpenRunSchema, agent: AgentDependency) -> SubmissionSchema:
    ensure_agent_provider_available(payload.provider_mode)
    receipt = agent.submit(
        OpenRun(
            request_id=payload.request_id,
            space_id=payload.space_id,
            goal=payload.goal,
            scope=ScopeSelector(source_ids=tuple(payload.scope.source_ids)),
            deliverable=DeliverableSpec(**payload.deliverable.model_dump()),
            mode=RunMode(payload.mode),
            budget=BudgetLimits(**payload.budget.model_dump()),
            permissions=PermissionPolicy(**payload.permissions.model_dump()),
            provider_mode=payload.provider_mode,
        )
    )
    return _submission(receipt)


@router.get("", response_model=RunCatalogSchema)
def list_runs(
    agent: AgentDependency,
    space_id: Annotated[int | None, Query(gt=0)] = None,
    run_status: Annotated[RunStatus | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> RunCatalogSchema:
    catalog = agent.inspect(ListRuns(space_id=space_id, status=run_status, limit=limit))
    return RunCatalogSchema(items=[_view(item) for item in catalog.items])


@router.get("/{run_id}", response_model=RunViewSchema)
def inspect_run(run_id: str, agent: AgentDependency) -> RunViewSchema:
    return _view(agent.inspect(GetRun(run_id)))


@router.post("/{run_id}/commands", response_model=SubmissionSchema)
def signal_run(run_id: str, payload: SignalRunSchema, agent: AgentDependency) -> SubmissionSchema:
    receipt = agent.submit(
        SignalRun(
            request_id=payload.request_id,
            run_id=run_id,
            expected_version=payload.expected_version,
            signal=SignalKind(payload.signal),
            response=payload.response,
            proposal_digest=payload.proposal_digest,
        )
    )
    return _submission(receipt)


@router.get("/{run_id}/stream")
def follow_run(
    run_id: str,
    agent: AgentDependency,
    after: Annotated[int | None, Query(ge=0)] = None,
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
) -> StreamingResponse:
    cursor = _cursor(last_event_id, after)

    async def stream():
        async for frame in agent.follow(run_id, cursor=cursor):
            data = json.dumps(
                {
                    "schema_version": frame.schema_version,
                    "cursor": frame.cursor,
                    "run_version": frame.run_version,
                    "type": frame.event_type,
                    "payload": dict(frame.payload),
                },
                ensure_ascii=False,
                separators=(",", ":"),
            )
            yield f"id: {frame.cursor}\nevent: {frame.event_type}\ndata: {data}\n\n"

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


def _cursor(last_event_id: str | None, after: int | None) -> int | None:
    if last_event_id is None:
        return after
    try:
        value = int(last_event_id)
    except ValueError:
        return after
    return value if value >= 0 else after


def _submission(receipt) -> SubmissionSchema:
    return SubmissionSchema(
        command_id=receipt.command_id,
        run_id=receipt.run_id,
        run_version=receipt.run_version,
        status=receipt.status.value,
        cursor=receipt.cursor,
        replayed=receipt.replayed,
    )


def _view(view) -> RunViewSchema:
    outcome = None
    if view.status is RunStatus.INSUFFICIENT_EVIDENCE:
        outcome = {
            "kind": "insufficient_evidence",
            "reason": view.termination_reason or "evidence_gap",
            "gaps": [],
        }
    elif view.final_artifact_id:
        outcome = {"kind": "artifact", "artifact_id": view.final_artifact_id}
    return RunViewSchema.model_validate(
        {
            "schema_version": 1,
            "id": view.id,
            "space_id": view.space_id,
            "goal": view.goal,
            "requested_mode": view.requested_mode.value,
            "effective_mode": view.effective_mode.value if view.effective_mode else None,
            "status": view.status.value,
            "phase": view.phase.value,
            "version": view.version,
            "execution_epoch": view.execution_epoch,
            "scope_snapshot": {
                "space_id": view.scope_snapshot.space_id,
                "revisions": [
                    {
                        "source_id": item.source_id,
                        "revision_id": item.revision_id,
                        "index_revision_id": item.index_revision_id,
                        "content_hash": item.content_hash,
                    }
                    for item in view.scope_snapshot.revisions
                ],
            },
            "budget_limits": dict(view.budget_limits),
            "budget_usage": dict(view.budget_usage),
            "provider_mode": view.provider_mode,
            "last_event_cursor": view.last_event_cursor,
            "decision_policy": (
                {
                    "id": view.decision_policy.id,
                    "version": view.decision_policy.version,
                    "config_sha256": view.decision_policy.config_sha256,
                }
                if view.decision_policy
                else None
            ),
            "final_artifact_id": view.final_artifact_id,
            "termination_reason": view.termination_reason,
            "cost_measurement": view.cost_measurement,
            "outcome": outcome,
        }
    )
