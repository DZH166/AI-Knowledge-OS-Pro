import json
import subprocess
import sys


def write_report(path, *, status: str = "passed", gate_count: int = 1) -> None:
    path.write_text(
        json.dumps(
            {
                "mode": "quick",
                "status": status,
                "generated_at": "2026-07-05T00:00:00+00:00",
                "git": {
                    "branch": "codex/v4.6-project-structure-learning",
                    "commit": "cc136206d19b9bc5845692edfd93e7d8edaad666",
                    "short_commit": "cc13620",
                    "dirty": False,
                },
                "report_path": "docs/v4_5_quality_gate_report.md",
                "gate_count": gate_count,
                "gates": [
                    {
                        "name": "encoding",
                        "status": status,
                        "duration_sec": 0.1,
                        "next_step": "No action required.",
                        "failure_reason": "" if status == "passed" else "exit_code=1",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def test_quality_artifact_check_passes_for_json_and_summary(tmp_path) -> None:
    report = tmp_path / "quality.json"
    summary = tmp_path / "summary.md"
    write_report(report)
    summary.write_text(
        "\n".join(
            [
                "# Quality Gate Summary",
                "",
                "- Mode: `quick`",
                "- Status: `passed`",
                "- Git branch: `codex/v4.6-project-structure-learning`",
                "- Git commit: `cc13620`",
                "- Git dirty: `no`",
                "",
                "## Gate Results",
                "",
                "## Optimization Focus",
                "",
            ]
        ),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/check_quality_artifacts.py",
            "--json",
            str(report),
            "--summary",
            str(summary),
            "--expected-mode",
            "quick",
            "--require-passed",
        ],
        text=True,
        capture_output=True,
        check=True,
    )

    assert "quality_artifacts=checked" in completed.stdout
    assert "result=passed" in completed.stdout


def test_quality_artifact_check_rejects_failed_report_when_required(tmp_path) -> None:
    report = tmp_path / "quality_failed.json"
    write_report(report, status="failed")

    completed = subprocess.run(
        [sys.executable, "scripts/check_quality_artifacts.py", "--json", str(report), "--require-passed"],
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 1
    assert "result=failed" in completed.stdout
    assert "Report status must be passed" in completed.stdout


def test_quality_artifact_check_rejects_gate_count_mismatch(tmp_path) -> None:
    report = tmp_path / "quality_bad_count.json"
    write_report(report, gate_count=2)

    completed = subprocess.run(
        [sys.executable, "scripts/check_quality_artifacts.py", "--json", str(report), "--expected-mode", "quick"],
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 1
    assert "gate_count=2" in completed.stdout


def test_quality_artifact_check_rejects_missing_git_metadata(tmp_path) -> None:
    report = tmp_path / "quality_missing_git.json"
    write_report(report)
    payload = json.loads(report.read_text(encoding="utf-8"))
    payload.pop("git")
    report.write_text(json.dumps(payload), encoding="utf-8")

    completed = subprocess.run(
        [sys.executable, "scripts/check_quality_artifacts.py", "--json", str(report), "--expected-mode", "quick"],
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 1
    assert "Report must include a git metadata object." in completed.stdout
