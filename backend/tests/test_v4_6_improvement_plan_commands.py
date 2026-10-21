import json
import subprocess
import sys


def write_plan(path, items) -> None:
    path.write_text(
        json.dumps(
            {
                "source_index": ".pytest_tmp/self_check",
                "run_count": 1,
                "failed_runs": 0,
                "regression_runs": 0,
                "item_count": len(items),
                "items": items,
            }
        ),
        encoding="utf-8",
    )


def test_improvement_plan_command_validator_accepts_allowlisted_commands(tmp_path) -> None:
    plan = tmp_path / "plan.json"
    write_plan(
        plan,
        [
            {
                "priority": "P2",
                "title": "Add a comparison baseline",
                "evidence": "latest run was not compared",
                "action": "rerun self-check",
                "command": "python scripts/run_self_check.py --mode quick --output-dir .pytest_tmp/self_check --compare-latest --write-index --write-plan --fail-on-regression",
            },
            {
                "priority": "P3",
                "title": "Broaden validation scope",
                "evidence": "release is healthy",
                "action": "run full gate",
                "command": "python scripts/run_self_check.py --mode full --output-dir .pytest_tmp/self_check_full --write-index --write-plan",
            },
            {
                "priority": "P3",
                "title": "Legacy full gate",
                "evidence": "release is healthy",
                "action": "run full gate",
                "command": "python scripts/check_all.py --full --json-report .pytest_tmp/check_all_full.json",
            },
        ],
    )

    completed = subprocess.run(
        [sys.executable, "scripts/check_improvement_plan_commands.py", "--plan-json", str(plan)],
        text=True,
        capture_output=True,
        check=True,
    )

    assert "improvement_plan_commands=checked" in completed.stdout
    assert "command_count=3" in completed.stdout
    assert "next_command=python scripts/run_self_check.py" in completed.stdout
    assert "result=passed" in completed.stdout


def test_improvement_plan_command_validator_allows_manual_items_without_command(tmp_path) -> None:
    plan = tmp_path / "manual_plan.json"
    write_plan(
        plan,
        [
            {
                "priority": "P0",
                "title": "Inspect failed self-check runs",
                "evidence": "one failed run",
                "action": "inspect artifacts",
                "command": "",
            }
        ],
    )

    completed = subprocess.run(
        [sys.executable, "scripts/check_improvement_plan_commands.py", "--plan-json", str(plan)],
        text=True,
        capture_output=True,
        check=True,
    )

    assert "command_count=0" in completed.stdout
    assert "result=passed" in completed.stdout


def test_improvement_plan_command_validator_rejects_non_allowlisted_command(tmp_path) -> None:
    plan = tmp_path / "unsafe_plan.json"
    write_plan(
        plan,
        [
            {
                "priority": "P0",
                "title": "Unsafe",
                "evidence": "bad",
                "action": "bad",
                "command": "python scripts/seed_demo_data.py --reset",
            }
        ],
    )

    completed = subprocess.run(
        [sys.executable, "scripts/check_improvement_plan_commands.py", "--plan-json", str(plan)],
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 1
    assert "result=failed" in completed.stdout
    assert "Command is not in the self-check allowlist." in completed.stdout


def test_improvement_plan_command_validator_rejects_paths_outside_pytest_tmp(tmp_path) -> None:
    plan = tmp_path / "bad_path_plan.json"
    write_plan(
        plan,
        [
            {
                "priority": "P3",
                "title": "Bad path",
                "evidence": "bad",
                "action": "bad",
                "command": "python scripts/check_all.py --full --json-report docs/check_all_full.json",
            }
        ],
    )

    completed = subprocess.run(
        [sys.executable, "scripts/check_improvement_plan_commands.py", "--plan-json", str(plan)],
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 1
    assert "relative .pytest_tmp path" in completed.stdout
