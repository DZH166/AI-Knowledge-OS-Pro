import subprocess
import sys
import json

from scripts.seed_demo_data import main as seed_demo_main


def test_demo_rag_evaluation_passes_on_seeded_demo_database(tmp_path, monkeypatch) -> None:
    database = tmp_path / "demo_showcase.db"
    report = tmp_path / "rag_eval_report.json"
    monkeypatch.setattr(sys, "argv", ["seed_demo_data.py", "--database-path", str(database), "--reset"])
    seed_demo_main()

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/evaluate_rag.py",
            "--demo",
            "--database-path",
            str(database),
            "--output",
            str(report),
        ],
        text=True,
        capture_output=True,
        check=True,
    )

    assert "rag_evaluation_mode=demo" in completed.stdout
    assert "result=passed" in completed.stdout
    assert "timestamp_citations=" in completed.stdout
    assert "refusal_answers=1" in completed.stdout
    assert "valid_citations=1" in completed.stdout
    assert "code_locators=2" in completed.stdout
    assert "citation_source_types=" in completed.stdout
    assert "does not measure real LLM quality" in completed.stdout

    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["result"] == "passed"
    assert payload["summary"]["qa_logs"] == 2
    assert payload["coverage"]["citation_source_type_counts"]["video"] == 1
    assert payload["coverage"]["multimodal_source_type_counts"]["video"] >= 1
    assert payload["coverage"]["locator_shape_counts"]["code_file_line"] == 2
    assert payload["coverage"]["locator_shape_counts"]["media_timestamp"] >= 1
    assert len(payload["coverage"]["qa_traces"]) == 2
    assert any(trace["retrieval_status"] == "insufficient_context" for trace in payload["coverage"]["qa_traces"])
    assert "does not measure real LLM quality" in payload["boundary"]


def test_rag_evaluation_requires_demo_flag() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/evaluate_rag.py"],
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 1
    assert "Only --demo evaluation is implemented" in completed.stderr


def test_demo_rag_evaluation_defaults_to_an_isolated_seed(tmp_path) -> None:
    report = tmp_path / "isolated_rag_eval.json"
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/evaluate_rag.py",
            "--demo",
            "--output",
            str(report),
        ],
        text=True,
        capture_output=True,
        check=True,
    )

    assert "database_source=isolated_seed" in completed.stdout
    assert "qa_logs=2" in completed.stdout
    assert "result=passed" in completed.stdout
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["database_source"] == "isolated_seed"
    assert payload["summary"]["qa_logs"] == 2
    assert payload["result"] == "passed"
