from __future__ import annotations

from dataclasses import dataclass, replace
import json
import re
from typing import Generic, TypeVar

from pydantic import BaseModel, ValidationError

from app.core.errors import ServiceError
from app.services.providers import CostStatus, LLMProvider, LLMResult, get_llm_provider


SchemaT = TypeVar("SchemaT", bound=BaseModel)


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
    ) -> StructuredGeneration[SchemaT]:
        """Generate schema-validated JSON with one bounded repair attempt."""

        results: list[LLMResult] = []
        schema_json = json.dumps(schema.model_json_schema(), ensure_ascii=False, separators=(",", ":"))
        first_system_prompt = (
            f"{system_prompt}\nReturn JSON only. It must satisfy this JSON Schema: {schema_json}"
        )
        first = self.provider.generate(
            system_prompt=first_system_prompt,
            user_prompt=user_prompt,
        )
        first = self._with_estimated_usage(
            first,
            system_prompt=first_system_prompt,
            user_prompt=user_prompt,
        )
        results.append(first)
        parsed = self._validate_json(first.text, schema)
        repaired = False

        if parsed is None and allow_repair:
            repaired = True
            repair_system_prompt = (
                "Repair the candidate into JSON only. Do not add facts. "
                f"It must satisfy this JSON Schema: {schema_json}"
            )
            repair_user_prompt = f"Candidate:\n{first.text}"
            second = self.provider.generate(
                system_prompt=repair_system_prompt,
                user_prompt=repair_user_prompt,
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
