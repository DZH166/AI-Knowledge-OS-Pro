from __future__ import annotations

import json

import httpx
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings
from app.core.errors import DependencyUnavailableError
from app.db.session import Base
from app.models.agent_run import AgentModelCall
from app.models.knowledge_space import KnowledgeSpace
from app.modules.evidence_agent.contracts import (
    BudgetLimits,
    DeliverableSpec,
    GetRun,
    OpenRun,
    PermissionPolicy,
    RunMode,
    ScopeSelector,
)
from app.modules.evidence_agent.controller import AgentRunner
from app.modules.evidence_agent.service import SqlEvidenceAgent
from app.modules.evidence_index import EvidenceSearchResult
from app.services import providers as provider_module
from app.services.agent_model import AgentModelInvocationError, PlanModelInput, StructuredAgentModel
from app.services.llm_service import LLMService, ModelCallLimits
from app.services.providers import OpenAICompatibleLLMProvider


def _mock_http(monkeypatch: pytest.MonkeyPatch, handler) -> None:
    real_client = httpx.Client
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        provider_module.httpx,
        "Client",
        lambda *, timeout: real_client(transport=transport, timeout=timeout),
    )
    monkeypatch.setattr(provider_module.time, "sleep", lambda _seconds: None)


def test_bounded_real_provider_caps_output_and_does_not_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        return httpx.Response(503, request=request)

    _mock_http(monkeypatch, handler)
    provider = OpenAICompatibleLLMProvider(Settings(llm_api_key="test-key", llm_max_retries=2))

    with pytest.raises(DependencyUnavailableError):
        provider.generate_bounded(
            system_prompt="system",
            user_prompt="question",
            max_output_tokens=4,
            timeout_seconds=1.0,
        )

    assert len(requests) == 1
    assert requests[0]["max_tokens"] == 4


def test_structured_model_shares_output_quota_with_repair(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        content = "not valid JSON" if len(requests) == 1 else '{"requirements":[{"text":"fact"}]}'
        output_tokens = 3 if len(requests) == 1 else 1
        return httpx.Response(
            200,
            request=request,
            json={
                "model": "recorded-model",
                "choices": [{"message": {"content": content}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": output_tokens},
            },
        )

    _mock_http(monkeypatch, handler)
    model = StructuredAgentModel(
        LLMService(OpenAICompatibleLLMProvider(Settings(llm_api_key="test-key")))
    ).with_call_limits(
        ModelCallLimits(
            remaining_model_calls=2,
            remaining_input_tokens=100_000,
            remaining_output_tokens=4,
            remaining_context_tokens=100_000,
            remaining_cost_micros=1_000_000,
            remaining_active_ms=60_000,
        )
    )

    result = model.plan(PlanModelInput(goal="Find a fact"))

    assert result.value.requirements[0].text == "fact"
    assert result.usage.output_tokens == 4
    assert [request["max_tokens"] for request in requests] == [4, 1]


def test_agent_run_propagates_remaining_budget_before_model_http(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        return httpx.Response(503, request=request)

    _mock_http(monkeypatch, handler)
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        with sessions.begin() as session:
            session.add(KnowledgeSpace(id=1, name="Bounded model", description="test"))
        model = StructuredAgentModel(
            LLMService(OpenAICompatibleLLMProvider(Settings(llm_api_key="test-key", llm_max_retries=2)))
        )
        agent = SqlEvidenceAgent(sessions)
        runner = AgentRunner(
            sessions, lambda _request: EvidenceSearchResult(hits=()), agent_model=model
        )
        opened = agent.submit(
            OpenRun(
                request_id="bounded-real-1",
                space_id=1,
                goal="Find a fact",
                scope=ScopeSelector(),
                deliverable=DeliverableSpec(kind="answer"),
                mode=RunMode.FORCE_AGENT,
                budget=BudgetLimits(
                    max_model_calls=1,
                    max_model_output_tokens=4,
                    max_model_input_tokens=100_000,
                    max_context_tokens=100_000,
                ),
                permissions=PermissionPolicy(read_only=True),
                provider_mode="real",
            )
        )
        for _ in range(2):
            view = agent.inspect(GetRun(opened.run_id))
            assert runner.advance_one(
                opened.run_id,
                expected_version=view.version,
                execution_epoch=view.execution_epoch,
            ).applied

        assert len(requests) == 1
        assert requests[0]["max_tokens"] == 4
        with sessions() as session:
            calls = session.scalars(select(AgentModelCall)).all()
            assert len(calls) == 1
            assert calls[0].retries == 0
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_repair_does_not_send_a_second_request_after_output_quota_is_spent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            request=request,
            json={
                "model": "recorded-model",
                "choices": [{"message": {"content": "not valid JSON"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 4},
            },
        )

    _mock_http(monkeypatch, handler)
    model = StructuredAgentModel(
        LLMService(OpenAICompatibleLLMProvider(Settings(llm_api_key="test-key")))
    ).with_call_limits(
        ModelCallLimits(2, 100_000, 4, 100_000, 1_000_000, 60_000)
    )

    with pytest.raises(AgentModelInvocationError) as caught:
        model.plan(PlanModelInput(goal="Find a fact"))

    assert caught.value.code == "MODEL_BUDGET_EXHAUSTED"
    assert caught.value.usage.output_tokens == 4
    assert len(requests) == 1


def test_final_prompt_input_budget_is_checked_before_any_http(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, request=request)

    _mock_http(monkeypatch, handler)
    model = StructuredAgentModel(
        LLMService(OpenAICompatibleLLMProvider(Settings(llm_api_key="test-key")))
    ).with_call_limits(ModelCallLimits(1, 1, 100, 100, 1_000_000, 60_000))

    with pytest.raises(AgentModelInvocationError) as caught:
        model.plan(PlanModelInput(goal="Short goal"))

    assert caught.value.code == "MODEL_BUDGET_EXHAUSTED"
    assert requests == []


def test_failed_repair_still_accounts_first_response_and_second_http(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if len(requests) == 2:
            return httpx.Response(503, request=request)
        return httpx.Response(
            200,
            request=request,
            json={
                "model": "recorded-model",
                "choices": [{"message": {"content": "invalid JSON"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 2},
            },
        )

    _mock_http(monkeypatch, handler)
    model = StructuredAgentModel(
        LLMService(OpenAICompatibleLLMProvider(Settings(llm_api_key="test-key")))
    ).with_call_limits(ModelCallLimits(2, 100_000, 4, 100_000, 1_000_000, 60_000))

    with pytest.raises(AgentModelInvocationError) as caught:
        model.plan(PlanModelInput(goal="Find a fact"))

    assert len(requests) == 2
    assert caught.value.usage.output_tokens == 2
    assert caught.value.usage.repair_attempts == 1


def test_configured_price_reduces_output_cap_before_http(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        return httpx.Response(
            200,
            request=request,
            json={
                "model": "recorded-model",
                "choices": [{"message": {"content": '{"requirements":[{"text":"fact"}]}'}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 2},
            },
        )

    _mock_http(monkeypatch, handler)
    provider = OpenAICompatibleLLMProvider(
        Settings(
            llm_api_key="test-key",
            llm_input_cost_micros_per_million_tokens=0,
            llm_output_cost_micros_per_million_tokens=10_000_000,
        )
    )
    model = StructuredAgentModel(LLMService(provider)).with_call_limits(
        ModelCallLimits(1, 100_000, 100, 100_000, 25, 60_000)
    )

    result = model.plan(PlanModelInput(goal="Find a fact"))

    assert result.usage.cost_micros == 20
    assert requests[0]["max_tokens"] == 2


def test_remaining_active_time_reduces_transport_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    timeouts: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            request=request,
            json={
                "model": "recorded-model",
                "choices": [{"message": {"content": '{"requirements":[{"text":"fact"}]}'}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 2},
            },
        )

    real_client = httpx.Client
    transport = httpx.MockTransport(handler)

    def client_with_timeout(*, timeout: float) -> httpx.Client:
        timeouts.append(timeout)
        return real_client(transport=transport, timeout=timeout)

    monkeypatch.setattr(provider_module.httpx, "Client", client_with_timeout)
    model = StructuredAgentModel(
        LLMService(OpenAICompatibleLLMProvider(Settings(llm_api_key="test-key")))
    ).with_call_limits(ModelCallLimits(1, 100_000, 100, 100_000, 1_000_000, 250))

    model.plan(PlanModelInput(goal="Find a fact"))

    assert timeouts == [0.25]
