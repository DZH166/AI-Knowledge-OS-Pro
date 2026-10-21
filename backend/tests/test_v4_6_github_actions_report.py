import json
import subprocess
import sys
from pathlib import Path
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[2]
REPO = "DZH166/AI-Knowledge-OS-Pro"
BRANCH = "codex/v4.6-project-structure-learning"
COMMIT = "b" * 40


def artifact_path(name: str) -> Path:
    base = ROOT / ".pytest_tmp" / "github_actions_report_tests" / uuid4().hex
    base.mkdir(parents=True, exist_ok=True)
    return base / name


def report_payload(**overrides) -> dict[str, str]:
    payload = {
        "schema_version": "1",
        "result": "passed",
        "status": "completed",
        "conclusion": "success",
        "repo": REPO,
        "branch": BRANCH,
        "commit": COMMIT,
        "workflow_name": "CI",
        "run_id": "123456",
        "run_url": "https://github.com/DZH166/AI-Knowledge-OS-Pro/actions/runs/123456",
        "run_head_sha": COMMIT,
        "run_head_branch": BRANCH,
        "source": "input_json",
        "failure": "",
    }
    payload.update(overrides)
    return payload


def write_report(payload: dict[str, str]) -> Path:
    path = artifact_path("github_actions_status.json")
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def write_markdown(payload: dict[str, str]) -> Path:
    path = artifact_path("github_actions_status.md")
    lines = [
        "# GitHub Actions Status",
        "",
        f"- Result: `{payload['result']}`",
        f"- Status: `{payload['status']}`",
        f"- Conclusion: `{payload['conclusion'] or '-'}`",
        f"- Repository: `{payload['repo']}`",
        f"- Branch: `{payload['branch']}`",
        f"- Commit: `{payload['commit']}`",
        f"- Workflow: `{payload['workflow_name']}`",
        f"- Source: `{payload['source']}`",
        f"- Run id: `{payload['run_id'] or '-'}`",
        f"- Run URL: {payload['run_url'] or '-'}",
    ]
    if payload["failure"]:
        lines.extend(["", "## Failure", "", f"`{payload['failure']}`"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def run_validator(report: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "scripts/check_github_actions_report.py", "--report-json", str(report), *extra],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )


def test_github_actions_report_validator_accepts_passed_report_with_markdown() -> None:
    payload = report_payload()
    report = write_report(payload)
    markdown = write_markdown(payload)

    completed = run_validator(report, "--markdown", str(markdown))

    assert completed.returncode == 0
    assert "github_actions_report=checked" in completed.stdout
    assert "failures=0" in completed.stdout
    assert "result=passed" in completed.stdout


def test_github_actions_report_validator_accepts_unavailable_report() -> None:
    payload = report_payload(
        result="unavailable",
        status="unavailable",
        conclusion="",
        run_id="",
        run_url="",
        run_head_sha="",
        run_head_branch="",
        source="github_api",
        failure="github_api_http_404",
    )
    report = write_report(payload)
    markdown = write_markdown(payload)

    completed = run_validator(report, "--markdown", str(markdown))

    assert completed.returncode == 0
    assert "result=passed" in completed.stdout


def test_github_actions_report_validator_rejects_unavailable_without_failure() -> None:
    report = write_report(
        report_payload(
            result="unavailable",
            status="unavailable",
            conclusion="",
            run_id="",
            run_url="",
            run_head_sha="",
            run_head_branch="",
            failure="",
        )
    )

    completed = run_validator(report)

    assert completed.returncode == 1
    assert "result='unavailable' requires failure text" in completed.stdout


def test_github_actions_report_validator_rejects_bad_run_url() -> None:
    report = write_report(report_payload(run_url="https://example.com/actions/runs/123456"))

    completed = run_validator(report)

    assert completed.returncode == 1
    assert "run_url must point to the repository Actions run" in completed.stdout


def test_github_actions_report_validator_rejects_missing_markdown_file() -> None:
    report = write_report(report_payload())
    markdown = artifact_path("missing.md")

    completed = run_validator(report, "--markdown", str(markdown))

    assert completed.returncode == 1
    assert "Markdown report does not exist" in completed.stdout


def test_github_actions_report_validator_rejects_mismatched_markdown() -> None:
    payload = report_payload()
    report = write_report(payload)
    markdown = write_markdown({**payload, "result": "failed", "status": "completed", "conclusion": "failure"})

    completed = run_validator(report, "--markdown", str(markdown))

    assert completed.returncode == 1
    assert "Markdown report is missing required text: - Result: `passed`" in completed.stdout
