import subprocess
import sys

from scripts.seed_demo_data import main as seed_demo_main


def test_demo_rag_evaluation_passes_on_seeded_demo_database(tmp_path, monkeypatch) -> None:
    database = tmp_path / "demo_showcase.db"
    monkeypatch.setattr(sys, "argv", ["seed_demo_data.py", "--database-path", str(database), "--reset"])
    seed_demo_main()

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/evaluate_rag.py",
            "--demo",
            "--database-path",
            str(database),
        ],
        text=True,
        capture_output=True,
        check=True,
    )

    assert "rag_evaluation_mode=demo" in completed.stdout
    assert "result=passed" in completed.stdout
    assert "timestamp_citations=" in completed.stdout
    assert "does not measure real LLM quality" in completed.stdout


def test_rag_evaluation_requires_demo_flag() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/evaluate_rag.py"],
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 1
    assert "Only --demo evaluation is implemented" in completed.stderr
