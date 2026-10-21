from __future__ import annotations

from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, Path, status

from app.modules.agent_run_share.contracts import CreateShareLink, GetSharedRunTrace, RevokeShareLink
from app.modules.agent_run_share.interface import AgentRunShare
from app.modules.agent_run_share.wiring import get_agent_run_share
from app.schemas.agent_control_schema import RunTraceSchema
from app.schemas.optimizer_schema import (
    CreateShareLinkSchema,
    ShareLinkReceiptSchema,
)


router = APIRouter(prefix="/v1/agent-runs", tags=["agent-run-share"])
RunShareDependency = Annotated[AgentRunShare, Depends(get_agent_run_share)]


@router.post("/{run_id}/share", response_model=ShareLinkReceiptSchema, status_code=status.HTTP_201_CREATED)
def create_share_link(
    run_id: Annotated[str, Path(min_length=1, max_length=36, pattern=r"^[A-Za-z0-9_-]+$")],
    share: RunShareDependency,
    payload: CreateShareLinkSchema | None = None,
) -> ShareLinkReceiptSchema:
    expires_in_days = payload.expires_in_days if payload is not None else 7
    receipt = share.submit(
        CreateShareLink(
            run_id=run_id,
            expires_in_days=expires_in_days if expires_in_days is not None else 7,
        )
    )
    return ShareLinkReceiptSchema(
        token=receipt.token,
        url_path=receipt.url_path,
        expires_at=receipt.expires_at.isoformat(),
    )


@router.get("/shared/{token}", response_model=RunTraceSchema)
def read_shared_trace(
    token: Annotated[str, Path(min_length=64, max_length=64, pattern=r"^[a-fA-F0-9]{64}$")],
    share: RunShareDependency,
) -> RunTraceSchema:
    trace = share.inspect(GetSharedRunTrace(token=token))
    return RunTraceSchema(**asdict(trace))


@router.delete("/shared/{token}", status_code=status.HTTP_200_OK)
def revoke_share_link(
    token: Annotated[str, Path(min_length=64, max_length=64, pattern=r"^[a-fA-F0-9]{64}$")],
    share: RunShareDependency,
) -> dict[str, object]:
    share.submit(RevokeShareLink(token=token))
    return {"success": True, "revoked": True}
