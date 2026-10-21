from __future__ import annotations

from app.core.config import settings
from app.core.errors import ConfigurationError
from app.db.session import SessionLocal
from app.modules.evidence_agent.controller import AgentRunner
from app.modules.evidence_agent.interface import EvidenceAgent
from app.modules.evidence_agent.search_adapter import HybridAgentSearch, SqlAgentEvidenceQuery
from app.modules.evidence_agent.service import SqlEvidenceAgent
from app.services.agent_model import DeterministicAgentModel, StructuredAgentModel
from app.services.llm_service import LLMService


_evidence_agent = SqlEvidenceAgent(SessionLocal)
_search_evidence = HybridAgentSearch(SessionLocal)
_query_evidence = SqlAgentEvidenceQuery(SessionLocal)


_llm_service = LLMService()
_agent_model = (
    StructuredAgentModel(_llm_service)
    if _llm_service.is_configured() and not settings.demo_mode
    else None
)
_deterministic_model = DeterministicAgentModel()
_agent_runner = AgentRunner(
    SessionLocal,
    _search_evidence,
    evidence_query=_query_evidence,
    agent_model=_agent_model,
    agent_models={"real": _agent_model, "demo": _deterministic_model, "recording": _deterministic_model},
    claim_lease_seconds=(
        settings.task_timeout_seconds + settings.task_heartbeat_timeout_seconds
    ),
)


def get_evidence_agent() -> EvidenceAgent:
    return _evidence_agent


def get_agent_runner() -> AgentRunner:
    return _agent_runner


def ensure_agent_provider_available(provider_mode: str) -> None:
    """Keep a real run from silently using the deterministic fallback policy."""

    if provider_mode not in {"real", "demo", "recording"}:
        raise ConfigurationError(
            "Unknown Evidence Agent provider mode.",
            code="PROVIDER_MODE_INVALID",
        )
    if provider_mode == "real" and _agent_model is None:
        raise ConfigurationError(
            "Real Evidence Agent mode requires a configured LLM provider.",
            code="LLM_NOT_CONFIGURED",
        )
