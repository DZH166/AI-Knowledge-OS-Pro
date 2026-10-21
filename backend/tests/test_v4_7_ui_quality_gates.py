import subprocess
import sys


def test_v4_7_ui_performance_budget_passes() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/check_ui_performance_budget.py"],
        text=True,
        capture_output=True,
        check=True,
    )

    assert "ui_performance_budget=checked" in completed.stdout
    assert "main_nav_targets=18" in completed.stdout
    assert "result=passed" in completed.stdout


def test_v4_7_interaction_feedback_passes() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/check_interaction_feedback.py"],
        text=True,
        capture_output=True,
        check=True,
    )

    assert "interaction_feedback=checked" in completed.stdout
    assert "high_risk=0" in completed.stdout
    assert "result=passed" in completed.stdout
