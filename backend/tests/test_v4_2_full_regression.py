import subprocess
import sys

from scripts.seed_demo_data import main as seed_demo_main


def test_full_regression_check_passes_on_seeded_demo_database(tmp_path, monkeypatch) -> None:
    database = tmp_path / "demo_showcase.db"
    monkeypatch.setattr(sys, "argv", ["seed_demo_data.py", "--database-path", str(database), "--reset"])
    seed_demo_main()

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/check_full_regression.py",
            "--database-path",
            str(database),
        ],
        text=True,
        capture_output=True,
        check=True,
    )

    assert "full_regression=checked" in completed.stdout
    assert "result=passed" in completed.stdout
    assert "source_types=audio,code_repository,image,video" in completed.stdout
    assert "qa_statuses=grounded,insufficient_context" in completed.stdout
    assert "checks=" in completed.stdout


def test_demo_readiness_requires_complete_v4_2_demo_chain(tmp_path, monkeypatch) -> None:
    database = tmp_path / "demo_showcase.db"
    monkeypatch.setattr(sys, "argv", ["seed_demo_data.py", "--database-path", str(database), "--reset"])
    seed_demo_main()

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/check_demo_ready.py",
            "--database-path",
            str(database),
        ],
        text=True,
        capture_output=True,
        check=True,
    )

    assert "sources=4" in completed.stdout
    assert "multimodal_chunks=9" in completed.stdout
    assert "qa_logs=2" in completed.stdout
    assert "'code_repository': 1" in completed.stdout
    assert "'video': 1" in completed.stdout
    assert "Demo readiness check passed" in completed.stdout
