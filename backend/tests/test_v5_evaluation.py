from __future__ import annotations

from scripts.evaluate_agentic_rag import run_demo_evaluation


def test_agentic_evaluator_runs_the_real_module_pipeline_not_seeded_qa_logs(tmp_path) -> None:
    report = run_demo_evaluation(tmp_path / "evaluation.db")

    assert report["status"] == "passed"
    assert report["pipeline"] == (
        "EvidenceIndex.stage/upsert/activate -> HybridAgentSearch -> "
        "EvidenceAgent.submit -> AgentRunner.advance_one + Hybrid evaluation arms"
    )
    assert report["provenance"]["agent_search"] == (
        "HybridAgentSearch(deterministic embedding/vector, pinned-scope RRF, "
        "rerank disabled)"
    )
    assert report["provenance"]["agent_search_calls"]["embedding_queries"] > 0
    assert report["provenance"]["agent_search_calls"]["vector_searches"] >= report[
        "provenance"
    ]["agent_search_calls"]["embedding_queries"]
    assert report["dataset"]["case_count"] == 60
    assert report["dataset"]["category_counts"] == {
        "cancel_recovery": 6,
        "cross_modal": 8,
        "insufficient_evidence": 8,
        "multi_hop": 12,
        "prompt_injection": 6,
        "single_hop": 12,
        "version_conflict": 8,
    }
    assert set(report["retrieval"]["arms"]) == {"dense", "sparse", "fusion", "rerank"}
    for arm in report["retrieval"]["arms"].values():
        assert set(arm) >= {
            "recall_at_k",
            "mrr",
            "ndcg_at_k",
            "active_revision_precision",
            "locator_validity",
        }
    assert report["retrieval"]["arms"]["rerank"]["provider"] == (
        "deterministic_feature_overlap_recording"
    )
    assert set(report["experiments"]) == {
        "v4_9_single_shot_proxy",
        "retrieval_only",
        "evidence_agent",
    }
    assert "HybridAgentSearch" in report["experiments"]["evidence_agent"]["method"]
    assert report["metrics"]["citation_completeness"] == 1.0
    assert report["metrics"]["immutable_evidence_identity_rate"] == 1.0
    assert report["metrics"]["unauthorized_action_rate"] == 0.0
    assert report["metrics"]["quick_plan_event_count"] == 0
    assert report["metrics"]["multi_hop_agent_lift_pp"] >= 10.0
    assert report["metrics"]["recovery_scenario_pass_rate"] == 1.0
    assert report["metrics"]["model_usage"]["calls"] > 0
    assert report["metrics"]["model_usage"]["input_tokens"] > 0
    assert report["metrics"]["model_usage"]["usage_is_estimated"] is True
    assert report["metrics"]["model_usage"]["cost_measurement"] == "estimated"
    assert report["metrics"]["model_usage"]["estimated_cost_calls"] == report["metrics"]["model_usage"]["calls"]
    assert report["metrics"]["model_usage"]["unknown_cost_calls"] == 0
    assert all(case["cost_measurement"] in {"estimated", "unknown"} for case in report["cases"])
    assert {case["actual_status"] for case in report["cases"]} == {
        "cancelled",
        "completed",
        "insufficient_evidence",
    }
    assert all(case["passed"] for case in report["cases"])
