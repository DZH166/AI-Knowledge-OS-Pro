import json
import subprocess
import sys


def test_quality_report_summary_writes_markdown(tmp_path) -> None:
    report = tmp_path / "quality.json"
    summary = tmp_path / "quality.md"
    report.write_text(
        json.dumps(
            {
                "mode": "quick",
                "status": "passed",
                "generated_at": "2026-07-05T00:00:00+00:00",
                "git": {
                    "branch": "codex/v4.6-project-structure-learning",
                    "commit": "cc136206d19b9bc5845692edfd93e7d8edaad666",
                    "short_commit": "cc13620",
                    "dirty": False,
                },
                "report_path": "docs/v4_5_quality_gate_report.md",
                "gate_count": 2,
                "gates": [
                    {
                        "name": "encoding",
                        "status": "passed",
                        "duration_sec": 1.2,
                        "next_step": "No action required.",
                        "failure_reason": "",
                    },
                    {
                        "name": "frontend smoke",
                        "status": "passed",
                        "duration_sec": 0.5,
                        "next_step": "No action required.",
                        "failure_reason": "",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/summarize_quality_report.py",
            "--input",
            str(report),
            "--output",
            str(summary),
        ],
        text=True,
        capture_output=True,
        check=True,
    )

    markdown = summary.read_text(encoding="utf-8")
    assert "quality_summary=passed" in completed.stdout
    assert "Quality Gate Summary" in markdown
    assert "- Git branch: `codex/v4.6-project-structure-learning`" in markdown
    assert "- Git commit: `cc13620`" in markdown
    assert "- Git dirty: `no`" in markdown
    assert "| encoding | passed | 1.20s | - | No action required. |" in markdown
    assert "No failed gates were reported." in markdown
    assert "Use this report as the quick baseline" in markdown


def test_quality_report_summary_prioritizes_failed_gate(tmp_path) -> None:
    report = tmp_path / "quality_failed.json"
    report.write_text(
        json.dumps(
            {
                "mode": "release",
                "status": "failed",
                "generated_at": "2026-07-05T00:00:00+00:00",
                "git": {
                    "branch": "codex/v4.6-project-structure-learning",
                    "commit": "cc136206d19b9bc5845692edfd93e7d8edaad666",
                    "short_commit": "cc13620",
                    "dirty": True,
                },
                "gate_count": 1,
                "gates": [
                    {
                        "name": "release dry-run",
                        "status": "failed",
                        "duration_sec": 0.4,
                        "next_step": "Inspect forbidden release entries.",
                        "failure_reason": "exit_code=1",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [sys.executable, "scripts/summarize_quality_report.py", "--input", str(report)],
        text=True,
        capture_output=True,
        check=True,
    )

    assert "Fix `release dry-run`: Inspect forbidden release entries." in completed.stdout
    assert "quality_summary=passed" in completed.stdout


def test_quality_report_summary_uses_report_mode_in_next_action(tmp_path) -> None:
    report = tmp_path / "quality_release.json"
    report.write_text(
        json.dumps(
            {
                "mode": "release",
                "status": "passed",
                "generated_at": "2026-07-05T00:00:00+00:00",
                "git": {
                    "branch": "codex/v4.6-project-structure-learning",
                    "commit": "cc136206d19b9bc5845692edfd93e7d8edaad666",
                    "short_commit": "cc13620",
                    "dirty": False,
                },
                "gate_count": 1,
                "gates": [
                    {
                        "name": "secret scan",
                        "status": "passed",
                        "duration_sec": 0.4,
                        "next_step": "No action required.",
                        "failure_reason": "",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [sys.executable, "scripts/summarize_quality_report.py", "--input", str(report)],
        text=True,
        capture_output=True,
        check=True,
    )

    assert "Use this report as the release baseline" in completed.stdout
