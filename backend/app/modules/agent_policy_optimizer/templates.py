"""Built-in optimization study templates for one-click study creation.

Pure module: database, queue, and web framework imports are forbidden here.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.modules.agent_policy_optimizer.contracts import (
    OptimizerInputError,
    ScoreWeights,
    SearchSpace,
    SearchSpaceBound,
    StudyCommand,
    StudyObjective,
)


@dataclass(frozen=True, slots=True)
class StudyTemplate:
    key: str
    description: str
    objective: StudyObjective
    search_space: SearchSpace
    weights: ScoreWeights
    max_candidates: int
    max_evaluations: int
    seed: int

    def catalog_payload(self) -> dict[str, object]:
        return {
            "key": self.key,
            "description": self.description,
            "objective": self.objective.value,
            "max_candidates": self.max_candidates,
            "max_evaluations": self.max_evaluations,
            "seed": self.seed,
            "search_space": {
                name: {
                    "minimum": getattr(self.search_space, name).minimum,
                    "maximum": getattr(self.search_space, name).maximum,
                }
                for name in (
                    "factual_top_k",
                    "comparative_top_k",
                    "temporal_top_k",
                    "minimum_score_millis",
                    "max_hits_per_source",
                    "neighbor_before",
                    "neighbor_after",
                )
            },
            "weights": {
                "quality_weight_permille": self.weights.quality_weight_permille,
                "cost_weight_permille": self.weights.cost_weight_permille,
            },
        }


_WIDE_SPACE = SearchSpace(
    factual_top_k=SearchSpaceBound(2, 24),
    comparative_top_k=SearchSpaceBound(4, 30),
    temporal_top_k=SearchSpaceBound(2, 24),
    minimum_score_millis=SearchSpaceBound(0, 300),
    max_hits_per_source=SearchSpaceBound(1, 8),
    neighbor_before=SearchSpaceBound(0, 3),
    neighbor_after=SearchSpaceBound(0, 3),
)
_BALANCED_SPACE = SearchSpace(
    factual_top_k=SearchSpaceBound(4, 16),
    comparative_top_k=SearchSpaceBound(6, 20),
    temporal_top_k=SearchSpaceBound(4, 18),
    minimum_score_millis=SearchSpaceBound(0, 200),
    max_hits_per_source=SearchSpaceBound(1, 6),
    neighbor_before=SearchSpaceBound(0, 2),
    neighbor_after=SearchSpaceBound(0, 2),
)
_LEAN_SPACE = SearchSpace(
    factual_top_k=SearchSpaceBound(2, 8),
    comparative_top_k=SearchSpaceBound(4, 12),
    temporal_top_k=SearchSpaceBound(2, 8),
    minimum_score_millis=SearchSpaceBound(0, 100),
    max_hits_per_source=SearchSpaceBound(1, 4),
    neighbor_before=SearchSpaceBound(0, 1),
    neighbor_after=SearchSpaceBound(0, 1),
)

STUDY_TEMPLATES: dict[str, StudyTemplate] = {
    "quality_first": StudyTemplate(
        key="quality_first",
        description="Maximize evidence quality with a wide retrieval window.",
        objective=StudyObjective.QUALITY_FIRST,
        search_space=_WIDE_SPACE,
        weights=ScoreWeights(quality_weight_permille=700, cost_weight_permille=300),
        max_candidates=4,
        max_evaluations=8,
        seed=42,
    ),
    "balanced": StudyTemplate(
        key="balanced",
        description="Balance quality and latency around the current defaults.",
        objective=StudyObjective.BALANCED,
        search_space=_BALANCED_SPACE,
        weights=ScoreWeights(quality_weight_permille=700, cost_weight_permille=300),
        max_candidates=4,
        max_evaluations=8,
        seed=42,
    ),
    "cost_first": StudyTemplate(
        key="cost_first",
        description="Shrink the retrieval window and latency while keeping quality gates.",
        objective=StudyObjective.COST_FIRST,
        search_space=_LEAN_SPACE,
        weights=ScoreWeights(quality_weight_permille=300, cost_weight_permille=700),
        max_candidates=4,
        max_evaluations=8,
        seed=42,
    ),
}


def template_command(
    *,
    request_id: str,
    label: str,
    base_policy_id: str,
    template_key: str,
    seed: int | None,
    max_candidates: int | None,
    max_evaluations: int | None,
    warm_start_study_id: str | None,
) -> StudyCommand:
    """Build a StudyCommand from a template, applying optional overrides."""

    template = STUDY_TEMPLATES.get(template_key)
    if template is None:
        raise OptimizerInputError(
            "OPTIMIZER_TEMPLATE_NOT_FOUND",
            f"Unknown study template: {template_key}.",
        )
    effective_seed = template.seed if seed is None else seed
    effective_candidates = template.max_candidates if max_candidates is None else max_candidates
    effective_evaluations = template.max_evaluations if max_evaluations is None else max_evaluations
    if effective_candidates > template.max_candidates or effective_evaluations > template.max_evaluations:
        raise OptimizerInputError(
            "OPTIMIZER_TEMPLATE_OVERRIDE_EXPANDS_BUDGET",
            "Template overrides may narrow, but never expand, the built-in budget.",
        )
    return StudyCommand(
        request_id=request_id,
        label=label,
        base_policy_id=base_policy_id,
        objective=template.objective,
        max_candidates=effective_candidates,
        max_evaluations=effective_evaluations,
        search_space=template.search_space,
        weights=template.weights,
        seed=effective_seed,
        warm_start_study_id=warm_start_study_id,
    )


__all__ = ["STUDY_TEMPLATES", "StudyTemplate", "template_command"]
