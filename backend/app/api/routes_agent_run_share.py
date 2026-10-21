from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Path, status

from app.core.errors import ServiceError
from dataclasses import asdict

from app.modules.agent_control.contracts import GetRunTrace, RunTrace
from app.modules.agent_control.service import SqlAgentControl
from app.modules.agent_policy_optimizer.interface import AgentPolicyOptimizer
from app.modules.agent_policy_optimizer.wiring import get_agent_policy_optimizer
from app.schemas.agent_control_schema import RunTraceSchema
from app.schemas.optimizer_schema import (
    CreateShareLinkSchema,
    ShareLinkReceiptSchema,
)


router = APIRouter(prefix="/v1/agent-runs", tags=["agent-run-share"])
ShareOptimizerDependency = Annotated[AgentPolicyOptimizer, Depends(get_agent_policy_optimizer)]


@router.post("/{run_id}/share", response_model=ShareLinkReceiptSchema, status_code=status.HTTP_201_CREATED)
def create_share_link(
    run_id: Annotated[str, Path(min_length=1, max_length=36, pattern=r"^[A-Za-z0-9_-]+$")],
    optimizer: ShareOptimizerDependency,
    payload: CreateShareLinkSchema | None = None,
) -> ShareLinkReceiptSchema:
    expires_in_days = payload.expires_in_days if payload is not None else 7
    receipt = optimizer.create_share_link(
        run_id=run_id,
        expires_in_days=expires_in_days if expires_in_days is not None else 7,
    )
    return ShareLinkReceiptSchema(**receipt)


@router.get("/shared/{token}", response_model=RunTraceSchema)
def read_shared_trace(
    token: Annotated[str, Path(min_length=64, max_length=64, pattern=r"^[a-fA-F0-9]{64}$")],
    optimizer: ShareOptimizerDependency,
) -> RunTraceSchema:
    link = optimizer.resolve_share_link(token=token, now=datetime.now(UTC))
    control = SqlAgentControl(optimizer._sessions)  # noqa: SLF001 - same session family
    trace = cast(RunTrace, control.inspect(GetRunTrace(run_id=link["run_id"])))
    return RunTraceSchema(**asdict(trace))


@router.delete("/shared/{token}", status_code=status.HTTP_200_OK)
def revoke_share_link(
    token: Annotated[str, Path(min_length=64, max_length=64, pattern=r"^[a-fA-F0-9]{64}$")],
    optimizer: ShareOptimizerDependency,
) -> dict[str, object]:
    revoked = optimizer.revoke_share_link(token=token)
    if not revoked:
        raise ServiceError(
            code="SHARE_LINK_NOT_FOUND",
            message="Share link is invalid, expired, or revoked.",
            status_code=404,
        )
    return {"success": True, "revoked": True}
