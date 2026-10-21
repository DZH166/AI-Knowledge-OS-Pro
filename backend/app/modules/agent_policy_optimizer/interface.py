from __future__ import annotations

from typing import Protocol, TYPE_CHECKING

from app.modules.agent_policy_optimizer.contracts import (
    CancelStudy,
    ConvertRecommendation,
    ExecuteTrial,
    ExportComparison,
    FailStudy,
    NextRound,
    NextRoundReceipt,
    OptimizerReadResult,
    OptimizerReadQuery,
    RecoverOptimizations,
    RetryTrial,
    RetryReceipt,
    StartStudy,
    StudyCommand,
    StudyMutationReceipt,
    TrialView,
    ConvertDraftReceipt,
    CategoryComparisonView,
    DiffView,
    ExportComparisonReceipt,
    FailReceipt,
    ParetoView,
    RecommendationView,
    StudyCatalogView,
    StudyDetailView,
    StudyEventCatalogView,
    StudyOverviewView,
    StudyTemplateReceipt,
    StudyTemplateCatalogView,
    TrialCatalogView,
)

if TYPE_CHECKING:
    from app.modules.agent_policy_optimizer.executor import TrialExecutor


class AgentPolicyOptimizer(Protocol):
    """Small public surface for the V5.4A-V5.7 retrieval optimizer workbench."""

    def submit(self, command: StudyCommand) -> StudyMutationReceipt: ...

    def inspect(self, query: OptimizerReadQuery) -> OptimizerReadResult: ...

    def execute(self, command: ExecuteTrial, executor: "TrialExecutor") -> TrialView: ...

    def start(self, study_id: str) -> StudyMutationReceipt: ...

    def cancel(self, study_id: str) -> StudyMutationReceipt: ...

    def recover(self, command: RecoverOptimizations) -> int: ...

    def convert_to_draft(self, command: ConvertRecommendation) -> ConvertDraftReceipt: ...

    def retry_trial(self, command: RetryTrial) -> RetryReceipt: ...

    def fail_study(self, command: FailStudy) -> FailReceipt: ...

    def start_next_round(self, command: NextRound) -> NextRoundReceipt: ...

    def inspect_study(self, study_id: str) -> StudyDetailView: ...

    def inspect_trial(self, trial_id: str) -> TrialView: ...

    def inspect_pareto(self, study_id: str) -> ParetoView: ...

    def inspect_recommendation(self, study_id: str) -> RecommendationView: ...

    def inspect_categories(self, study_id: str, trial_id: str) -> CategoryComparisonView: ...

    def diff_trial_against_active(self, study_id: str, trial_id: str) -> DiffView: ...

    def list_studies(self, *, limit: int, status: str | None = None) -> StudyCatalogView: ...

    def list_trials(
        self, study_id: str, *, limit: int, status: str | None = None
    ) -> TrialCatalogView: ...

    def inspect_overview(self, study_id: str) -> StudyOverviewView: ...

    def list_templates(self) -> StudyTemplateCatalogView: ...

    def create_from_template(
        self,
        *,
        request_id: str,
        label: str,
        base_policy_id: str,
        template_key: str,
        seed: int | None,
        max_candidates: int | None,
        max_evaluations: int | None,
        warm_start_study_id: str | None,
    ) -> StudyTemplateReceipt: ...

    def inspect_events(
        self, study_id: str, *, limit: int = 100, after: str | None = None
    ) -> StudyEventCatalogView: ...

    def export_comparison(self, command: ExportComparison) -> ExportComparisonReceipt: ...


__all__ = [
    "AgentPolicyOptimizer",
    "NextRound",
    "ConvertRecommendation",
    "ExportComparison",
    "FailStudy",
    "RetryTrial",
    "CancelStudy",
    "ExecuteTrial",
    "RecoverOptimizations",
    "StartStudy",
    "StudyCommand",
]
