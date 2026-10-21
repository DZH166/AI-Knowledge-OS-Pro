from __future__ import annotations

from dataclasses import asdict
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Path, Query, status

from app.modules.agent_control.contracts import (
    CompareEvaluations,
    EvaluationCatalog,
    EvaluationComparison,
    EvaluationDetail,
    EvaluationStatus,
    GetEvaluation,
    GetRunTrace,
    ListEvaluations,
    RunTrace,
    StartEvaluation,
)
from app.modules.agent_control.interface import AgentControl
from app.modules.agent_control.wiring import get_agent_control
from app.schemas.agent_control_schema import (
    EvaluationCatalogSchema,
    EvaluationComparisonSchema,
    EvaluationDetailSchema,
    EvaluationReceiptSchema,
    RunTraceSchema,
    StartEvaluationSchema,
)


router = APIRouter(prefix="/v1", tags=["agent-control"])
AgentControlDependency = Annotated[AgentControl, Depends(get_agent_control)]


@router.post(
    "/agent-evaluations",
    response_model=EvaluationReceiptSchema,
    status_code=status.HTTP_201_CREATED,
)
def start_evaluation(
    payload: StartEvaluationSchema,
    control: AgentControlDependency,
) -> EvaluationReceiptSchema:
    receipt = control.submit(
        StartEvaluation(
            request_id=payload.request_id,
            label=payload.label,
            policy_id=payload.policy_id,
        )
    )
    return EvaluationReceiptSchema(
        evaluation_id=receipt.evaluation_id,
        status=receipt.status.value,
        replayed=receipt.replayed,
    )


@router.get("/agent-evaluations", response_model=EvaluationCatalogSchema)
def list_evaluations(
    control: AgentControlDependency,
    evaluation_status: Annotated[EvaluationStatus | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> EvaluationCatalogSchema:
    catalog = cast(
        EvaluationCatalog,
        control.inspect(ListEvaluations(status=evaluation_status, limit=limit)),
    )
    return EvaluationCatalogSchema(items=[asdict(item) for item in catalog.items])


@router.get("/agent-evaluations/compare", response_model=EvaluationComparisonSchema)
def compare_evaluation_snapshots(
    control: AgentControlDependency,
    left_id: Annotated[str, Query(min_length=1, max_length=36, pattern=r"^[A-Za-z0-9_-]+$")],
    right_id: Annotated[str, Query(min_length=1, max_length=36, pattern=r"^[A-Za-z0-9_-]+$")],
) -> EvaluationComparisonSchema:
    comparison = cast(
        EvaluationComparison,
        control.inspect(CompareEvaluations(left_id=left_id, right_id=right_id)),
    )
    return EvaluationComparisonSchema(**asdict(comparison))


@router.get("/agent-evaluations/{evaluation_id}", response_model=EvaluationDetailSchema)
def inspect_evaluation(
    evaluation_id: Annotated[str, Path(min_length=1, max_length=36, pattern=r"^[A-Za-z0-9_-]+$")],
    control: AgentControlDependency,
) -> EvaluationDetailSchema:
    detail = cast(EvaluationDetail, control.inspect(GetEvaluation(evaluation_id)))
    payload = asdict(detail)
    payload["report_schema_version"] = payload.pop("schema_version")
    return EvaluationDetailSchema(**payload)


@router.get("/evidence-runs/{run_id}/trace", response_model=RunTraceSchema)
def inspect_run_trace(
    run_id: Annotated[str, Path(min_length=1, max_length=36, pattern=r"^[A-Za-z0-9_-]+$")],
    control: AgentControlDependency,
) -> RunTraceSchema:
    trace = cast(RunTrace, control.inspect(GetRunTrace(run_id)))
    return RunTraceSchema(**asdict(trace))
