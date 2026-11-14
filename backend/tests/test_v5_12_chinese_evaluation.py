from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

import pytest

from scripts.evaluate_chinese_retrieval import evaluate


def _dataset() -> dict:
    return {
        "schema_version": 1,
        "dataset_id": "evaluator-contract",
        "sources": [{
            "key": "events",
            "space_id": 1,
            "versions": [{"key": "v1", "chunks": [{"key": "cursor", "text": "durable cursor"}]}],
        }],
        "queries": [
            {"id": "literal", "category": "literal", "space_id": 1,
             "text": "durable cursor", "expected": ["events/v1/cursor"]},
            {"id": "translation", "category": "no-literal-overlap", "space_id": 1,
             "text": "持久游标", "expected": ["events/v1/cursor"]},
            {"id": "unrelated", "category": "negative", "space_id": 1,
             "text": "quantum", "expected": []},
        ],
    }


def _write_dataset(tmp_path: Path, dataset: dict) -> Path:
    path = tmp_path / "labeled.json"
    path.write_text(json.dumps(dataset, ensure_ascii=False), encoding="utf-8")
    return path


def test_evaluator_counts_missed_positive_queries_and_keeps_negatives_separate(tmp_path: Path) -> None:
    path = _write_dataset(tmp_path, _dataset())
    report = evaluate(path)

    for name, metrics in report["metrics"].items():
        assert metrics == {
            "positive_queries": 2,
            "negative_queries": 1,
            "hit_at_1": 0.5,
            "hit_at_5": 0.5,
            "mrr": 0.5,
            "negative_empty_successes": 1,
            "scope_violations": 0,
            "identity_violations": 0,
        }
        assert report["queries"][0]["paths"][name]["ranking"][0]["case_key"] == "events/v1/cursor"
        assert report["queries"][1]["paths"][name]["ranking"] == []
    assert report["strict_passed"] is True  # Safety gates are not a positive-accuracy gate.
    assert report["providers"]["external_calls"] == 0
    repeated = evaluate(path)
    assert repeated["metrics"] == report["metrics"]
    assert repeated["dataset_sha256"] == report["dataset_sha256"]
    assert repeated["evaluator_sha256"] == report["evaluator_sha256"]


def test_locked_chinese_corpus_preserves_manual_top_one_answers_and_empty_negatives() -> None:
    report = evaluate()

    for query in report["queries"]:
        for name, result in query["paths"].items():
            assert result["scope_violations"] == result["identity_violations"] == 0, (query["id"], name)
            if query["expected"]:
                assert result["ranking"], (query["id"], name, "missed manual answer")
                assert result["ranking"][0]["case_key"] in query["expected"], (query["id"], name)
            else:
                assert result["ranking"] == [], (query["id"], name, "unanswerable query returned evidence")


@pytest.mark.parametrize("invalid", ["duplicate-id", "unknown-answer", "answer-outside-scope"])
def test_evaluator_rejects_invalid_manual_answer_labels(tmp_path: Path, invalid: str) -> None:
    dataset = _dataset()
    if invalid == "duplicate-id":
        dataset["queries"].append(deepcopy(dataset["queries"][0]))
    elif invalid == "unknown-answer":
        dataset["queries"][0]["expected"] = ["events/v1/not-a-chunk"]
    else:
        dataset["queries"][0]["space_id"] = 2

    with pytest.raises(ValueError, match="Duplicate query id|unknown reference|outside the query scope"):
        evaluate(_write_dataset(tmp_path, dataset))


def test_strict_cli_fails_when_an_unanswerable_query_returns_evidence(tmp_path: Path) -> None:
    dataset = _dataset()
    dataset["queries"] = [{
        "id": "false-positive", "category": "negative", "space_id": 1,
        "text": "durable cursor", "expected": [],
    }]
    path = _write_dataset(tmp_path, dataset)
    output = tmp_path / "report.json"
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, "-B", "scripts/evaluate_chinese_retrieval.py", "--dataset", str(path),
         "--output", str(output), "--strict"],
        cwd=root, capture_output=True, text=True, encoding="utf-8", timeout=60, check=False,
    )

    assert result.returncode == 1, result.stderr
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["strict_passed"] is False
    for metrics in report["metrics"].values():
        assert metrics["positive_queries"] == 0
        assert metrics["hit_at_1"] is None
        assert metrics["negative_queries"] == 1
        assert metrics["negative_empty_successes"] == 0
