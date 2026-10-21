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
    assert "primary_nav_targets=4" in completed.stdout
    assert "developer_nav_targets=8" in completed.stdout
    assert "main_nav_targets=12" in completed.stdout
    assert "result=passed" in completed.stdout


def test_v4_7_interaction_feedback_passes() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/check_interaction_feedback.py"],
        text=True,
        capture_output=True,
        check=True,
    )

    assert "interaction_feedback=checked" in completed.stdout
    high_risk = next(
        int(line.partition("=")[2])
        for line in completed.stdout.splitlines()
        if line.startswith("high_risk=")
    )
    assert high_risk <= 12
    assert "result=passed" in completed.stdout
