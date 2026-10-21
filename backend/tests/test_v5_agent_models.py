from __future__ import annotations

from dataclasses import FrozenInstanceError

from pydantic import BaseModel
import pytest

from app.core.errors import ServiceError
from app.modules.evidence_agent.contracts import EvidenceRef, RunMode, RunPhase, RunStatus
from app.modules.evidence_agent.budget import BudgetController, BudgetExceeded, BudgetUsage
from app.modules.evidence_agent.contracts import BudgetLimits
from app.modules.evidence_agent.state_machine import InvalidRunTransition, RunSignal, transition_run
from app.services.llm_service import LLMService
from app.services.providers import LLMProvider, LLMResult


class PlanProposal(BaseModel):
    objective: str
    requirements: list[str]


class RecordingProvider(LLMProvider):
    name = "recording"

    def __init__(self, responses: list[LLMResult]) -> None:
        self.responses = list(responses)
        self.calls = 0

    @property
    def model(self) -> str:
        return "recording-v1"

    def is_configured(self) -> bool:
        return True

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        return self.generate(system_prompt=system_prompt, user_prompt=user_prompt).text

    def generate(self, *, system_prompt: str, user_prompt: str) -> LLMResult:
        self.calls += 1
        return self.responses.pop(0)


def _result(text: str, *, input_tokens: int = 10, output_tokens: int = 5) -> LLMResult:
    return LLMResult(
        text=text,
        provider="recording",
        model="recording-v1",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        retries=0,
        latency_ms=3,
        cost_micros=7,
        estimated_usage=False,
    )


def test_structured_generation_repairs_once_and_preserves_usage() -> None:
    provider = RecordingProvider(
        [
            _result("not-json", input_tokens=11, output_tokens=2),
            _result('{"objective":"比较方案","requirements":["成本","证据"]}', input_tokens=13, output_tokens=8),
        ]
    )
    service = LLMService(provider)

    generated = service.generate_structured(
        system_prompt="Return a plan.",
        user_prompt="比较两个有证据的方案",
        schema=PlanProposal,
    )

    assert generated.value.objective == "比较方案"
    assert generated.value.requirements == ["成本", "证据"]
    assert generated.usage.input_tokens == 24
    assert generated.usage.output_tokens == 10
    assert generated.usage.cost_micros == 14
    assert generated.repaired is True
    assert provider.calls == 2


def test_structured_generation_fails_explicitly_after_one_repair() -> None:
    provider = RecordingProvider([_result("bad"), _result('{"unknown":true}')])

    with pytest.raises(ServiceError) as raised:
        LLMService(provider).generate_structured(
            system_prompt="Return a plan.",
            user_prompt="goal",
            schema=PlanProposal,
        )

    assert raised.value.code == "MODEL_OUTPUT_INVALID"
    assert provider.calls == 2


def test_evidence_reference_is_immutable_and_revision_complete() -> None:
    evidence = EvidenceRef(
        source_id=3,
        revision_id=7,
        index_revision_id=9,
        chunk_id=11,
        content_hash="a" * 64,
        locator={"kind": "pdf_page", "page": 4},
    )

    assert evidence.revision_id == 7
    with pytest.raises(FrozenInstanceError):
        evidence.chunk_id = 12  # type: ignore[misc]


@pytest.mark.parametrize(
    ("status", "signal", "expected"),
    [
        (RunStatus.QUEUED, RunSignal.DISPATCH, RunStatus.ROUTING),
        (RunStatus.ROUTING, RunSignal.SELECT_QUICK, RunStatus.RUNNING),
        (RunStatus.ROUTING, RunSignal.SELECT_AGENT, RunStatus.PLANNED),
        (RunStatus.PLANNED, RunSignal.EXECUTE, RunStatus.RUNNING),
        (RunStatus.RUNNING, RunSignal.NEED_INPUT, RunStatus.AWAITING_INPUT),
        (RunStatus.AWAITING_INPUT, RunSignal.PROVIDE_INPUT, RunStatus.QUEUED),
        (RunStatus.RUNNING, RunSignal.NEED_APPROVAL, RunStatus.AWAITING_APPROVAL),
        (RunStatus.AWAITING_APPROVAL, RunSignal.APPROVE, RunStatus.QUEUED),
        (RunStatus.RUNNING, RunSignal.PAUSE, RunStatus.PAUSED),
        (RunStatus.PAUSED, RunSignal.RESUME, RunStatus.QUEUED),
        (RunStatus.RUNNING, RunSignal.COMPLETE, RunStatus.COMPLETED),
        (RunStatus.RUNNING, RunSignal.INSUFFICIENT, RunStatus.INSUFFICIENT_EVIDENCE),
    ],
)
def test_agent_state_machine_has_explicit_legal_transitions(
    status: RunStatus,
    signal: RunSignal,
    expected: RunStatus,
) -> None:
    assert transition_run(status, signal) is expected


def test_terminal_run_rejects_further_transitions() -> None:
    for status in (
        RunStatus.COMPLETED,
        RunStatus.INSUFFICIENT_EVIDENCE,
        RunStatus.CANCELLED,
        RunStatus.FAILED,
    ):
        with pytest.raises(InvalidRunTransition):
            transition_run(status, RunSignal.CANCEL)


def test_run_modes_and_phases_do_not_explode_status_space() -> None:
    assert {mode.value for mode in RunMode} == {"auto", "force_quick", "force_agent"}
    assert RunPhase.RETRIEVE.value == "retrieve"
    assert "retrieving" not in {status.value for status in RunStatus}


def test_budget_controller_enforces_limits_before_external_calls() -> None:
    limits = BudgetLimits(
        max_steps=2,
        max_tool_calls=1,
        max_model_calls=1,
        max_model_input_tokens=10,
        max_model_output_tokens=5,
        max_cost_micros=100,
        max_active_ms=1_000,
        max_no_new_evidence_rounds=2,
        max_query_rewrites=1,
        max_evidence_records=3,
        max_context_tokens=20,
    )
    controller = BudgetController(limits)
    usage = controller.reserve_tool(BudgetUsage())

    with pytest.raises(BudgetExceeded) as tool_limit:
        controller.reserve_tool(usage)
    assert tool_limit.value.reason == "max_tool_calls"

    usage = controller.reserve_model(usage, input_tokens=8, output_tokens=4, cost_micros=90)
    with pytest.raises(BudgetExceeded) as token_limit:
        controller.reserve_model(usage, input_tokens=3, output_tokens=1, cost_micros=1)
    assert token_limit.value.reason in {
        "max_steps",
        "max_model_calls",
        "max_model_input_tokens",
    }


def test_no_new_evidence_counter_resets_only_when_new_identity_is_added() -> None:
    limits = BudgetLimits(max_no_new_evidence_rounds=2)
    controller = BudgetController(limits)
    usage = controller.record_evidence(BudgetUsage(), new_records=0)
    assert usage.no_new_evidence_rounds == 1

    with pytest.raises(BudgetExceeded) as stopped:
        controller.record_evidence(usage, new_records=0)
    assert stopped.value.reason == "max_no_new_evidence_rounds"

    reset = controller.record_evidence(usage, new_records=2)
    assert reset.no_new_evidence_rounds == 0
    assert reset.evidence_records == 2
