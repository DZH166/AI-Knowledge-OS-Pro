import json
import subprocess
import sys


def write_report(path, *, generated_at: str, status: str = "passed") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "mode": "quick",
                "status": status,
                "generated_at": generated_at,
                "git": {
                    "branch": "codex/v4.6-project-structure-learning",
                    "commit": "cc136206d19b9bc5845692edfd93e7d8edaad666",
                    "short_commit": "cc13620",
                    "dirty": status != "passed",
                },
                "gate_count": 1,
                "gates": [
                    {
                        "name": "encoding",
                        "status": status,
                        "duration_sec": 1.0,
                        "next_step": "No action required.",
                        "failure_reason": "" if status == "passed" else "exit_code=1",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def test_self_check_index_writes_json_and_markdown(tmp_path) -> None:
    input_dir = tmp_path / "checks"
    write_report(input_dir / "run-1" / "check_all_quick.json", generated_at="2026-07-05T00:00:00+00:00")
    write_report(input_dir / "run-2" / "check_all_quick.json", generated_at="2026-07-05T00:05:00+00:00", status="failed")
    (input_dir / "run-2" / "check_all_quick_comparison.json").write_text(
        json.dumps({"regression_count": 1}),
        encoding="utf-8",
    )
    output = tmp_path / "index.json"
    markdown = tmp_path / "index.md"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/index_self_checks.py",
            "--input-dir",
            str(input_dir),
            "--output",
            str(output),
            "--markdown-output",
            str(markdown),
        ],
        text=True,
        capture_output=True,
        check=True,
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    text = markdown.read_text(encoding="utf-8")
    assert "self_check_index=passed" in completed.stdout
    assert payload["run_count"] == 2
    assert payload["failed_runs"] == 1
    assert payload["regression_runs"] == 1
    assert payload["latest_run"]["status"] == "failed"
    assert payload["latest_run"]["git"]["short_commit"] == "cc13620"
    assert "Self-Check History Index" in text
    assert "codex/v4.6-project-structure-learning@cc13620" in text
    assert "- Git dirty: `yes`" in text
    assert "Inspect failed runs before promoting the current branch." in text


def test_self_check_index_handles_empty_directory(tmp_path) -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/index_self_checks.py", "--input-dir", str(tmp_path)],
        text=True,
        capture_output=True,
        check=True,
    )

    assert "Runs: 0" in completed.stdout
    assert "Generate at least one self-check run" in completed.stdout


def test_self_check_index_ignores_pytest_temp_reports(tmp_path) -> None:
    input_dir = tmp_path / "checks"
    write_report(input_dir / "self_check" / "check_all_quick.json", generated_at="2026-07-05T00:00:00+00:00")
    write_report(input_dir / "test_fixture0" / "check_all_quick.json", generated_at="2026-07-05T00:05:00+00:00", status="failed")

    completed = subprocess.run(
        [sys.executable, "scripts/index_self_checks.py", "--input-dir", str(input_dir)],
        text=True,
        capture_output=True,
        check=True,
    )

    assert "Runs: 1" in completed.stdout
    assert "Failed runs: 0" in completed.stdout
