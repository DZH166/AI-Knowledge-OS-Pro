from __future__ import annotations

from dataclasses import asdict, replace
import json
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.db.session import Base, create_database_engine
from app.core.errors import ServiceError
from app.models.agent_event import AgentEvent
from app.models.agent_evidence import AgentEvidence, RequirementEvidence
from app.models.agent_policy import AgentPolicyVersion
from app.models.agent_run import AgentRequirement, AgentRun, AgentToolCall
from app.models.knowledge_space import KnowledgeSpace
from app.models.source import IndexRevision, MultimodalChunk, Source, SourceRevision
from app.modules.agent_policy.config import RetrievalPolicyConfig, canonical_policy_json, policy_fingerprint
from app.modules.evidence_agent.budget import BudgetUsage
from app.modules.evidence_agent.contracts import BudgetLimits
from app.modules.evidence_agent.controller import AgentRunner
from app.modules.evidence_index import (
    EvidenceSearchResult,
    EvidenceWindow,
    GetEvidenceNeighbors,
    PinnedEvidenceRef,
)


@pytest.fixture()
def adaptive_runtime_factory(tmp_path: Path):
    engine = create_database_engine(f"sqlite:///{(tmp_path / 'adaptive-runtime.db').as_posix()}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory.begin() as session:
        session.add(KnowledgeSpace(id=1, name="Adaptive runtime", description="test"))
    try:
        yield factory
    finally:
        engine.dispose()


def _seed_retrieval_run(factory, *, requirement_kind: str, pinned: bool = True) -> str:
    config = replace(
        RetrievalPolicyConfig(),
        factual_top_k=7,
        comparative_top_k=17,
        temporal_top_k=13,
        minimum_score_millis=450,
        max_hits_per_source=2,
        neighbor_before=2,
        neighbor_after=0,
    )
    run_id = f"run-{requirement_kind}-{'pinned' if pinned else 'legacy'}"
    with factory.begin() as session:
        if pinned:
            session.add(
                AgentPolicyVersion(
                    id="policy-adaptive-runtime",
                    policy_key="default-research",
                    version=4,
                    label="Adaptive runtime policy",
                    status="active",
                    config_schema_version=1,
                    config_json=canonical_policy_json(config),
                    config_sha256=policy_fingerprint(config),
                    base_policy_id=None,
                    created_by="test",
                    has_been_active=1,
                )
            )
        session.add(
            AgentRun(
                id=run_id,
                space_id=1,
                goal="Adaptive retrieval",
                requested_mode="force_agent",
                effective_mode="force_agent",
                status="running",
                phase="retrieve",
                version=1,
                execution_epoch=0,
                scope_snapshot_json='{"revisions":[],"space_id":1}',
                scope_digest="a" * 64,
                deliverable_json="{}",
                policy_snapshot_json="{}",
                decision_policy_id="policy-adaptive-runtime" if pinned else None,
                decision_policy_version=4 if pinned else None,
                decision_policy_fingerprint=policy_fingerprint(config) if pinned else None,
                decision_policy_snapshot_json=canonical_policy_json(config) if pinned else None,
                budget_limits_json=json.dumps(asdict(BudgetLimits())),
                budget_usage_json=json.dumps(BudgetUsage().as_dict()),
                provider_mode="demo",
                trace_id=f"trace-{requirement_kind}",
                active_elapsed_ms=0,
            )
        )
        session.flush()
        session.add(
            AgentRequirement(
                id=f"requirement-{requirement_kind}",
                run_id=run_id,
                plan_version=1,
                ordinal=1,
                text=f"Find {requirement_kind} evidence",
                kind=requirement_kind,
                priority="must",
                depends_on_json="[]",
                status="uncovered",
            )
        )
    return run_id


@pytest.mark.parametrize(
    ("requirement_kind", "expected_top_k"),
    [("factual", 7), ("comparative", 17), ("temporal", 13)],
)
def test_runner_applies_pinned_requirement_policy_and_persists_exact_decision(
    adaptive_runtime_factory,
    requirement_kind: str,
    expected_top_k: int,
) -> None:
    run_id = _seed_retrieval_run(
        adaptive_runtime_factory,
        requirement_kind=requirement_kind,
    )
    searches = []

    def search(request):
        searches.append(request)
        return EvidenceSearchResult(hits=())

    result = AgentRunner(adaptive_runtime_factory, search).advance_one(
        run_id,
        expected_version=1,
        execution_epoch=0,
    )

    assert result.applied is True
    assert searches[0].limit == expected_top_k
    with adaptive_runtime_factory() as session:
        call = session.scalar(
            select(AgentToolCall).where(
                AgentToolCall.run_id == run_id,
                AgentToolCall.tool_name == "search_evidence",
            )
        )
        arguments = json.loads(call.arguments_json)
        assert arguments == {
            "limit": expected_top_k,
            "max_hits_per_source": 2,
            "minimum_score_millis": 450,
            "query": f"Find {requirement_kind} evidence",
            "revision_ids": [],
        }
        event = session.scalar(
            select(AgentEvent).where(
                AgentEvent.run_id == run_id,
                AgentEvent.event_type == "tool.started",
            )
        )
        payload = json.loads(event.payload_json)
        assert payload["retrieval_policy"] == {
            "max_hits_per_source": 2,
            "minimum_score_millis": 450,
            "policy_id": "policy-adaptive-runtime",
            "policy_version": 4,
            "reason_code": f"requirement_kind:{requirement_kind}",
            "top_k": expected_top_k,
        }


def test_legacy_run_keeps_v5_2_search_arguments_and_top_k(adaptive_runtime_factory) -> None:
    run_id = _seed_retrieval_run(
        adaptive_runtime_factory,
        requirement_kind="factual",
        pinned=False,
    )
    searches = []

    def search(request):
        searches.append(request)
        return EvidenceSearchResult(hits=())

    AgentRunner(adaptive_runtime_factory, search).advance_one(
        run_id,
        expected_version=1,
        execution_epoch=0,
    )

    assert searches[0].limit == 10
    with adaptive_runtime_factory() as session:
        call = session.scalar(select(AgentToolCall).where(AgentToolCall.run_id == run_id))
        assert json.loads(call.arguments_json) == {
            "query": "Find factual evidence",
            "revision_ids": [],
        }


def test_runner_applies_pinned_neighbor_window_to_real_evidence_query(adaptive_runtime_factory) -> None:
    run_id = _seed_retrieval_run(
        adaptive_runtime_factory,
        requirement_kind="factual",
    )
    content_hash = "b" * 64
    locator_json = '{"chunk_index":0,"kind":"document_chunk"}'
    with adaptive_runtime_factory.begin() as session:
        source = Source(
            id=1,
            space_id=1,
            source_type="document",
            title="Neighbor source",
            file_size=10,
            status="ready",
        )
        session.add(source)
        session.flush()
        revision = SourceRevision(
            id=1,
            source_id=source.id,
            revision_number=1,
            status="active",
            content_hash="c" * 64,
            chunk_count=1,
            vector_count=1,
            validation_status="valid",
        )
        session.add(revision)
        session.flush()
        index_revision = IndexRevision(
            id=1,
            source_id=source.id,
            revision_id=revision.id,
            status="active",
            index_version="v5.3-test",
            point_count=1,
            validation_status="valid",
        )
        chunk = MultimodalChunk(
            id=1,
            source_id=source.id,
            revision_id=revision.id,
            chunk_index=0,
            modality="text",
            source_type="document",
            content_text="center evidence",
            content_hash=content_hash,
            search_text="center evidence",
            raw_payload_json="{}",
            locator_json=locator_json,
            status="active",
        )
        session.add_all([index_revision, chunk])
        session.flush()
        source.active_revision_id = revision.id
        source.latest_revision_id = revision.id
        source.active_index_revision_id = index_revision.id
        run = session.get(AgentRun, run_id)
        run.scope_snapshot_json = json.dumps(
            {
                "space_id": 1,
                "revisions": [
                    {
                        "source_id": 1,
                        "revision_id": 1,
                        "index_revision_id": 1,
                        "content_hash": "c" * 64,
                    }
                ],
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        search_call = AgentToolCall(
            id="search-before-neighbors",
            run_id=run_id,
            invocation_key="search:requirement-factual:1",
            tool_name="search_evidence",
            tool_version="2",
            effect="read_evidence",
            arguments_json='{"limit":7,"query":"center","revision_ids":[1]}',
            arguments_digest="d" * 64,
            status="completed",
            result_json='{"count":1}',
            execution_epoch=0,
        )
        session.add(search_call)
        session.flush()
        evidence = AgentEvidence(
            id="evidence-center",
            run_id=run_id,
            source_id=1,
            revision_id=1,
            index_revision_id=1,
            chunk_id=1,
            source_type="document",
            locator_json=locator_json,
            locator_digest="e" * 64,
            revision_content_hash="c" * 64,
            evidence_content_hash=content_hash,
            excerpt_preview="center evidence",
            retrieved_by_tool_call_id=search_call.id,
            query="center",
            retrieval_scores_json='{"hybrid":0.9}',
            trust_level="untrusted",
            active_at_snapshot=1,
        )
        session.add(evidence)
        session.flush()
        session.add(
            RequirementEvidence(
                requirement_id="requirement-factual",
                evidence_id=evidence.id,
                relation="candidate",
                method="retrieval_candidate",
                confidence_millis=800,
                reason_code="semantic_retrieval_candidate",
            )
        )
        session.add(
            AgentToolCall(
                id="open-before-neighbors",
                run_id=run_id,
                invocation_key="open:evidence-center:2",
                tool_name="open_evidence",
                tool_version="1",
                effect="read_evidence",
                arguments_json='{"evidence_id":"evidence-center"}',
                arguments_digest="f" * 64,
                status="completed",
                result_json="{}",
                execution_epoch=0,
            )
        )

    queries = []

    def evidence_query(query):
        queries.append(query)
        return EvidenceWindow(
            center_chunk_id=1,
            items=(
                PinnedEvidenceRef(
                    source_id=1,
                    revision_id=1,
                    index_revision_id=1,
                    chunk_id=1,
                    source_type="document",
                    modality="text",
                    content_hash=content_hash,
                    locator={"kind": "document_chunk", "chunk_index": 0},
                    excerpt="center evidence",
                    currently_active=True,
                ),
            ),
        )

    result = AgentRunner(
        adaptive_runtime_factory,
        lambda _request: pytest.fail("search should not repeat"),
        evidence_query=evidence_query,
    ).advance_one(run_id, expected_version=1, execution_epoch=0)

    assert result.applied is True
    assert isinstance(queries[0], GetEvidenceNeighbors)
    assert queries[0].before == 2
    assert queries[0].after == 0
    with adaptive_runtime_factory() as session:
        call = session.scalar(
            select(AgentToolCall).where(
                AgentToolCall.run_id == run_id,
                AgentToolCall.tool_name == "read_neighbors",
            )
        )
        assert json.loads(call.arguments_json) == {
            "after": 0,
            "before": 2,
            "evidence_id": "evidence-center",
        }


def test_runner_rejects_corrupted_pinned_policy_before_search(adaptive_runtime_factory) -> None:
    run_id = _seed_retrieval_run(
        adaptive_runtime_factory,
        requirement_kind="factual",
    )
    with adaptive_runtime_factory.begin() as session:
        run = session.get(AgentRun, run_id)
        payload = json.loads(run.decision_policy_snapshot_json)
        payload["factual_top_k"] = True
        run.decision_policy_snapshot_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))

    with pytest.raises(ServiceError) as exc_info:
        AgentRunner(
            adaptive_runtime_factory,
            lambda _request: pytest.fail("corrupt policy must fail before search"),
        ).advance_one(run_id, expected_version=1, execution_epoch=0)
    assert exc_info.value.code == "POLICY_SNAPSHOT_INVALID"
