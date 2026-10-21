import json
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

from scripts.check_ci_artifacts import REQUIRED_COMMANDS
from scripts.check_ci_artifacts import REQUIRED_ORDERED_SNIPPETS
from scripts.check_ci_artifacts import REQUIRED_QUALITY_ARTIFACT_PATHS
from scripts.check_ci_artifacts import REQUIRED_WORKFLOW_SNIPPETS


ROOT = Path(__file__).resolve().parents[2]


def artifact_path(name: str) -> Path:
    base = ROOT / ".pytest_tmp" / "ci_artifacts_report_tests" / uuid4().hex
    base.mkdir(parents=True, exist_ok=True)
    return base / name


def report_payload(**overrides) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": "1",
        "result": "passed",
        "workflow": ".github/workflows/ci.yml",
        "required_commands": len(REQUIRED_COMMANDS),
        "required_artifact_paths": len(REQUIRED_QUALITY_ARTIFACT_PATHS),
        "required_workflow_snippets": len(REQUIRED_WORKFLOW_SNIPPETS),
        "required_ordered_groups": len(REQUIRED_ORDERED_SNIPPETS),
        "failure_count": 0,
        "failures": [],
    }
    payload.update(overrides)
    return payload


def write_report(payload: dict[str, object]) -> Path:
    path = artifact_path("ci_artifacts_contract.json")
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def write_markdown(payload: dict[str, object]) -> Path:
    path = artifact_path("ci_artifacts_contract.md")
    lines = [
        "# CI Artifact Contract",
        "",
        f"- Result: `{payload['result']}`",
        f"- Workflow: `{payload['workflow']}`",
        f"- Required commands: {payload['required_commands']}",
        f"- Required artifact paths: {payload['required_artifact_paths']}",
        f"- Required workflow snippets: {payload['required_workflow_snippets']}",
        f"- Required ordered groups: {payload['required_ordered_groups']}",
        f"- Failures: {payload['failure_count']}",
        "",
        "## Failures",
        "",
    ]
    failures = payload["failures"]
    if isinstance(failures, list) and failures:
        lines.extend(f"- {failure}" for failure in failures)
    else:
        lines.append("- None")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def run_validator(report: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "scripts/check_ci_artifacts_report.py", "--report-json", str(report), *extra],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )


def test_ci_artifacts_report_validator_accepts_passed_report_with_markdown() -> None:
    payload = report_payload()
    report = write_report(payload)
    markdown = write_markdown(payload)

    completed = run_validator(report, "--markdown", str(markdown))

    assert completed.returncode == 0
    assert "ci_artifacts_report=checked" in completed.stdout
    assert "failures=0" in completed.stdout
    assert "result=passed" in completed.stdout


def test_ci_artifacts_report_validator_accepts_failed_report_with_markdown() -> None:
    payload = report_payload(
        result="failed",
        failure_count=2,
        failures=[
            "CI workflow is missing self-check command: example",
            "CI quality artifact upload is missing path: .pytest_tmp/example.json",
        ],
    )
    report = write_report(payload)
    markdown = write_markdown(payload)

    completed = run_validator(report, "--markdown", str(markdown))

    assert completed.returncode == 0
    assert "result=passed" in completed.stdout


def test_ci_artifacts_report_validator_rejects_failure_count_mismatch() -> None:
    report = write_report(report_payload(result="failed", failure_count=2, failures=["one failure"]))

    completed = run_validator(report)

    assert completed.returncode == 1
    assert "failure_count must match the number of failure entries" in completed.stdout


def test_ci_artifacts_report_validator_rejects_passed_report_with_failures() -> None:
    report = write_report(report_payload(result="passed", failure_count=1, failures=["unexpected failure"]))

    completed = run_validator(report)

    assert completed.returncode == 1
    assert "result='passed' requires failure_count=0" in completed.stdout


def test_ci_artifacts_report_validator_rejects_missing_markdown_file() -> None:
    report = write_report(report_payload())
    markdown = artifact_path("missing.md")

    completed = run_validator(report, "--markdown", str(markdown))

    assert completed.returncode == 1
    assert "Markdown report does not exist" in completed.stdout


def test_ci_artifacts_report_validator_rejects_mismatched_markdown() -> None:
    payload = report_payload()
    report = write_report(payload)
    markdown = write_markdown({**payload, "required_commands": 0})

    completed = run_validator(report, "--markdown", str(markdown))

    assert completed.returncode == 1
    assert "Markdown report is missing required text: - Required commands:" in completed.stdout


def test_ci_artifacts_report_validator_rejects_unsafe_workflow_path() -> None:
    report = write_report(report_payload(workflow="../ci.yml"))

    completed = run_validator(report)

    assert completed.returncode == 1
    assert "workflow must be a safe repository-relative path" in completed.stdout
