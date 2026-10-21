import json
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

from scripts.check_ci_artifacts import REQUIRED_COMMANDS
from scripts.check_ci_artifacts import REQUIRED_QUALITY_ARTIFACT_PATHS
from scripts.check_ci_artifacts import REQUIRED_RELEASE_DEPENDENCIES
from scripts.check_ci_artifacts import REQUIRED_WORKFLOW_SNIPPETS
from scripts.check_ci_artifacts import WORKFLOW
from scripts.check_ci_artifacts import validate_workflow_text


ROOT = Path(__file__).resolve().parents[2]


def artifact_path(name: str) -> Path:
    base = ROOT / ".pytest_tmp" / "ci_artifacts_tests" / uuid4().hex
    base.mkdir(parents=True, exist_ok=True)
    return base / name


def test_ci_artifact_check_passes_current_v5_workflow() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/check_ci_artifacts.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "ci_artifacts=checked" in completed.stdout
    assert "result=passed" in completed.stdout
    assert "failures=0" in completed.stdout


def test_ci_artifact_check_writes_json_and_markdown_reports() -> None:
    json_output = artifact_path("ci_artifacts_contract.json")
    markdown_output = json_output.with_suffix(".md")

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/check_ci_artifacts.py",
            "--json-output",
            str(json_output),
            "--markdown-output",
            str(markdown_output),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    payload = json.loads(json_output.read_text(encoding="utf-8"))
    markdown = markdown_output.read_text(encoding="utf-8")
    assert "json_output=" in completed.stdout
    assert "markdown_output=" in completed.stdout
    assert payload["schema_version"] == "1"
    assert payload["result"] == "passed"
    assert payload["required_commands"] == len(REQUIRED_COMMANDS)
    assert payload["required_artifact_paths"] == len(REQUIRED_QUALITY_ARTIFACT_PATHS)
    assert payload["failure_count"] == 0
    assert "# CI Artifact Contract" in markdown
    assert "Result: `passed`" in markdown


def test_ci_artifact_check_writes_failed_report_for_missing_v5_evidence() -> None:
    workflow = artifact_path("broken-ci.yml")
    workflow.write_text(
        WORKFLOW.read_text(encoding="utf-8").replace(".pytest_tmp/v5_acceptance_gate.json", ""),
        encoding="utf-8",
    )
    json_output = artifact_path("ci_artifacts_contract_failed.json")

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/check_ci_artifacts.py",
            "--workflow",
            str(workflow),
            "--json-output",
            str(json_output),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    payload = json.loads(json_output.read_text(encoding="utf-8"))
    assert completed.returncode == 1
    assert payload["result"] == "failed"
    assert any("v5_acceptance_gate.json" in failure for failure in payload["failures"])


def test_ci_artifact_check_rejects_report_output_outside_pytest_tmp() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/check_ci_artifacts.py", "--json-output", "docs/ci_artifacts_contract.json"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 1
    assert "result=failed" in completed.stdout
    assert "JSON output must be written under .pytest_tmp" in completed.stdout


def test_ci_contract_requires_executable_v5_quality_evidence() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    for command in REQUIRED_COMMANDS:
        assert command in workflow
    for artifact_path in REQUIRED_QUALITY_ARTIFACT_PATHS:
        assert artifact_path in workflow
    for snippet in REQUIRED_WORKFLOW_SNIPPETS:
        assert snippet in workflow


def test_ci_contract_rejects_missing_critical_commands() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    critical = (
        "python scripts/verify_v5_migration.py --roundtrip",
        "npm run test:unit",
        "python scripts/run_demo_e2e.py --strict --database-path .pytest_tmp/v5_ci_showcase_live_e2e.db",
        "python scripts/check_release.py --version V5.7",
    )

    for command in critical:
        failures = validate_workflow_text(workflow.replace(command, ""))
        assert any(command in failure for failure in failures)


def test_ci_contract_rejects_quality_steps_in_the_wrong_order() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    before = "python -m alembic current"
    after = "python scripts/verify_v5_migration.py --roundtrip"
    broken = workflow.replace(before, "__BEFORE__").replace(after, before).replace("__BEFORE__", after)

    failures = validate_workflow_text(broken)

    assert any("alembic" in failure and "verify_v5_migration" in failure for failure in failures)


def test_release_job_waits_for_every_executable_quality_job() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    dependency_line = f"needs: [{', '.join(REQUIRED_RELEASE_DEPENDENCIES)}]"

    assert dependency_line in workflow

    broken = workflow.replace(dependency_line, "needs: [backend, frontend]")
    failures = validate_workflow_text(broken)

    assert any("quality-and-release" in failure and "browser-e2e" in failure for failure in failures)


def test_release_job_validates_the_downloaded_backend_evaluation_before_packaging() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    required = (
        "actions/download-artifact@v4",
        "name: v5-evaluation-evidence",
        "path: .pytest_tmp",
        "python scripts/check_v5_acceptance.py --report .pytest_tmp/v5_evaluation_report.json",
        "python scripts/release.py --version V5.7 --dry-run",
        "name: suzhi-evidence-os-v5.2",
    )

    cursor = workflow.index("  quality-and-release:")
    positions = []
    for snippet in required:
        cursor = workflow.index(snippet, cursor + 1)
        positions.append(cursor)
    assert positions == sorted(positions)

    failures = validate_workflow_text(workflow.replace("actions/download-artifact@v4", "actions/cache@v4"))

    assert any("download" in failure and "v5-evaluation-evidence" in failure for failure in failures)


def test_release_artifact_upload_is_not_forced_after_a_failed_gate() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    upload = "- uses: actions/upload-artifact@v4\n        with:\n          name: suzhi-evidence-os-v5.2"

    assert upload in workflow
    for condition in ("always()", "${{ always() }}", "failure()"):
        forced_upload = (
            f"- uses: actions/upload-artifact@v4\n        if: {condition}\n"
            "        with:\n          name: suzhi-evidence-os-v5.2"
        )
        failures = validate_workflow_text(workflow.replace(upload, forced_upload))

        assert any("release artifact" in failure and "failed gate" in failure for failure in failures)


def test_ci_contract_does_not_require_legacy_process_theater() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "run_self_check.py" not in workflow
    assert all("self_check" not in command for command in REQUIRED_COMMANDS)
    assert validate_workflow_text(workflow) == []
