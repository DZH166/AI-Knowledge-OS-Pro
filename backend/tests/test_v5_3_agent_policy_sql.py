from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
from pathlib import Path

import pytest
from sqlalchemy.orm import sessionmaker

from app.core.errors import ServiceError
from app.db.session import Base, create_database_engine
from app.models.agent_evaluation import AgentEvaluation
from app.models.agent_event import AgentEvent
from app.models.agent_policy import AgentPolicyVersion
from app.models.agent_run import AgentRequirement, AgentRun, AgentToolCall
from app.models.knowledge_space import KnowledgeSpace
from app.modules.agent_policy.config import RetrievalPolicyConfig, canonical_policy_json, policy_fingerprint
from app.modules.agent_policy.contracts import (
    ActivatePolicy,
    ComparePolicies,
    CreatePolicy,
    GetActivePolicy,
    GetPolicy,
    ListPolicies,
    PolicyStatus,
    RollbackPolicy,
    SimulatePolicy,
)
from app.modules.agent_policy.service import SqlAgentPolicy
from app.modules.agent_control.report import REQUIRED_HARD_GATES


DEFAULT_POLICY_ID = "00000000-0000-0000-0000-000000000001"


@pytest.fixture()
def policy_factory(tmp_path: Path):
    engine = create_database_engine(f"sqlite:///{(tmp_path / 'policy.db').as_posix()}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    config = RetrievalPolicyConfig()
    with factory.begin() as session:
        session.add(
            AgentPolicyVersion(
                id=DEFAULT_POLICY_ID,
                policy_key="default-research",
                version=1,
                label="Balanced evidence retrieval",
                status="active",
                config_schema_version=1,
                config_json=canonical_policy_json(config),
                config_sha256=policy_fingerprint(config),
                base_policy_id=None,
                created_by="system:test",
                has_been_active=1,
            )
        )
    try:
        yield factory
    finally:
        engine.dispose()


def _add_passed_evaluation(factory, detail, evaluation_id: str) -> None:
    with factory.begin() as session:
        session.add(
            AgentEvaluation(
                id=evaluation_id,
                request_id=f"request-{evaluation_id}",
                request_payload_hash="a" * 64,
                label="Candidate evaluation",
                mode="deterministic_recording",
                status="passed",
                policy_fingerprint=detail.config_sha256,
                policy_version_id=detail.id,
                policy_snapshot_json=canonical_policy_json(detail.config),
                dataset_name="v5_fixed_evidence_cases",
                dataset_path="evaluation/v5/cases.jsonl",
                dataset_sha256="b" * 64,
                evaluator_sha256="c" * 64,
                report_sha256="d" * 64,
                schema_version=2,
                case_count=60,
                case_pass_rate_millis=1000,
                external_provider_calls=0,
                failure_case_count=0,
                category_counts_json="{}",
                metrics_json="{}",
                hard_gates_json=json.dumps(
                    {gate: True for gate in sorted(REQUIRED_HARD_GATES)},
                    separators=(",", ":"),
                ),
                failure_case_ids_json="[]",
                report_json="{}",
                provider_boundary="not a real-model quality benchmark",
                attempt=1,
            )
        )


def test_create_policy_is_idempotent_immutable_and_catalogued(policy_factory) -> None:
    policy = SqlAgentPolicy(policy_factory)
    config = replace(RetrievalPolicyConfig(), factual_top_k=11)

    first = policy.submit(
        CreatePolicy(
            request_id="create-1",
            label="Factual precision candidate",
            base_policy_id=DEFAULT_POLICY_ID,
            config=config,
        )
    )
    replay = policy.submit(
        CreatePolicy(
            request_id="create-1",
            label="Factual precision candidate",
            base_policy_id=DEFAULT_POLICY_ID,
            config=config,
        )
    )

    assert first.policy_id == replay.policy_id
    assert first.version == 2
    assert first.status is PolicyStatus.DRAFT
    assert replay.replayed is True
    detail = policy.inspect(GetPolicy(first.policy_id))
    assert detail.config == config
    assert detail.config_sha256 == policy_fingerprint(config)
    assert [item.version for item in policy.inspect(ListPolicies()).items] == [2, 1]

    with pytest.raises(ServiceError) as conflict:
        policy.submit(
            CreatePolicy(
                request_id="create-1",
                label="Changed payload",
                base_policy_id=DEFAULT_POLICY_ID,
                config=RetrievalPolicyConfig(),
            )
        )
    assert conflict.value.code == "POLICY_IDEMPOTENCY_CONFLICT"


def test_concurrent_drafts_receive_distinct_monotonic_versions(policy_factory) -> None:
    policy = SqlAgentPolicy(policy_factory)

    def create(index: int):
        return policy.submit(
            CreatePolicy(
                request_id=f"concurrent-{index}",
                label=f"Concurrent candidate {index}",
                base_policy_id=DEFAULT_POLICY_ID,
                config=replace(RetrievalPolicyConfig(), factual_top_k=9 + index),
            )
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        receipts = list(executor.map(create, (1, 2)))

    assert {item.version for item in receipts} == {2, 3}
    assert len({item.policy_id for item in receipts}) == 2


def test_activation_requires_matching_passed_evaluation_and_supports_audited_rollback(
    policy_factory,
) -> None:
    policy = SqlAgentPolicy(policy_factory)
    candidate = policy.submit(
        CreatePolicy(
            request_id="candidate-create",
            label="Recall candidate",
            base_policy_id=DEFAULT_POLICY_ID,
            config=replace(RetrievalPolicyConfig(), comparative_top_k=18),
        )
    )

    with pytest.raises(ServiceError) as missing_evaluation:
        policy.submit(
            ActivatePolicy(
                request_id="activate-missing",
                policy_id=candidate.policy_id,
                expected_active_policy_id=DEFAULT_POLICY_ID,
                evaluation_id="evaluation-missing",
            )
        )
    assert missing_evaluation.value.code == "POLICY_EVALUATION_REQUIRED"

    detail = policy.inspect(GetPolicy(candidate.policy_id))
    _add_passed_evaluation(policy_factory, detail, "evaluation-candidate")

    activated = policy.submit(
        ActivatePolicy(
            request_id="activate-candidate",
            policy_id=candidate.policy_id,
            expected_active_policy_id=DEFAULT_POLICY_ID,
            evaluation_id="evaluation-candidate",
        )
    )
    assert activated.status is PolicyStatus.ACTIVE
    assert policy.inspect(GetActivePolicy()).id == candidate.policy_id
    assert policy.inspect(GetPolicy(DEFAULT_POLICY_ID)).status is PolicyStatus.RETIRED

    replay = policy.submit(
        ActivatePolicy(
            request_id="activate-candidate",
            policy_id=candidate.policy_id,
            expected_active_policy_id=DEFAULT_POLICY_ID,
            evaluation_id="evaluation-candidate",
        )
    )
    assert replay.replayed is True

    with pytest.raises(ServiceError) as stale:
        policy.submit(
            RollbackPolicy(
                request_id="rollback-stale",
                policy_id=DEFAULT_POLICY_ID,
                expected_active_policy_id=DEFAULT_POLICY_ID,
            )
        )
    assert stale.value.code == "POLICY_ACTIVE_CONFLICT"

    rollback = policy.submit(
        RollbackPolicy(
            request_id="rollback-default",
            policy_id=DEFAULT_POLICY_ID,
            expected_active_policy_id=candidate.policy_id,
        )
    )
    assert rollback.status is PolicyStatus.ACTIVE
    assert policy.inspect(GetActivePolicy()).id == DEFAULT_POLICY_ID
    assert policy.inspect(GetPolicy(candidate.policy_id)).status is PolicyStatus.RETIRED


def test_activation_rejects_tampered_fixed_evaluation_gate_set(policy_factory) -> None:
    policy = SqlAgentPolicy(policy_factory)
    candidate = policy.submit(
        CreatePolicy(
            request_id="tampered-candidate-create",
            label="Tampered evaluation candidate",
            base_policy_id=DEFAULT_POLICY_ID,
            config=replace(RetrievalPolicyConfig(), temporal_top_k=15),
        )
    )
    detail = policy.inspect(GetPolicy(candidate.policy_id))
    _add_passed_evaluation(policy_factory, detail, "evaluation-tampered-gates")
    with policy_factory.begin() as session:
        evaluation = session.get(AgentEvaluation, "evaluation-tampered-gates")
        assert evaluation is not None
        evaluation.hard_gates_json = '{"all_cases_pass":true}'

    with pytest.raises(ServiceError) as rejected:
        policy.submit(
            ActivatePolicy(
                request_id="activate-tampered-gates",
                policy_id=candidate.policy_id,
                expected_active_policy_id=DEFAULT_POLICY_ID,
                evaluation_id="evaluation-tampered-gates",
            )
        )

    assert rejected.value.code == "POLICY_EVALUATION_REQUIRED"
    assert policy.inspect(GetActivePolicy()).id == DEFAULT_POLICY_ID


def test_concurrent_activation_with_same_expected_active_has_one_winner(policy_factory) -> None:
    policy = SqlAgentPolicy(policy_factory)
    candidates = [
        policy.submit(
            CreatePolicy(
                request_id=f"activation-race-create-{index}",
                label=f"Activation race {index}",
                base_policy_id=DEFAULT_POLICY_ID,
                config=replace(RetrievalPolicyConfig(), factual_top_k=8 + index),
            )
        )
        for index in (1, 2)
    ]
    for index, candidate in enumerate(candidates, start=1):
        _add_passed_evaluation(
            policy_factory,
            policy.inspect(GetPolicy(candidate.policy_id)),
            f"evaluation-race-{index}",
        )

    def activate(index: int):
        candidate = candidates[index]
        try:
            return policy.submit(
                ActivatePolicy(
                    request_id=f"activation-race-{index}",
                    policy_id=candidate.policy_id,
                    expected_active_policy_id=DEFAULT_POLICY_ID,
                    evaluation_id=f"evaluation-race-{index + 1}",
                )
            )
        except ServiceError as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(activate, (0, 1)))

    winners = [item for item in results if not isinstance(item, str)]
    failures = [item for item in results if isinstance(item, str)]
    assert len(winners) == 1
    assert failures == ["POLICY_ACTIVE_CONFLICT"] or failures == ["POLICY_WRITE_CONFLICT"]
    assert policy.inspect(GetActivePolicy()).id == winners[0].policy_id


def test_policy_compare_and_simulate_use_public_interface_without_executing_runtime(policy_factory) -> None:
    policy = SqlAgentPolicy(policy_factory)
    candidate = policy.submit(
        CreatePolicy(
            request_id="simulation-policy",
            label="Simulation candidate",
            base_policy_id=DEFAULT_POLICY_ID,
            config=replace(RetrievalPolicyConfig(), factual_top_k=12, neighbor_before=2),
        )
    )
    comparison = policy.inspect(ComparePolicies(DEFAULT_POLICY_ID, candidate.policy_id))
    assert [(item.field, item.left, item.right) for item in comparison.changes] == [
        ("factual_top_k", 8, 12),
        ("neighbor_before", 1, 2),
    ]

    with policy_factory.begin() as session:
        space = KnowledgeSpace(name="Simulation", description="persisted facts")
        session.add(space)
        session.flush()
        session.add(
            AgentRun(
                id="run-simulation",
                space_id=space.id,
                goal="Private goal is not returned",
                requested_mode="force_agent",
                effective_mode="force_agent",
                status="completed",
                phase="persist_artifact",
                version=4,
                execution_epoch=0,
                scope_snapshot_json="{}",
                scope_digest="e" * 64,
                deliverable_json="{}",
                policy_snapshot_json="{}",
                budget_limits_json="{}",
                budget_usage_json="{}",
                provider_mode="demo",
                trace_id="trace-simulation",
                active_elapsed_ms=1,
            )
        )
        session.flush()
        session.add(
            AgentRequirement(
                id="requirement-simulation",
                run_id="run-simulation",
                plan_version=1,
                ordinal=1,
                text="private requirement",
                kind="factual",
                priority="must",
                depends_on_json="[]",
                status="covered",
            )
        )
        session.add_all(
            [
                AgentToolCall(
                    id="tool-search-simulation",
                    run_id="run-simulation",
                    invocation_key="search:requirement-simulation:1",
                    tool_name="search_evidence",
                    tool_version="1",
                    effect="read_evidence",
                    arguments_json="private arguments are deliberately not valid JSON",
                    arguments_digest="f" * 64,
                    status="completed",
                    result_json='{"count":1}',
                    execution_epoch=0,
                ),
                AgentToolCall(
                    id="tool-failed-simulation",
                    run_id="run-simulation",
                    invocation_key="search:requirement-simulation:3",
                    tool_name="search_evidence",
                    tool_version="1",
                    effect="read_evidence",
                    arguments_json="failed private arguments are deliberately not valid JSON",
                    arguments_digest="2" * 64,
                    status="failed",
                    result_json=None,
                    execution_epoch=0,
                ),
                AgentToolCall(
                    id="tool-neighbors-simulation",
                    run_id="run-simulation",
                    invocation_key="neighbors:evidence-1:2",
                    tool_name="read_neighbors",
                    tool_version="1",
                    effect="read_evidence",
                    arguments_json="private neighbor arguments are deliberately not valid JSON",
                    arguments_digest="1" * 64,
                    status="completed",
                    result_json='{"count":3}',
                    execution_epoch=0,
                ),
            ]
        )
        session.add_all(
            [
                AgentEvent(
                    event_id="event-search-simulation",
                    run_id="run-simulation",
                    run_sequence=1,
                    run_version=2,
                    event_type="tool.started",
                    payload_json=json.dumps(
                        {
                            "tool": "search_evidence",
                            "retrieval_policy": {
                                "policy_id": DEFAULT_POLICY_ID,
                                "policy_version": 1,
                                "reason_code": "requirement_kind:factual",
                                "top_k": 10,
                            },
                        },
                        separators=(",", ":"),
                    ),
                    visibility="public",
                    tool_call_id="tool-search-simulation",
                    trace_id="trace-simulation",
                ),
                AgentEvent(
                    event_id="event-neighbors-simulation",
                    run_id="run-simulation",
                    run_sequence=2,
                    run_version=3,
                    event_type="tool.started",
                    payload_json=json.dumps(
                        {
                            "tool": "read_neighbors",
                            "retrieval_policy": {
                                "policy_id": DEFAULT_POLICY_ID,
                                "policy_version": 1,
                                "reason_code": "bounded_neighbor_context",
                                "before": 1,
                                "after": 1,
                            },
                        },
                        separators=(",", ":"),
                    ),
                    visibility="public",
                    tool_call_id="tool-neighbors-simulation",
                    trace_id="trace-simulation",
                ),
                AgentEvent(
                    event_id="event-failed-simulation",
                    run_id="run-simulation",
                    run_sequence=3,
                    run_version=4,
                    event_type="tool.started",
                    payload_json=json.dumps(
                        {
                            "tool": "search_evidence",
                            "retrieval_policy": {
                                "policy_id": DEFAULT_POLICY_ID,
                                "policy_version": 1,
                                "reason_code": "requirement_kind:factual",
                                "top_k": 50,
                            },
                        },
                        separators=(",", ":"),
                    ),
                    visibility="public",
                    tool_call_id="tool-failed-simulation",
                    trace_id="trace-simulation",
                ),
            ]
        )

    simulation = policy.simulate(SimulatePolicy("run-simulation", candidate.policy_id))
    assert simulation.changed_decision_count == 2
    assert simulation.projected_candidate_window_delta == 2
    assert simulation.projected_neighbor_context_delta == 1
    assert "Private goal" not in str(simulation)
    assert "private requirement" not in str(simulation)


def test_policy_rejects_secret_looking_labels_and_unknown_base(policy_factory) -> None:
    policy = SqlAgentPolicy(policy_factory)
    with pytest.raises(ServiceError) as secret:
        policy.submit(
            CreatePolicy(
                request_id="secret-label",
                label="api_key=" + "sk-" + "policy-secret-value",
                base_policy_id=DEFAULT_POLICY_ID,
                config=RetrievalPolicyConfig(),
            )
        )
    assert secret.value.code == "POLICY_INPUT_REJECTED"

    with pytest.raises(ServiceError) as missing:
        policy.submit(
            CreatePolicy(
                request_id="missing-base",
                label="Missing base",
                base_policy_id="policy-missing",
                config=RetrievalPolicyConfig(),
            )
        )
    assert missing.value.code == "POLICY_NOT_FOUND"
