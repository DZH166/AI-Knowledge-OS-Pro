from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Path, Query, status

from app.modules.agent_policy_optimizer.contracts import (
    CancelStudy,
    GetOptimizationPareto,
    GetOptimizationRecommendation,
    GetOptimizationStudy,
    GetOptimizationTrial,
    ListOptimizationStudies,
    ListOptimizationTrials,
    RecoverOptimizations,
    StartStudy,
    StudyCommand,
    StudyObjective,
)
from app.modules.agent_policy_optimizer.interface import AgentPolicyOptimizer
from app.modules.agent_policy_optimizer.wiring import get_agent_policy_optimizer
from app.schemas.optimizer_schema import (
    CancelReceiptSchema,
    CreateStudySchema,
    ParetoFrontierSchema,
    RecommendationBundleSchema,
    RecoverReceiptSchema,
    StudyCatalogSchema,
    StudyDetailSchema,
    StudyMutationReceiptSchema,
    TrialCatalogSchema,
    TrialReceiptSchema,
)


router = APIRouter(prefix="/v1/optimizer", tags=["agent-policy-optimizer"])
OptimizerDependency = Annotated[AgentPolicyOptimizer, Depends(get_agent_policy_optimizer)]
StudyIdPath = Annotated[str, Path(min_length=1, max_length=36, pattern=r"^[A-Za-z0-9_-]+$")]
TrialIdPath = Annotated[str, Path(min_length=1, max_length=36, pattern=r"^[A-Za-z0-9_-]+$")]


@router.post("/studies", response_model=StudyMutationReceiptSchema, status_code=status.HTTP_201_CREATED)
def create_study(payload: CreateStudySchema, optimizer: OptimizerDependency) -> StudyMutationReceiptSchema:
    receipt = optimizer.submit(
        StudyCommand(
            request_id=payload.request_id,
            label=payload.label,
            base_policy_id=payload.base_policy_id,
            objective=StudyObjective(payload.objective),
            max_candidates=payload.max_candidates,
            max_evaluations=payload.max_evaluations,
            search_space=_search_space(payload.search_space.model_dump()),
            weights=_weights(payload.weights.model_dump()),
            seed=payload.seed,
            deadline_at=payload.deadline_at,
        )
    )
    return StudyMutationReceiptSchema(**_study_receipt(receipt))


@router.get("/studies", response_model=StudyCatalogSchema)
def list_studies(
    optimizer: OptimizerDependency,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> StudyCatalogSchema:
    result = cast("dict[str, object]", optimizer.inspect(ListOptimizationStudies(limit=limit)))
    return StudyCatalogSchema(items=result["items"])  # type: ignore[arg-type]


@router.get("/studies/{study_id}", response_model=StudyDetailSchema)
def get_study(study_id: StudyIdPath, optimizer: OptimizerDependency) -> StudyDetailSchema:
    detail = cast("dict[str, object]", optimizer.inspect(GetOptimizationStudy(study_id=study_id)))
    return StudyDetailSchema(**detail)


@router.get("/studies/{study_id}/trials", response_model=TrialCatalogSchema)
def list_trials(
    study_id: StudyIdPath,
    optimizer: OptimizerDependency,
    limit: Annotated[int, Query(ge=1, le=200)] = 200,
) -> TrialCatalogSchema:
    result = cast(
        "dict[str, object]",
        optimizer.inspect(ListOptimizationTrials(study_id=study_id, limit=limit)),
    )
    return TrialCatalogSchema(items=result["items"])  # type: ignore[arg-type]


@router.get("/trials/{trial_id}", response_model=TrialReceiptSchema)
def get_trial(trial_id: TrialIdPath, optimizer: OptimizerDependency) -> TrialReceiptSchema:
    detail = cast("dict[str, object]", optimizer.inspect(GetOptimizationTrial(trial_id=trial_id)))
    return TrialReceiptSchema(**_trial_payload(detail))


@router.post("/studies/{study_id}/start", response_model=StudyMutationReceiptSchema)
def start_study(study_id: StudyIdPath, optimizer: OptimizerDependency) -> StudyMutationReceiptSchema:
    receipt = optimizer.start(study_id)
    return StudyMutationReceiptSchema(**_study_receipt(receipt))


@router.post("/studies/{study_id}/cancel", response_model=CancelReceiptSchema)
def cancel_study(study_id: StudyIdPath, optimizer: OptimizerDependency) -> CancelReceiptSchema:
    receipt = optimizer.cancel(study_id)
    return CancelReceiptSchema(
        study_id=str(receipt["study_id"]),
        status=str(receipt["status"]),
        cancelled=bool(receipt.get("cancelled", False)),
    )


@router.post("/studies/{study_id}/recover", response_model=RecoverReceiptSchema)
def recover_study(study_id: StudyIdPath, optimizer: OptimizerDependency) -> RecoverReceiptSchema:
    recovered = optimizer.recover(RecoverOptimizations(now=datetime.now(UTC), study_id=study_id))
    return RecoverReceiptSchema(recovered_trials=recovered)


@router.get("/studies/{study_id}/pareto", response_model=ParetoFrontierSchema)
def get_pareto(study_id: StudyIdPath, optimizer: OptimizerDependency) -> ParetoFrontierSchema:
    result = cast("dict[str, object]", optimizer.inspect(GetOptimizationPareto(study_id=study_id)))
    return ParetoFrontierSchema(**result)


@router.get("/studies/{study_id}/recommendation", response_model=RecommendationBundleSchema)
def get_recommendation(study_id: StudyIdPath, optimizer: OptimizerDependency) -> RecommendationBundleSchema:
    result = cast("dict[str, object]", optimizer.inspect(GetOptimizationRecommendation(study_id=study_id)))
    return RecommendationBundleSchema(**result)


def _search_space(payload: dict[str, dict[str, int]]):
    from app.modules.agent_policy_optimizer.contracts import SearchSpace, SearchSpaceBound

    return SearchSpace(
        **{
            name: SearchSpaceBound(minimum=bounds["minimum"], maximum=bounds["maximum"])
            for name, bounds in payload.items()
        }
    )


def _weights(payload: dict[str, int]):
    from app.modules.agent_policy_optimizer.contracts import ScoreWeights

    return ScoreWeights(**payload)


def _study_receipt(receipt: dict[str, object]) -> dict[str, object]:
    return {
        "study_id": receipt.get("study_id"),
        "status": receipt.get("status"),
        "created": receipt.get("created"),
        "cancelled": receipt.get("cancelled"),
        "replayed": bool(receipt.get("replayed", False)),
    }


def _trial_payload(detail: dict[str, object]) -> dict[str, object]:
    payload = dict(detail)
    payload["is_baseline"] = bool(detail.get("is_baseline", False))
    return payload
