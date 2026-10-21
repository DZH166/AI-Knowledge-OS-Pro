from __future__ import annotations

from dataclasses import asdict
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Path, Query, status

from app.modules.agent_policy.config import RetrievalPolicyConfig
from app.modules.agent_policy.contracts import (
    ActivatePolicy,
    ComparePolicies,
    CreatePolicy,
    GetActivePolicy,
    GetPolicy,
    ListPolicies,
    PolicyCatalog,
    PolicyComparison,
    PolicyDetail,
    PolicyReceipt,
    PolicySimulation,
    PolicyStatus,
    RollbackPolicy,
    SimulatePolicy,
)
from app.modules.agent_policy.interface import AgentPolicy
from app.modules.agent_policy.wiring import get_agent_policy
from app.schemas.agent_policy_schema import (
    ActivatePolicySchema,
    CreatePolicySchema,
    PolicyCatalogSchema,
    PolicyComparisonSchema,
    PolicyDetailSchema,
    PolicyReceiptSchema,
    PolicySimulationSchema,
    RollbackPolicySchema,
    SimulatePolicySchema,
)


router = APIRouter(prefix="/v1/agent-policies", tags=["agent-policy"])
AgentPolicyDependency = Annotated[AgentPolicy, Depends(get_agent_policy)]
PolicyIdPath = Annotated[
    str,
    Path(min_length=1, max_length=36, pattern=r"^[A-Za-z0-9_-]+$"),
]


@router.get("", response_model=PolicyCatalogSchema)
def list_policies(
    policy: AgentPolicyDependency,
    policy_status: Annotated[PolicyStatus | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> PolicyCatalogSchema:
    catalog = cast(PolicyCatalog, policy.inspect(ListPolicies(status=policy_status, limit=limit)))
    return PolicyCatalogSchema(items=[asdict(item) for item in catalog.items])


@router.get("/active", response_model=PolicyDetailSchema)
def get_active_policy_detail(policy: AgentPolicyDependency) -> PolicyDetailSchema:
    detail = cast(PolicyDetail, policy.inspect(GetActivePolicy()))
    return PolicyDetailSchema(**asdict(detail))


@router.get("/compare", response_model=PolicyComparisonSchema)
def compare_policy_versions(
    policy: AgentPolicyDependency,
    left_id: Annotated[str, Query(min_length=1, max_length=36, pattern=r"^[A-Za-z0-9_-]+$")],
    right_id: Annotated[str, Query(min_length=1, max_length=36, pattern=r"^[A-Za-z0-9_-]+$")],
) -> PolicyComparisonSchema:
    comparison = cast(
        PolicyComparison,
        policy.inspect(ComparePolicies(left_id=left_id, right_id=right_id)),
    )
    return PolicyComparisonSchema(**asdict(comparison))


@router.post("/simulate", response_model=PolicySimulationSchema)
def simulate_policy(
    payload: SimulatePolicySchema,
    policy: AgentPolicyDependency,
) -> PolicySimulationSchema:
    simulation = cast(
        PolicySimulation,
        policy.simulate(SimulatePolicy(run_id=payload.run_id, policy_id=payload.policy_id)),
    )
    return PolicySimulationSchema(**asdict(simulation))


@router.post("", response_model=PolicyReceiptSchema, status_code=status.HTTP_201_CREATED)
def create_policy(
    payload: CreatePolicySchema,
    policy: AgentPolicyDependency,
) -> PolicyReceiptSchema:
    receipt = policy.submit(
        CreatePolicy(
            request_id=payload.request_id,
            label=payload.label,
            base_policy_id=payload.base_policy_id,
            config=RetrievalPolicyConfig(**payload.config.model_dump()),
        )
    )
    return PolicyReceiptSchema(**asdict(receipt))


@router.get("/{policy_id}", response_model=PolicyDetailSchema)
def get_policy_detail(policy_id: PolicyIdPath, policy: AgentPolicyDependency) -> PolicyDetailSchema:
    detail = cast(PolicyDetail, policy.inspect(GetPolicy(policy_id)))
    return PolicyDetailSchema(**asdict(detail))


@router.post("/{policy_id}/activate", response_model=PolicyReceiptSchema)
def activate_policy(
    policy_id: PolicyIdPath,
    payload: ActivatePolicySchema,
    policy: AgentPolicyDependency,
) -> PolicyReceiptSchema:
    receipt = cast(
        PolicyReceipt,
        policy.submit(
            ActivatePolicy(
                request_id=payload.request_id,
                policy_id=policy_id,
                expected_active_policy_id=payload.expected_active_policy_id,
                evaluation_id=payload.evaluation_id,
            )
        ),
    )
    return PolicyReceiptSchema(**asdict(receipt))


@router.post("/{policy_id}/rollback", response_model=PolicyReceiptSchema)
def rollback_policy(
    policy_id: PolicyIdPath,
    payload: RollbackPolicySchema,
    policy: AgentPolicyDependency,
) -> PolicyReceiptSchema:
    receipt = cast(
        PolicyReceipt,
        policy.submit(
            RollbackPolicy(
                request_id=payload.request_id,
                policy_id=policy_id,
                expected_active_policy_id=payload.expected_active_policy_id,
            )
        ),
    )
    return PolicyReceiptSchema(**asdict(receipt))
