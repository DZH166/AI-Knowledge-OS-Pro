from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.modules.evidence_agent.wiring import get_evidence_agent
from app.services.agent_model import AssessModelInput, RequirementModelContext, SynthesisModelInput


class _RejectUnexpectedSubmit:
    def submit(self, _command: object) -> None:
        raise AssertionError("An overlong goal must be rejected before a run is created")


def test_overlong_goal_is_rejected_before_agent_submission() -> None:
    app.dependency_overrides[get_evidence_agent] = lambda: _RejectUnexpectedSubmit()
    try:
        response = TestClient(app).post(
            "/api/v1/evidence-runs",
            json={
                "schema_version": 1,
                "request_id": "overlong-goal-1",
                "space_id": 1,
                "goal": "a" * 4001,
                "provider_mode": "recording",
            },
        )
        assert response.status_code == 422
        assert any(
            item.get("loc") == ["body", "goal"]
            for item in response.json()["error"]["details"]["errors"]
        )
    finally:
        app.dependency_overrides.pop(get_evidence_agent, None)


def test_existing_long_goals_remain_resumeable_by_model_inputs() -> None:
    requirement = RequirementModelContext(ordinal=1, text="Find evidence", status="uncovered")
    historical_goal = "a" * 12_000
    assert AssessModelInput(
        goal=historical_goal, requirements=[requirement], query_rewrites_remaining=0
    ).goal == historical_goal
    assert SynthesisModelInput(
        goal=historical_goal, title="Result", requirements=[requirement]
    ).goal == historical_goal
