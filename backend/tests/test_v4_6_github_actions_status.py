import json
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

from scripts.check_github_actions import build_report
from scripts.check_github_actions import parse_github_repo


ROOT = Path(__file__).resolve().parents[2]
REPO = "DZH166/AI-Knowledge-OS-Pro"
BRANCH = "codex/v4.6-project-structure-learning"
COMMIT = "a" * 40


def artifact_path(name: str) -> Path:
    base = ROOT / ".pytest_tmp" / "github_actions_status_tests" / uuid4().hex
    base.mkdir(parents=True, exist_ok=True)
    return base / name


def sample_payload(*, status: str = "completed", conclusion: str | None = "success", commit: str = COMMIT) -> dict[str, object]:
    return {
        "workflow_runs": [
            {
                "id": 123456,
                "name": "CI",
                "head_branch": BRANCH,
                "head_sha": commit,
                "status": status,
                "conclusion": conclusion,
                "html_url": "https://github.com/DZH166/AI-Knowledge-OS-Pro/actions/runs/123456",
            }
        ]
    }


def write_payload(payload: dict[str, object]) -> Path:
    path = artifact_path("actions_runs.json")
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def run_cli(payload_path: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "scripts/check_github_actions.py",
            "--repo",
            REPO,
            "--branch",
            BRANCH,
            "--commit",
            COMMIT,
            "--input-json",
            str(payload_path),
            *extra,
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )


def test_parse_github_repo_accepts_https_and_ssh_remotes() -> None:
    assert parse_github_repo("https://github.com/DZH166/AI-Knowledge-OS-Pro.git") == REPO
    assert parse_github_repo("git@github.com:DZH166/AI-Knowledge-OS-Pro.git") == REPO
    assert parse_github_repo("https://example.com/DZH166/AI-Knowledge-OS-Pro.git") is None


def test_build_report_marks_completed_success_as_passed() -> None:
    report = build_report(
        sample_payload(),
        repo=REPO,
        branch=BRANCH,
        commit=COMMIT,
        workflow_name="CI",
        source="input_json",
    )

    assert report.result == "passed"
    assert report.status == "completed"
    assert report.conclusion == "success"
    assert report.run_id == "123456"


def test_check_github_actions_cli_writes_reports_for_passed_run() -> None:
    payload = write_payload(sample_payload())
    json_output = Path(".pytest_tmp/github_actions_status_tests") / uuid4().hex / "github_actions.json"
    markdown_output = json_output.with_suffix(".md")

    completed = run_cli(
        payload,
        "--json-output",
        json_output.as_posix(),
        "--markdown-output",
        markdown_output.as_posix(),
        "--require-success",
    )

    report = json.loads((ROOT / json_output).read_text(encoding="utf-8"))
    markdown = (ROOT / markdown_output).read_text(encoding="utf-8")
    assert completed.returncode == 0
    assert "github_actions=checked" in completed.stdout
    assert "github_actions_report=checked" in completed.stdout
    assert "result=passed" in completed.stdout
    assert report["result"] == "passed"
    assert report["source"] == "input_json"
    assert "GitHub Actions Status" in markdown
    assert "Result: `passed`" in markdown


def test_check_github_actions_cli_fails_require_success_for_failed_run() -> None:
    payload = write_payload(sample_payload(conclusion="failure"))

    completed = run_cli(payload, "--require-success")

    assert completed.returncode == 1
    assert "status=completed" in completed.stdout
    assert "conclusion=failure" in completed.stdout
    assert "result=failed" in completed.stdout


def test_check_github_actions_cli_reports_pending_without_require_failure() -> None:
    payload = write_payload(sample_payload(status="in_progress", conclusion=None))

    completed = run_cli(payload)

    assert completed.returncode == 0
    assert "status=in_progress" in completed.stdout
    assert "result=pending" in completed.stdout


def test_check_github_actions_cli_reports_unavailable_when_no_matching_run() -> None:
    payload = write_payload(sample_payload(commit="0" * 40))

    completed = run_cli(payload)

    assert completed.returncode == 0
    assert "status=unavailable" in completed.stdout
    assert "result=unavailable" in completed.stdout
    assert "No 'CI' workflow run matched" in completed.stdout


def test_check_github_actions_cli_rejects_report_output_outside_pytest_tmp() -> None:
    payload = write_payload(sample_payload())

    completed = run_cli(payload, "--json-output", "docs/github_actions.json")

    assert completed.returncode == 1
    assert "result=unavailable" in completed.stdout
    assert "JSON output must be written under .pytest_tmp" in completed.stdout
