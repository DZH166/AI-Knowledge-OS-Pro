from __future__ import annotations

from app.services.agent_model import (
    AssessModelInput,
    PlanModelInput,
    StructuredAgentModel,
    SynthesisModelInput,
    RouteModelInput,
)
from app.services.llm_service import LLMService
from app.services.providers import LLMProvider, LLMResult


class _CapturingProvider(LLMProvider):
    name = "capturing"

    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)
        self.system_prompts: list[str] = []

    @property
    def model(self) -> str:
        return "capturing-v1"

    def is_configured(self) -> bool:
        return True

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        return self.generate(system_prompt=system_prompt, user_prompt=user_prompt).text

    def generate(self, *, system_prompt: str, user_prompt: str) -> LLMResult:
        self.system_prompts.append(system_prompt)
        return LLMResult(
            text=self.responses.pop(0),
            provider=self.name,
            model=self.model,
            input_tokens=10,
            output_tokens=5,
            retries=0,
            latency_ms=1,
            cost_micros=0,
            estimated_usage=False,
        )


def test_agent_prompts_keep_goal_language_for_plan_assess_and_synthesis() -> None:
    provider = _CapturingProvider([
        '{"mode":"force_agent","rationale":"multi-source"}',
        '{"requirements":[{"text":"比较部署成本","kind":"comparative","priority":"must"}],"rationale":"cost"}',
        (
            '{"decision":"answer","reason":"covered","evidence_selections":'
            '[{"requirement_ordinal":1,"supporting_evidence_ids":["ev-1"]}]}'
        ),
        (
            '{"claims":[{"requirement_ordinal":1,"text":"方案 A 的部署成本更低。"}],'
            '"summary":"成本对比完成"}'
        ),
    ])
    model = StructuredAgentModel(LLMService(provider))

    model.route(RouteModelInput(goal="比较三个方案的部署成本", source_count=3))
    model.plan(PlanModelInput(goal="比较三个方案的部署成本", max_requirements=3))
    model.assess(AssessModelInput(
        goal="比较三个方案的部署成本",
        requirements=[{
            "ordinal": 1,
            "text": "比较部署成本",
            "status": "covered",
            "evidence": [{"evidence_id": "ev-1", "excerpt": "方案 A 成本更低", "relation": "supports"}],
        }],
        query_rewrites_remaining=1,
    ))
    model.synthesize(SynthesisModelInput(
        goal="比较三个方案的部署成本",
        title="成本对比",
        requirements=[{
            "ordinal": 1,
            "text": "比较部署成本",
            "status": "covered",
            "evidence": [{"evidence_id": "ev-1", "excerpt": "方案 A 成本更低", "relation": "supports"}],
        }],
    ))

    for prompt in provider.system_prompts[1:]:
        assert "same language as the" in prompt and "goal" in prompt
