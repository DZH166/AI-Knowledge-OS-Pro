from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from typing import Literal, Mapping

from app.modules.evidence_agent.contracts import BudgetLimits


@dataclass(frozen=True, slots=True)
class BudgetUsage:
    steps: int = 0
    tool_calls: int = 0
    model_calls: int = 0
    model_input_tokens: int = 0
    model_output_tokens: int = 0
    cost_micros: int = 0
    cost_reported_calls: int = 0
    cost_estimated_calls: int = 0
    cost_unknown_calls: int = 0
    active_ms: int = 0
    no_new_evidence_rounds: int = 0
    query_rewrites: int = 0
    evidence_records: int = 0
    context_tokens: int = 0

    @classmethod
    def from_mapping(cls, value: Mapping[str, int]) -> "BudgetUsage":
        known = {name: int(value.get(name, 0)) for name in cls.__dataclass_fields__}
        return cls(**known)

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


class BudgetExceeded(RuntimeError):
    def __init__(self, reason: str, *, usage: BudgetUsage | None = None) -> None:
        super().__init__(f"Agent budget exhausted: {reason}")
        self.reason = reason
        self.usage = usage


class BudgetController:
    """Deterministic hard-stop policy evaluated before every external call."""

    def __init__(self, limits: BudgetLimits) -> None:
        self.limits = limits

    def reserve_tool(self, usage: BudgetUsage) -> BudgetUsage:
        proposed = replace(usage, steps=usage.steps + 1, tool_calls=usage.tool_calls + 1)
        self._check(proposed)
        return proposed

    def reserve_model(
        self,
        usage: BudgetUsage,
        *,
        input_tokens: int,
        output_tokens: int,
        cost_micros: int,
    ) -> BudgetUsage:
        reserved = self.reserve_model_call(usage)
        return self.record_model_usage(
            reserved,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_micros=cost_micros,
        )

    def reserve_model_call(self, usage: BudgetUsage) -> BudgetUsage:
        proposed = replace(
            usage,
            steps=usage.steps + 1,
            model_calls=usage.model_calls + 1,
        )
        self._check(proposed)
        return proposed

    def record_model_usage(
        self,
        usage: BudgetUsage,
        *,
        input_tokens: int,
        output_tokens: int,
        cost_micros: int | None,
        cost_status: Literal["reported", "estimated", "unknown"] | None = None,
        active_ms: int = 0,
        additional_model_calls: int = 0,
    ) -> BudgetUsage:
        normalized_cost_status = cost_status or (
            "unknown" if cost_micros is None else "reported"
        )
        if cost_micros is None and normalized_cost_status != "unknown":
            raise ValueError("Known or estimated cost requires cost_micros.")
        if cost_micros is not None and cost_micros < 0:
            raise ValueError("Model cost cannot be negative.")
        proposed = replace(
            usage,
            steps=usage.steps + max(0, additional_model_calls),
            model_calls=usage.model_calls + max(0, additional_model_calls),
            model_input_tokens=usage.model_input_tokens + max(0, input_tokens),
            model_output_tokens=usage.model_output_tokens + max(0, output_tokens),
            cost_micros=usage.cost_micros + (cost_micros or 0),
            cost_reported_calls=(
                usage.cost_reported_calls
                + (1 if normalized_cost_status == "reported" else 0)
            ),
            cost_estimated_calls=(
                usage.cost_estimated_calls
                + (1 if normalized_cost_status == "estimated" else 0)
            ),
            cost_unknown_calls=(
                usage.cost_unknown_calls
                + (1 if normalized_cost_status == "unknown" else 0)
            ),
            active_ms=usage.active_ms + max(0, active_ms),
            context_tokens=usage.context_tokens + max(0, input_tokens),
        )
        self._check(proposed)
        return proposed

    def add_active_time(self, usage: BudgetUsage, elapsed_ms: int) -> BudgetUsage:
        proposed = replace(usage, active_ms=usage.active_ms + max(0, elapsed_ms))
        self._check(proposed)
        return proposed

    def record_query_rewrite(self, usage: BudgetUsage) -> BudgetUsage:
        proposed = replace(usage, query_rewrites=usage.query_rewrites + 1)
        self._check(proposed)
        return proposed

    def record_evidence(self, usage: BudgetUsage, *, new_records: int) -> BudgetUsage:
        if new_records > 0:
            proposed = replace(
                usage,
                evidence_records=usage.evidence_records + new_records,
                no_new_evidence_rounds=0,
            )
        else:
            proposed = replace(usage, no_new_evidence_rounds=usage.no_new_evidence_rounds + 1)
        self._check(proposed)
        return proposed

    def _check(self, usage: BudgetUsage) -> None:
        ordered_limits = (
            ("max_active_ms", usage.active_ms, self.limits.max_active_ms),
            ("max_cost_micros", usage.cost_micros, self.limits.max_cost_micros),
            ("max_model_input_tokens", usage.model_input_tokens, self.limits.max_model_input_tokens),
            ("max_model_output_tokens", usage.model_output_tokens, self.limits.max_model_output_tokens),
            ("max_steps", usage.steps, self.limits.max_steps),
            ("max_tool_calls", usage.tool_calls, self.limits.max_tool_calls),
            ("max_model_calls", usage.model_calls, self.limits.max_model_calls),
            (
                "max_no_new_evidence_rounds",
                usage.no_new_evidence_rounds,
                self.limits.max_no_new_evidence_rounds - 1,
            ),
            ("max_query_rewrites", usage.query_rewrites, self.limits.max_query_rewrites),
            ("max_evidence_records", usage.evidence_records, self.limits.max_evidence_records),
            ("max_context_tokens", usage.context_tokens, self.limits.max_context_tokens),
        )
        for reason, value, limit in ordered_limits:
            if value > limit:
                raise BudgetExceeded(reason, usage=usage)
