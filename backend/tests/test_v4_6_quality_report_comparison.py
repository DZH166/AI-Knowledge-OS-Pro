import json
import subprocess
import sys


def write_report(path, *, status: str = "passed", gates: list[dict] | None = None) -> None:
    if gates is None:
        gates = [
            {
                "name": "encoding",
                "status": "passed",
                "duration_sec": 1.0,
                "next_step": "No action required.",
                "failure_reason": "",
            }
        ]
    path.write_text(
        json.dumps(
            {
                "mode": "quick",
                "status": status,
                "generated_at": "2026-07-05T00:00:00+00:00",
                "gate_count": len(gates),
                "gates": gates,
            }
        ),
        encoding="utf-8",
    )


def test_quality_report_comparison_detects_status_and_duration_changes(tmp_path) -> None:
    base = tmp_path / "base.json"
    current = tmp_path / "current.json"
    output = tmp_path / "comparison.md"
    json_output = tmp_path / "comparison.json"
    write_report(
        base,
        gates=[
            {"name": "encoding", "status": "passed", "duration_sec": 1.0, "next_step": "No action required.", "failure_reason": ""},
            {"name": "frontend smoke", "status": "passed", "duration_sec": 1.0, "next_step": "No action required.", "failure_reason": ""},
        ],
    )
    write_report(
        current,
        status="failed",
        gates=[
            {"name": "encoding", "status": "failed", "duration_sec": 8.0, "next_step": "Fix encoding.", "failure_reason": "exit_code=1"},
            {"name": "release dry-run", "status": "passed", "duration_sec": 1.0, "next_step": "No action required.", "failure_reason": ""},
        ],
    )

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/compare_quality_reports.py",
            "--base",
            str(base),
            "--current",
            str(current),
            "--output",
            str(output),
            "--json-output",
            str(json_output),
            "--slow-threshold-sec",
            "2",
        ],
        text=True,
        capture_output=True,
        check=True,
    )

    markdown = output.read_text(encoding="utf-8")
    comparison = json.loads(json_output.read_text(encoding="utf-8"))
    assert "quality_comparison=passed" in completed.stdout
    assert "`encoding`: `passed` -> `failed`" in markdown
    assert "Missing gates: `frontend smoke`" in markdown
    assert "New gates: `release dry-run`" in markdown
    assert "`encoding`: 1.00s -> 8.00s (+7.00s)" in markdown
    assert comparison["regression_count"] == 2


def test_quality_report_comparison_can_fail_on_regression(tmp_path) -> None:
    base = tmp_path / "base.json"
    current = tmp_path / "current.json"
    write_report(base)
    write_report(
        current,
        status="failed",
        gates=[
            {
                "name": "encoding",
                "status": "failed",
                "duration_sec": 1.0,
                "next_step": "Fix encoding.",
                "failure_reason": "exit_code=1",
            }
        ],
    )

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/compare_quality_reports.py",
            "--base",
            str(base),
            "--current",
            str(current),
            "--fail-on-regression",
        ],
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 1
    assert "quality_comparison=failed" in completed.stdout


def test_quality_report_comparison_preserves_duplicate_gate_occurrences(tmp_path) -> None:
    base = tmp_path / "base.json"
    current = tmp_path / "current.json"
    json_output = tmp_path / "comparison.json"
    write_report(
        base,
        gates=[
            {"name": "E2E scaffolding", "status": "passed", "duration_sec": 1.0, "next_step": "No action required.", "failure_reason": ""},
            {"name": "E2E scaffolding", "status": "passed", "duration_sec": 2.0, "next_step": "No action required.", "failure_reason": ""},
            {"name": "release dry-run", "status": "passed", "duration_sec": 1.0, "next_step": "No action required.", "failure_reason": ""},
        ],
    )
    write_report(
        current,
        gates=[
            {"name": "E2E scaffolding", "status": "passed", "duration_sec": 1.0, "next_step": "No action required.", "failure_reason": ""},
            {"name": "release dry-run", "status": "passed", "duration_sec": 1.0, "next_step": "No action required.", "failure_reason": ""},
        ],
    )

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/compare_quality_reports.py",
            "--base",
            str(base),
            "--current",
            str(current),
            "--json-output",
            str(json_output),
        ],
        text=True,
        capture_output=True,
    )

    comparison = json.loads(json_output.read_text(encoding="utf-8"))
    assert completed.returncode == 0
    assert comparison["base_gate_count"] == 3
    assert comparison["current_gate_count"] == 2
    assert comparison["missing_gates"] == ["E2E scaffolding #2"]
    assert comparison["regression_count"] == 1


def test_quality_report_comparison_detects_duplicate_occurrence_status_change(tmp_path) -> None:
    base = tmp_path / "base.json"
    current = tmp_path / "current.json"
    json_output = tmp_path / "comparison.json"
    write_report(
        base,
        gates=[
            {"name": "E2E scaffolding", "status": "passed", "duration_sec": 1.0, "next_step": "No action required.", "failure_reason": ""},
            {"name": "E2E scaffolding", "status": "passed", "duration_sec": 2.0, "next_step": "No action required.", "failure_reason": ""},
        ],
    )
    write_report(
        current,
        gates=[
            {"name": "E2E scaffolding", "status": "passed", "duration_sec": 1.0, "next_step": "No action required.", "failure_reason": ""},
            {"name": "E2E scaffolding", "status": "failed", "duration_sec": 2.0, "next_step": "Review E2E.", "failure_reason": "exit_code=1"},
        ],
    )

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/compare_quality_reports.py",
            "--base",
            str(base),
            "--current",
            str(current),
            "--json-output",
            str(json_output),
            "--fail-on-regression",
        ],
        text=True,
        capture_output=True,
    )

    comparison = json.loads(json_output.read_text(encoding="utf-8"))
    assert completed.returncode == 1
    assert comparison["base_gate_count"] == 2
    assert comparison["current_gate_count"] == 2
    assert comparison["status_changes"] == [{"gate": "E2E scaffolding #2", "from": "passed", "to": "failed"}]
    assert comparison["regression_count"] == 1
