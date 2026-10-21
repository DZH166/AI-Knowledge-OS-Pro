import json
import subprocess
import sys


def test_improvement_plan_prioritizes_failed_and_regressed_runs(tmp_path) -> None:
    index = tmp_path / "index.json"
    output = tmp_path / "plan.md"
    json_output = tmp_path / "plan.json"
    index.write_text(
        json.dumps(
            {
                "input_dir": ".pytest_tmp/self_check",
                "run_count": 2,
                "failed_runs": 1,
                "regression_runs": 1,
                "latest_run": {
                    "status": "failed",
                    "regression_count": 1,
                },
                "runs": [],
            }
        ),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/plan_self_check_improvements.py",
            "--index",
            str(index),
            "--output",
            str(output),
            "--json-output",
            str(json_output),
        ],
        text=True,
        capture_output=True,
        check=True,
    )

    markdown = output.read_text(encoding="utf-8")
    payload = json.loads(json_output.read_text(encoding="utf-8"))
    assert "self_check_improvement_plan=passed" in completed.stdout
    assert "Inspect failed self-check runs" in markdown
    assert "Review regression comparison reports" in markdown
    assert "| Priority | Action | Evidence | Next Step | Command |" in markdown
    assert payload["item_count"] == 2
    assert all("command" in item for item in payload["items"])


def test_improvement_plan_uses_comparison_details(tmp_path) -> None:
    index = tmp_path / "index.json"
    comparison = tmp_path / "comparison.json"
    index.write_text(
        json.dumps(
            {
                "input_dir": ".pytest_tmp/self_check",
                "run_count": 1,
                "failed_runs": 0,
                "regression_runs": 0,
                "latest_run": {"status": "passed", "regression_count": 0},
                "runs": [],
            }
        ),
        encoding="utf-8",
    )
    comparison.write_text(
        json.dumps(
            {
                "status_changes": [],
                "missing_gates": [],
                "slower_gates": [{"gate": "encoding", "delta_sec": 9.0}],
            }
        ),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [sys.executable, "scripts/plan_self_check_improvements.py", "--index", str(index), "--comparison", str(comparison)],
        text=True,
        capture_output=True,
        check=True,
    )

    assert "Review slower quality gates" in completed.stdout
    assert "self_check_improvement_plan=passed" in completed.stdout


def test_improvement_plan_marks_healthy_baseline_as_broaden_scope(tmp_path) -> None:
    index = tmp_path / "healthy.json"
    index.write_text(
        json.dumps(
            {
                "input_dir": ".pytest_tmp/self_check",
                "run_count": 1,
                "failed_runs": 0,
                "regression_runs": 0,
                "latest_run": {"status": "passed", "regression_count": 0},
                "runs": [],
            }
        ),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [sys.executable, "scripts/plan_self_check_improvements.py", "--index", str(index)],
        text=True,
        capture_output=True,
        check=True,
    )

    assert "Broaden validation scope" in completed.stdout
    assert "python scripts/run_self_check.py --mode release" in completed.stdout


def test_improvement_plan_suggests_auto_compare_command_for_uncompared_pass(tmp_path) -> None:
    index = tmp_path / "needs_baseline.json"
    json_output = tmp_path / "plan.json"
    index.write_text(
        json.dumps(
            {
                "input_dir": ".pytest_tmp/self_check",
                "run_count": 1,
                "failed_runs": 0,
                "regression_runs": 0,
                "latest_run": {"status": "passed", "regression_count": None},
                "runs": [],
            }
        ),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/plan_self_check_improvements.py",
            "--index",
            str(index),
            "--json-output",
            str(json_output),
        ],
        text=True,
        capture_output=True,
        check=True,
    )

    payload = json.loads(json_output.read_text(encoding="utf-8"))
    assert "Add a comparison baseline" in completed.stdout
    assert "--compare-latest" in completed.stdout
    assert payload["items"][0]["command"].endswith("--fail-on-regression")


def test_improvement_plan_uses_latest_mode_in_command_suggestions(tmp_path) -> None:
    index = tmp_path / "release_needs_baseline.json"
    index.write_text(
        json.dumps(
            {
                "input_dir": ".pytest_tmp/self_check_release",
                "run_count": 1,
                "failed_runs": 0,
                "regression_runs": 0,
                "latest_run": {"mode": "release", "status": "passed", "regression_count": None},
                "runs": [],
            }
        ),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [sys.executable, "scripts/plan_self_check_improvements.py", "--index", str(index)],
        text=True,
        capture_output=True,
        check=True,
    )

    assert "--mode release" in completed.stdout
    assert "--output-dir .pytest_tmp/self_check_release" in completed.stdout


def test_improvement_plan_uses_release_mode_in_broaden_scope_action(tmp_path) -> None:
    index = tmp_path / "release_healthy.json"
    index.write_text(
        json.dumps(
            {
                "input_dir": ".pytest_tmp/self_check_release",
                "run_count": 1,
                "failed_runs": 0,
                "regression_runs": 0,
                "latest_run": {"mode": "release", "status": "passed", "regression_count": 0},
                "runs": [],
            }
        ),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [sys.executable, "scripts/plan_self_check_improvements.py", "--index", str(index)],
        text=True,
        capture_output=True,
        check=True,
    )

    assert "healthy release baseline" in completed.stdout
    assert "python scripts/run_self_check.py --mode full" in completed.stdout


def test_improvement_plan_full_mode_has_no_broader_command(tmp_path) -> None:
    index = tmp_path / "full_healthy.json"
    json_output = tmp_path / "plan.json"
    index.write_text(
        json.dumps(
            {
                "input_dir": ".pytest_tmp/self_check_full",
                "run_count": 1,
                "failed_runs": 0,
                "regression_runs": 0,
                "latest_run": {"mode": "full", "status": "passed", "regression_count": 0},
                "runs": [],
            }
        ),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/plan_self_check_improvements.py",
            "--index",
            str(index),
            "--json-output",
            str(json_output),
        ],
        text=True,
        capture_output=True,
        check=True,
    )

    payload = json.loads(json_output.read_text(encoding="utf-8"))
    assert "healthy full baseline" in completed.stdout
    assert payload["items"][0]["command"] == ""
