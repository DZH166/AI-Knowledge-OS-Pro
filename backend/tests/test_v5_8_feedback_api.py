from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.db.session import Base, create_database_engine
from app.main import app
from app.models.agent_evidence import AgentArtifact, AgentClaim
from app.models.agent_run import AgentRun
from app.models.knowledge_space import KnowledgeSpace
from app.modules.feedback.wiring import get_feedback
from app.modules.feedback.service import SqlFeedback


@pytest.fixture()
def feedback_api(tmp_path):
    engine = create_database_engine(f"sqlite:///{(tmp_path / 'feedback.db').as_posix()}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory.begin() as session:
        session.add(KnowledgeSpace(id=1, name="Feedback lab", description="synthetic test"))
    with factory.begin() as session:
        session.add(AgentRun(
            id="run-feedback", space_id=1, goal="Explain the retrieval trade-off", requested_mode="force_agent",
            effective_mode="force_agent", status="completed", phase="done", provider_mode="demo",
            scope_snapshot_json='{"sources":[]}', scope_digest="a" * 64,
            final_artifact_id="artifact-feedback", version=9,
        ))
    with factory.begin() as session:
        session.add(AgentArtifact(id="artifact-feedback", producing_run_id="run-feedback", kind="answer",
                                  title="Retrieval comparison", body_markdown="Original answer", status="final"))
    with factory.begin() as session:
        session.add(AgentClaim(id="claim-feedback", artifact_id="artifact-feedback", ordinal=1,
                               text="Original claim", kind="factual", verification_status="supported"))
    app.dependency_overrides[get_feedback] = lambda: SqlFeedback(factory)
    try:
        yield TestClient(app, raise_server_exceptions=False), factory
    finally:
        app.dependency_overrides.pop(get_feedback, None)
        engine.dispose()


def submission(**changes):
    return {"request_id": "feedback-request-1", "artifact_id": "artifact-feedback", "claim_id": "claim-feedback",
            "issue": "incorrect_answer", "comment": "The comparison omits the measured trade-off.", **changes}


def data(response):
    assert response.is_success, response.text
    return response.json()["data"]


def test_feedback_captures_original_claim_and_replays_without_duplicates(feedback_api):
    client, _factory = feedback_api
    first = client.post("/api/v1/feedback", json=submission())
    assert first.status_code == 201, first.text
    saved = data(first)
    assert saved["feedback"]["status"] == "pending"
    assert saved["feedback"]["snapshot"]["claim"]["text"] == "Original claim"
    assert saved["feedback"]["snapshot"]["goal"] == "Explain the retrieval trade-off"
    assert saved["feedback"]["snapshot"]["provider_mode"] == "demo"
    replay = data(client.post("/api/v1/feedback", json=submission()))
    assert replay["replayed"] is True
    assert replay["feedback"]["id"] == saved["feedback"]["id"]
    assert len(data(client.get("/api/v1/feedback"))["items"]) == 1
    detail = client.get(f"/api/v1/feedback/{saved['feedback']['id']}")
    assert data(detail) == saved["feedback"]
    assert detail.headers["cache-control"] == "no-store"


def review(**changes):
    return {"request_id": "review-request-1", "expected_version": 1, "decision": "accepted",
            "reason": "Checked the original experiment notes.", "expected_answer": "Quality must be compared with latency.",
            "acceptance_criteria": "Explain both measured quality and latency; do not claim a universal winner.",
            "split": "holdout", "reference_evidence_ids": [], **changes}


def test_acceptance_creates_one_persistent_sample_and_replay_preserves_review(feedback_api):
    client, _factory = feedback_api
    feedback_id = data(client.post("/api/v1/feedback", json=submission()))["feedback"]["id"]
    path = f"/api/v1/feedback/{feedback_id}/review"
    response = client.post(path, json=review())
    assert response.status_code == 200, response.text
    accepted = data(response)["feedback"]
    assert accepted["status"] == "accepted"
    assert accepted["version"] == 2
    assert accepted["review"]["reviewer"] == "local_user"
    assert accepted["sample"]["split"] == "holdout"
    assert accepted["sample"]["expected_answer"] == "Quality must be compared with latency."
    replay = data(client.post(path, json=review()))
    assert replay["replayed"] is True
    assert replay["feedback"] == accepted
    assert data(client.get(f"/api/v1/feedback/{feedback_id}")) == accepted
    conflict = client.post(path, json=review(request_id="other-review", split="tuning"))
    assert conflict.status_code == 409


def test_export_contains_only_selected_reviewed_samples_and_is_reproducible(feedback_api):
    import hashlib
    import json

    client, _factory = feedback_api
    feedback_id = data(client.post("/api/v1/feedback", json=submission()))["feedback"]["id"]
    pending_export = client.post("/api/v1/feedback/cases/export", json={"feedback_ids": [feedback_id]})
    assert pending_export.status_code == 409
    data(client.post(f"/api/v1/feedback/{feedback_id}/review", json=review()))
    response = client.post("/api/v1/feedback/cases/export", json={"feedback_ids": [feedback_id]})
    exported = data(response)
    payload = json.loads(exported["content"])
    assert payload["format"] == "human_reviewed_feedback_v1"
    assert payload["split"] == "holdout"
    assert payload["provider_mode"] == "demo"
    assert payload["cases"][0]["snapshot"]["claim"]["text"] == "Original claim"
    assert payload["cases"][0]["sample"]["expected_answer"] == "Quality must be compared with latency."
    assert hashlib.sha256(exported["content"].encode("utf-8")).hexdigest() == exported["sha256"]
    assert data(client.post("/api/v1/feedback/cases/export", json={"feedback_ids": [feedback_id]})) == exported


@pytest.mark.parametrize("changes", [
    {"comment": "  "}, {"comment": "a" * 2001}, {"issue": "other"},
    {"snapshot": {}}, {"request_id": "../secret"}, {"claim_id": "unknown-claim"},
])
def test_submission_rejects_invalid_or_client_authored_facts(feedback_api, changes):
    client, _factory = feedback_api
    assert client.post("/api/v1/feedback", json=submission(**changes)).status_code == 422
    assert data(client.get("/api/v1/feedback"))["items"] == []


def test_snapshot_survives_changed_original_and_idempotency_conflicts(feedback_api):
    client, factory = feedback_api
    saved = data(client.post("/api/v1/feedback", json=submission()))["feedback"]
    with factory.begin() as session:
        session.get(AgentClaim, "claim-feedback").text = "Changed claim"
        session.get(AgentRun, "run-feedback").goal = "Changed question"
    assert data(client.get(f"/api/v1/feedback/{saved['id']}"))["snapshot"] == saved["snapshot"]
    assert data(client.post("/api/v1/feedback", json=submission()))["feedback"]["snapshot"] == saved["snapshot"]
    assert client.post("/api/v1/feedback", json=submission(comment="Changed request")).status_code == 409


@pytest.mark.parametrize("target", ["active_run", "unfinalized", "wrong_final", "wrong_claim"])
def test_feedback_rejects_nonfinal_or_mismatched_target(feedback_api, target):
    client, factory = feedback_api
    with factory.begin() as session:
        if target == "active_run":
            session.get(AgentRun, "run-feedback").status = "running"
        elif target == "unfinalized":
            session.get(AgentArtifact, "artifact-feedback").status = "draft"
        elif target == "wrong_final":
            session.get(AgentRun, "run-feedback").final_artifact_id = "different"
        else:
            session.add(AgentRun(id="run-other", space_id=1, goal="Other", requested_mode="force_quick",
                                 status="completed", phase="done", provider_mode="demo", scope_snapshot_json="{}", scope_digest="a"*64))
            session.flush()
            session.add(AgentArtifact(id="artifact-other", producing_run_id="run-other", kind="answer",
                                      title="Other", body_markdown="Other", status="final"))
            session.flush()
            session.get(AgentClaim, "claim-feedback").artifact_id = "artifact-other"
    response = client.post("/api/v1/feedback", json=submission())
    assert response.status_code == (422 if target == "wrong_claim" else 409)


@pytest.mark.parametrize("changes", [
    {"expected_version": 99}, {"expected_answer": None}, {"acceptance_criteria": " "},
    {"reference_evidence_ids": ["alien-evidence"]}, {"reviewer": "admin"},
    {"decision": "rejected"}, {"split": "training"}, {"expected_version": True},
])
def test_review_rejects_incomplete_stale_or_forged_input_without_partial_save(feedback_api, changes):
    client, _factory = feedback_api
    feedback_id = data(client.post("/api/v1/feedback", json=submission()))["feedback"]["id"]
    response = client.post(f"/api/v1/feedback/{feedback_id}/review", json=review(**changes))
    assert response.status_code == (409 if changes.get("expected_version") == 99 else 422)
    current = data(client.get(f"/api/v1/feedback/{feedback_id}"))
    assert current["status"] == "pending" and current["sample"] is None and current["review"] is None


def test_rejection_is_terminal_and_does_not_produce_sample(feedback_api):
    client, _factory = feedback_api
    feedback_id = data(client.post("/api/v1/feedback", json=submission()))["feedback"]["id"]
    command = {"request_id": "reject-1", "expected_version": 1, "decision": "rejected", "reason": "Original source supports the claim."}
    path = f"/api/v1/feedback/{feedback_id}/review"
    rejected = data(client.post(path, json=command))["feedback"]
    assert rejected["status"] == "rejected" and rejected["sample"] is None
    assert data(client.post(path, json=command))["replayed"] is True
    assert client.post(path, json=review()).status_code == 409
    assert client.post("/api/v1/feedback/cases/export", json={"feedback_ids": [feedback_id]}).status_code == 409


def test_concurrent_creation_and_review_are_idempotent(feedback_api):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    client, _factory = feedback_api
    gate = Barrier(4)

    def create(_):
        gate.wait()
        return data(client.post("/api/v1/feedback", json=submission()))

    with ThreadPoolExecutor(max_workers=4) as pool:
        receipts = list(pool.map(create, range(4)))
    assert len({item["feedback"]["id"] for item in receipts}) == 1
    assert sum(not item["replayed"] for item in receipts) == 1
    feedback_id = receipts[0]["feedback"]["id"]

    def accept(_):
        gate.wait()
        return data(client.post(f"/api/v1/feedback/{feedback_id}/review", json=review()))

    with ThreadPoolExecutor(max_workers=4) as pool:
        reviewed = list(pool.map(accept, range(4)))
    assert sum(not item["replayed"] for item in reviewed) == 1
    assert {item["feedback"]["sample"]["id"] for item in reviewed} == {feedback_id}


def test_sample_failure_rolls_back_acceptance(feedback_api):
    from sqlalchemy import text

    client, factory = feedback_api
    feedback_id = data(client.post("/api/v1/feedback", json=submission()))["feedback"]["id"]
    with factory.begin() as session:
        session.execute(text("CREATE TRIGGER reject_sample BEFORE INSERT ON feedback_samples BEGIN SELECT RAISE(ABORT, 'test disk write failure'); END"))
    assert client.post(f"/api/v1/feedback/{feedback_id}/review", json=review()).status_code == 409
    detail = data(client.get(f"/api/v1/feedback/{feedback_id}"))
    assert detail["status"] == "pending" and detail["version"] == 1 and detail["sample"] is None
    with factory.begin() as session:
        session.execute(text("DROP TRIGGER reject_sample"))
    assert data(client.post(f"/api/v1/feedback/{feedback_id}/review", json=review()))["feedback"]["status"] == "accepted"


def test_list_pagination_and_export_mode_split_isolation(feedback_api):
    client, factory = feedback_api
    ids = []
    for index in range(3):
        if index == 2:
            with factory.begin() as session:
                session.get(AgentRun, "run-feedback").provider_mode = "real"
        item = data(client.post("/api/v1/feedback", json=submission(request_id=f"request-{index}")))["feedback"]
        ids.append(item["id"])
        data(client.post(f"/api/v1/feedback/{item['id']}/review", json=review(
            request_id=f"review-{index}", split="holdout" if index == 0 else "tuning")))
    first = data(client.get("/api/v1/feedback?limit=1&status=accepted&provider_mode=demo"))
    second = data(client.get(f"/api/v1/feedback?limit=1&status=accepted&provider_mode=demo&after={first['next_after']}"))
    assert first["items"][0]["id"] == ids[0]
    assert second["items"][0]["id"] == ids[1] and second["next_after"] is None
    for selection in ([ids[0], ids[1]], [ids[1], ids[2]], [ids[0], ids[0]], []):
        assert client.post("/api/v1/feedback/cases/export", json={"feedback_ids": selection}).status_code == 422
    assert client.post("/api/v1/feedback/cases/export", json={"feedback_ids": [999]}).status_code == 404


def test_corrupt_snapshot_is_not_exposed_or_promoted(feedback_api):
    from app.models.feedback import ResearchFeedback

    client, factory = feedback_api
    feedback_id = data(client.post("/api/v1/feedback", json=submission()))["feedback"]["id"]
    with factory.begin() as session:
        session.get(ResearchFeedback, feedback_id).snapshot_json = '{}'
    assert client.get(f"/api/v1/feedback/{feedback_id}").status_code == 409
    assert client.post(f"/api/v1/feedback/{feedback_id}/review", json=review()).status_code == 409


def test_stored_mode_cannot_relabel_demo_snapshot_as_real(feedback_api):
    from app.models.feedback import ResearchFeedback

    client, factory = feedback_api
    feedback_id = data(client.post("/api/v1/feedback", json=submission()))["feedback"]["id"]
    with factory.begin() as session:
        session.get(ResearchFeedback, feedback_id).provider_mode = "real"
    assert client.get(f"/api/v1/feedback/{feedback_id}").status_code == 409


def test_reference_snapshot_keeps_exact_locator_after_source_retirement(feedback_api):
    from app.models.agent_evidence import AgentEvidence, ClaimEvidence
    from app.models.source import IndexRevision, MultimodalChunk, Source, SourceRevision

    client, factory = feedback_api
    with factory.begin() as session:
        session.add(Source(id=10, space_id=1, source_type="document", title="Original document"))
        session.flush()
        session.add(SourceRevision(id=11, source_id=10, revision_number=1, status="active", content_hash="b"*64))
        session.flush()
        session.add(IndexRevision(id=12, source_id=10, revision_id=11, index_version="test", status="active"))
        session.add(MultimodalChunk(id=13, source_id=10, revision_id=11, chunk_index=0, modality="text",
                                    source_type="document", content_text="Original source excerpt", content_hash="c"*64,
                                    search_text="Original source excerpt", locator_json='{"page_number":3}'))
        session.flush()
        session.add(AgentEvidence(id="reference-1", run_id="run-feedback", source_id=10, revision_id=11,
                                  index_revision_id=12, chunk_id=13, source_type="document", locator_json='{"page_number":3}',
                                  locator_digest="d"*64, revision_content_hash="b"*64, evidence_content_hash="c"*64,
                                  excerpt_preview="Original source excerpt", query="Original question"))
        session.flush()
        session.add(ClaimEvidence(claim_id="claim-feedback", evidence_id="reference-1", relation="supports",
                                  verifier_method="test", reason_code="test"))
    saved = data(client.post("/api/v1/feedback", json=submission()))["feedback"]
    reference = saved["snapshot"]["evidence"][0]
    assert reference["locator"] == {"page_number": 3}
    assert (reference["source_id"], reference["revision_id"], reference["index_revision_id"], reference["chunk_id"]) == (10, 11, 12, 13)
    assert reference["excerpt"] == "Original source excerpt"
    with factory.begin() as session:
        session.get(SourceRevision, 11).status = "retired"
        session.get(IndexRevision, 12).status = "retired"
    accepted = data(client.post(f"/api/v1/feedback/{saved['id']}/review", json=review(reference_evidence_ids=["reference-1"])))
    assert accepted["feedback"]["snapshot"]["evidence"] == [reference]
    assert accepted["feedback"]["sample"]["reference_evidence_ids"] == ["reference-1"]
