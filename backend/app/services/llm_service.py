from __future__ import annotations

from dataclasses import dataclass, replace
import json
import re
from typing import Generic, TypeVar

from pydantic import BaseModel, ValidationError

from app.core.errors import ServiceError
from app.services.providers import CostStatus, LLMProvider, LLMResult, OpenAICompatibleLLMProvider, get_llm_provider


SchemaT = TypeVar("SchemaT", bound=BaseModel)


@dataclass(frozen=True, slots=True)
class ModelCallLimits:
    """Remaining run allowance before an Agent's next external model request."""

    remaining_model_calls: int
    remaining_input_tokens: int
    remaining_output_tokens: int
    remaining_context_tokens: int
    remaining_cost_micros: int
    remaining_active_ms: int


@dataclass(frozen=True, slots=True)
class LLMUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    retries: int = 0
    latency_ms: int = 0
    cost_micros: int | None = None
    cost_status: CostStatus = "unknown"
    estimated: bool = False

    @classmethod
    def from_results(cls, results: list[LLMResult]) -> "LLMUsage":
        cost_statuses = {item.cost_status for item in results}
        cost_status: CostStatus
        if "unknown" in cost_statuses:
            cost_status = "unknown"
        elif "estimated" in cost_statuses:
            cost_status = "estimated"
        else:
            cost_status = "reported"
        return cls(
            input_tokens=sum(item.input_tokens for item in results),
            output_tokens=sum(item.output_tokens for item in results),
            retries=sum(item.retries for item in results),
            latency_ms=sum(item.latency_ms for item in results),
            cost_micros=(
                sum(item.cost_micros for item in results if item.cost_micros is not None)
                if cost_status != "unknown"
                else None
            ),
            cost_status=cost_status,
            estimated=any(item.estimated_usage for item in results),
        )


@dataclass(frozen=True, slots=True)
class StructuredGeneration(Generic[SchemaT]):
    value: SchemaT
    usage: LLMUsage
    repaired: bool
    provider: str
    model: str


class LLMService:
    def __init__(self, provider: LLMProvider | None = None) -> None:
        self.provider = provider or get_llm_provider()

    def is_configured(self) -> bool:
        return self.provider.is_configured()

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        return self.provider.complete(system_prompt=system_prompt, user_prompt=user_prompt)

    def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: type[SchemaT],
        allow_repair: bool = True,
        call_limits: ModelCallLimits | None = None,
    ) -> StructuredGeneration[SchemaT]:
        """Generate schema-validated JSON with one bounded repair attempt."""

        results: list[LLMResult] = []
        schema_json = json.dumps(schema.model_json_schema(), ensure_ascii=False, separators=(",", ":"))
        first_system_prompt = (
            f"{system_prompt}\nReturn JSON only. It must satisfy this JSON Schema: {schema_json}"
        )
        first = self._generate_with_limits(
            system_prompt=first_system_prompt,
            user_prompt=user_prompt,
            call_limits=call_limits,
            previous_results=results,
        )
        first = self._with_estimated_usage(
            first,
            system_prompt=first_system_prompt,
            user_prompt=user_prompt,
        )
        results.append(first)
        parsed = self._validate_json(first.text, schema)
        repaired = False

        if parsed is None and allow_repair and (
            call_limits is None or call_limits.remaining_model_calls > 1
        ):
            repaired = True
            repair_system_prompt = (
                "Repair the candidate into JSON only. Do not add facts. "
                f"It must satisfy this JSON Schema: {schema_json}"
            )
            repair_user_prompt = f"Candidate:\n{first.text}"
            second = self._generate_with_limits(
                system_prompt=repair_system_prompt,
                user_prompt=repair_user_prompt,
                call_limits=call_limits,
                previous_results=results,
            )
            second = self._with_estimated_usage(
                second,
                system_prompt=repair_system_prompt,
                user_prompt=repair_user_prompt,
            )
            results.append(second)
            parsed = self._validate_json(second.text, schema)

        if parsed is None:
            usage = LLMUsage.from_results(results)
            raise ServiceError(
                code="MODEL_OUTPUT_INVALID",
                message="The model returned invalid structured output within the allowed attempts.",
                user_message="模型输出无法通过结构校验，本次运行已安全停止。",
                status_code=502,
                details={
                    "schema": schema.__name__,
                    "attempts": len(results),
                    "repair_attempts": max(0, len(results) - 1),
                    "input_tokens": usage.input_tokens,
                    "output_tokens": usage.output_tokens,
                    "cost_micros": usage.cost_micros,
                    "cost_status": usage.cost_status,
                    "latency_ms": usage.latency_ms,
                    "provider_retries": usage.retries,
                    "estimated": usage.estimated,
                    "provider": results[-1].provider,
                    "model": results[-1].model,
                },
                retryable=False,
            )

        last = results[-1]
        return StructuredGeneration(
            value=parsed,
            usage=LLMUsage.from_results(results),
            repaired=repaired,
            provider=last.provider,
            model=last.model,
        )

    def _generate_with_limits(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        call_limits: ModelCallLimits | None,
        previous_results: list[LLMResult],
    ) -> LLMResult:
        if call_limits is None or not isinstance(self.provider, OpenAICompatibleLLMProvider):
            return self.provider.generate(system_prompt=system_prompt, user_prompt=user_prompt)

        used = LLMUsage.from_results(previous_results) if previous_results else LLMUsage()
        remaining_calls = call_limits.remaining_model_calls - len(previous_results)
        remaining_input = call_limits.remaining_input_tokens - used.input_tokens
        remaining_context = call_limits.remaining_context_tokens - used.input_tokens
        remaining_output = call_limits.remaining_output_tokens - used.output_tokens
        remaining_active_ms = call_limits.remaining_active_ms - used.latency_ms
        remaining_cost = call_limits.remaining_cost_micros - (used.cost_micros or 0)
        estimated_input = self._estimate_tokens(f"{system_prompt}\n{user_prompt}")

        reason = None
        if remaining_calls < 1:
            reason = "max_model_calls"
        elif estimated_input > remaining_input:
            reason = "max_model_input_tokens"
        elif estimated_input > remaining_context:
            reason = "max_context_tokens"
        elif remaining_output < 1:
            reason = "max_model_output_tokens"
        elif remaining_active_ms < 1:
            reason = "max_active_ms"
        elif remaining_cost < 1:
            reason = "max_cost_micros"
        if reason is not None:
            self._raise_bounded_failure(reason, previous_results)

        max_output = remaining_output
        input_price = self.provider.config.llm_input_cost_micros_per_million_tokens
        output_price = self.provider.config.llm_output_cost_micros_per_million_tokens
        if input_price is not None and output_price is not None:
            estimated_input_cost = (estimated_input * input_price + 999_999) // 1_000_000
            if estimated_input_cost >= remaining_cost:
                self._raise_bounded_failure("max_cost_micros", previous_results)
            if output_price > 0:
                affordable_output = (remaining_cost - estimated_input_cost) * 1_000_000 // output_price
                max_output = min(max_output, affordable_output)
                if max_output < 1:
                    self._raise_bounded_failure("max_cost_micros", previous_results)

        try:
            return self.provider.generate_bounded(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_output_tokens=max_output,
                timeout_seconds=remaining_active_ms / 1_000,
            )
        except ServiceError as exc:
            # A failed repair is still a second external attempt. Preserve the
            # first response's observed usage even though the repair has none.
            raise ServiceError(
                code=exc.code,
                message=exc.message,
                user_message=exc.user_message,
                status_code=exc.status_code,
                details={
                    **(exc.details or {}),
                    "input_tokens": used.input_tokens,
                    "output_tokens": used.output_tokens,
                    # The failed HTTP may itself be billable, so the aggregate
                    # cost is unknown even when earlier responses had prices.
                    "cost_micros": None,
                    "cost_status": "unknown",
                    "observed_cost_micros": used.cost_micros if previous_results else None,
                    "latency_ms": used.latency_ms,
                    "provider_retries": used.retries,
                    "repair_attempts": len(previous_results),
                    "estimated": used.estimated,
                },
                retryable=exc.retryable,
            ) from exc

    @staticmethod
    def _raise_bounded_failure(reason: str, results: list[LLMResult]) -> None:
        usage = LLMUsage.from_results(results) if results else LLMUsage()
        raise ServiceError(
            code="MODEL_BUDGET_EXHAUSTED",
            message=f"Model invocation stopped before an external request: {reason}.",
            user_message="本次模型调用的剩余额度不足，已在发送请求前停止。",
            status_code=409,
            details={
                "reason": reason,
                "input_tokens": usage.input_tokens,
                "output_tokens": usage.output_tokens,
                "cost_micros": usage.cost_micros,
                "cost_status": usage.cost_status,
                "latency_ms": usage.latency_ms,
                "provider_retries": usage.retries,
                "repair_attempts": max(0, len(results) - 1),
                "estimated": usage.estimated,
            },
            retryable=False,
        )

    @staticmethod
    def _validate_json(text: str, schema: type[SchemaT]) -> SchemaT | None:
        candidate = text.strip()
        if candidate.startswith("```"):
            lines = candidate.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            candidate = "\n".join(lines).strip()
        try:
            return schema.model_validate_json(candidate)
        except (ValidationError, ValueError):
            return None

    @classmethod
    def _with_estimated_usage(
        cls,
        result: LLMResult,
        *,
        system_prompt: str,
        user_prompt: str,
    ) -> LLMResult:
        if not result.estimated_usage:
            return result
        return replace(
            result,
            input_tokens=(
                result.input_tokens
                or cls._estimate_tokens(f"{system_prompt}\n{user_prompt}")
            ),
            output_tokens=result.output_tokens or cls._estimate_tokens(result.text),
        )

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        cjk_characters = len(re.findall(r"[\u3400-\u9fff]", text))
        other_characters = max(0, len(text) - cjk_characters)
        return max(1, cjk_characters + (other_characters + 3) // 4)
