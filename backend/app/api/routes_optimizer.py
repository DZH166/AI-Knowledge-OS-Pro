from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.modules.agent_policy_optimizer.contracts import (
    CancelStudy,
    ExportComparison,
    ConvertRecommendation,
    NextRound,
    DiffTrialAgainstActive,
    FailStudy,
    RetryTrial,
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
from app.modules.agent_policy_optimizer.templates import STUDY_TEMPLATES
from app.modules.agent_policy_optimizer.wiring import get_agent_policy_optimizer
from app.schemas.optimizer_schema import (
    CancelReceiptSchema,
    CategoryComparisonSchema,
    ConvertDraftSchema,
    ConvertReceiptSchema,
    CreateShareLinkSchema,
    CreateStudyFromTemplateSchema,
    DiffReceiptSchema,
    ExportComparisonReceiptSchema,
    ExportComparisonSchema,
    NextRoundReceiptSchema,
    NextRoundSchema,
    FailReceiptSchema,
    FailStudySchema,
    RetryReceiptSchema,
    CreateStudySchema,
    ParetoFrontierSchema,
    RecommendationBundleSchema,
    RecoverReceiptSchema,
    ShareLinkReceiptSchema,
    StudyCatalogSchema,
    StudyEventCatalogSchema,
    StudyDetailSchema,
    StudyMutationReceiptSchema,
    StudyOverviewSchema,
    StudyTemplateCatalogSchema,
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
            warm_start_study_id=payload.warm_start_study_id,
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


@router.post(
    "/studies/{study_id}/recommendation/{trial_id}/convert-draft",
    response_model=ConvertReceiptSchema,
)
def convert_recommendation_to_draft(
    study_id: StudyIdPath,
    trial_id: TrialIdPath,
    payload: ConvertDraftSchema,
    optimizer: OptimizerDependency,
) -> ConvertReceiptSchema:
    receipt = optimizer.convert_to_draft(
        ConvertRecommendation(
            study_id=study_id,
            trial_id=trial_id,
            request_id=payload.request_id,
            label=payload.label,
        )
    )
    return ConvertReceiptSchema(**receipt)


@router.get("/studies/{study_id}/trials/{trial_id}/diff", response_model=DiffReceiptSchema)
def diff_trial_against_active(
    study_id: StudyIdPath,
    trial_id: TrialIdPath,
    optimizer: OptimizerDependency,
) -> DiffReceiptSchema:
    result = optimizer.inspect(DiffTrialAgainstActive(study_id=study_id, trial_id=trial_id))
    return DiffReceiptSchema(**result)


@router.post("/trials/{trial_id}/retry", response_model=RetryReceiptSchema)
def retry_trial(trial_id: TrialIdPath, optimizer: OptimizerDependency) -> RetryReceiptSchema:
    receipt = optimizer.retry_trial(RetryTrial(trial_id=trial_id))
    return RetryReceiptSchema(**receipt)


@router.post("/studies/{study_id}/fail", response_model=FailReceiptSchema)
def fail_study(study_id: StudyIdPath, payload: FailStudySchema, optimizer: OptimizerDependency) -> FailReceiptSchema:
    receipt = optimizer.fail_study(FailStudy(study_id=study_id, reason=payload.reason))
    return FailReceiptSchema(
        study_id=str(receipt["study_id"]),
        status=str(receipt["status"]),
        cancelled=bool(receipt.get("cancelled", False)),
    )


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


@router.post("/studies/{study_id}/next-round", response_model=NextRoundReceiptSchema)
def start_next_round(
    study_id: StudyIdPath,
    payload: NextRoundSchema,
    optimizer: OptimizerDependency,
) -> NextRoundReceiptSchema:
    receipt = optimizer.start_next_round(
        NextRound(study_id=study_id, request_id=payload.request_id)
    )
    return NextRoundReceiptSchema(
        study_id=str(receipt["study_id"]),
        round_no=int(receipt["round_no"]),
        created=int(receipt["created"]),
        replayed=bool(receipt.get("replayed", False)),
    )


@router.get("/studies/{study_id}/trials/{trial_id}/categories", response_model=CategoryComparisonSchema)
def get_trial_categories(
    study_id: StudyIdPath,
    trial_id: TrialIdPath,
    optimizer: OptimizerDependency,
) -> CategoryComparisonSchema:
    result = optimizer.inspect_categories(study_id=study_id, trial_id=trial_id)
    return CategoryComparisonSchema(**result)


@router.get("/studies/{study_id}/overview", response_model=StudyOverviewSchema)
def get_study_overview(study_id: StudyIdPath, optimizer: OptimizerDependency) -> StudyOverviewSchema:
    overview = optimizer.inspect_overview(study_id)
    return StudyOverviewSchema(**overview)


@router.get("/study-templates", response_model=StudyTemplateCatalogSchema)
def list_study_templates() -> StudyTemplateCatalogSchema:
    return StudyTemplateCatalogSchema(
        items=[
            {
                "key": template.key,
                "description": template.description,
                "objective": template.objective.value,
                "max_candidates": template.max_candidates,
                "max_evaluations": template.max_evaluations,
                "seed": template.seed,
            }
            for template in STUDY_TEMPLATES.values()
        ]
    )


@router.post(
    "/studies/from-template",
    response_model=StudyMutationReceiptSchema,
    status_code=status.HTTP_201_CREATED,
)
def create_study_from_template(
    payload: CreateStudyFromTemplateSchema,
    optimizer: OptimizerDependency,
) -> StudyMutationReceiptSchema:
    receipt = optimizer.create_from_template(
        request_id=payload.request_id,
        label=payload.label,
        base_policy_id=payload.base_policy_id,
        template_key=payload.template_key,
        seed=payload.seed,
        max_candidates=payload.max_candidates,
        max_evaluations=payload.max_evaluations,
        warm_start_study_id=payload.warm_start_study_id,
    )
    return StudyMutationReceiptSchema(
        study_id=str(receipt["study_id"]),
        status=str(receipt["status"]),
        replayed=bool(receipt.get("replayed", False)),
    )


@router.get("/studies/{study_id}/events", response_model=StudyEventCatalogSchema)
def list_study_events(
    study_id: StudyIdPath,
    optimizer: OptimizerDependency,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    after: Annotated[str | None, Query(min_length=1, max_length=36)] = None,
) -> StudyEventCatalogSchema:
    events = optimizer.inspect_events(study_id, limit=limit, after=after)
    return StudyEventCatalogSchema(**events)


@router.post(
    "/studies/{study_id}/export-comparison",
    response_model=ExportComparisonReceiptSchema,
)
def export_comparison_report(
    study_id: StudyIdPath,
    payload: ExportComparisonSchema,
    optimizer: OptimizerDependency,
) -> ExportComparisonReceiptSchema:
    receipt = optimizer.export_comparison(
        ExportComparison(
            study_id=study_id,
            trial_ids=tuple(payload.trial_ids),
            include_categories=payload.include_categories,
        )
    )
    return ExportComparisonReceiptSchema(
        study_id=str(receipt["study_id"]),
        markdown=str(receipt["markdown"]),
        sha256=str(receipt["sha256"]),
        generated_trial_ids=list(receipt["generated_trial_ids"]),
    )
