import json
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

from scripts.check_ci_artifacts import REQUIRED_COMMANDS
from scripts.check_ci_artifacts import REQUIRED_QUALITY_ARTIFACT_PATHS
from scripts.check_ci_artifacts import REQUIRED_WORKFLOW_SNIPPETS
from scripts.check_ci_artifacts import WORKFLOW
from scripts.check_ci_artifacts import validate_workflow_text


ROOT = Path(__file__).resolve().parents[2]


def artifact_path(name: str) -> Path:
    base = ROOT / ".pytest_tmp" / "ci_artifacts_tests" / uuid4().hex
    base.mkdir(parents=True, exist_ok=True)
    return base / name


def test_ci_artifact_check_passes_current_workflow() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/check_ci_artifacts.py"],
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


def test_ci_artifact_check_writes_failed_report_for_broken_workflow() -> None:
    workflow = artifact_path("broken-ci.yml")
    workflow.write_text(WORKFLOW.read_text(encoding="utf-8").replace(".pytest_tmp/github_actions_status.md", ""), encoding="utf-8")
    json_output = artifact_path("ci_artifacts_contract_failed.json")
    markdown_output = json_output.with_suffix(".md")

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/check_ci_artifacts.py",
            "--workflow",
            str(workflow),
            "--json-output",
            str(json_output),
            "--markdown-output",
            str(markdown_output),
        ],
        text=True,
        capture_output=True,
    )

    payload = json.loads(json_output.read_text(encoding="utf-8"))
    markdown = markdown_output.read_text(encoding="utf-8")
    assert completed.returncode == 1
    assert payload["result"] == "failed"
    assert payload["failure_count"] > 0
    assert "github_actions_status.md" in "\n".join(payload["failures"])
    assert "Result: `failed`" in markdown


def test_ci_artifact_check_rejects_report_output_outside_pytest_tmp() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/check_ci_artifacts.py", "--json-output", "docs/ci_artifacts_contract.json"],
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 1
    assert "result=failed" in completed.stdout
    assert "JSON output must be written under .pytest_tmp" in completed.stdout


def test_ci_artifact_check_requires_loop_step_markdown_upload() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    broken = workflow.replace(".pytest_tmp/self_check_loop/next_self_check_step_*.md", "")

    failures = validate_workflow_text(broken)

    assert any("next_self_check_step_*.md" in failure for failure in failures)


def test_ci_artifact_check_requires_all_quality_paths() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    for artifact_path in REQUIRED_QUALITY_ARTIFACT_PATHS:
        assert artifact_path in workflow


def test_ci_artifact_check_requires_release_to_full_handoff_command() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    handoff_command = (
        "python scripts/run_next_self_check.py --next-command-json "
        ".pytest_tmp/self_check_release/self_check_next_command.json --json-output "
        ".pytest_tmp/self_check_release/next_self_check_full_ready.json --markdown-output "
        ".pytest_tmp/self_check_release/next_self_check_full_ready.md"
    )
    broken = workflow.replace(handoff_command, "")

    failures = validate_workflow_text(broken)

    assert handoff_command in REQUIRED_COMMANDS
    assert any("next_self_check_full_ready.json" in failure for failure in failures)


def test_ci_artifact_check_requires_release_to_full_handoff_upload() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    broken = workflow.replace(".pytest_tmp/self_check_release/next_self_check_full_ready.md", "")

    failures = validate_workflow_text(broken)

    assert any("next_self_check_full_ready.md" in failure for failure in failures)


def test_ci_artifact_check_requires_github_actions_status_command() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    command = (
        "python scripts/check_github_actions.py --json-output .pytest_tmp/github_actions_status.json "
        "--markdown-output .pytest_tmp/github_actions_status.md"
    )
    broken = workflow.replace(command, "")

    failures = validate_workflow_text(broken)

    assert command in REQUIRED_COMMANDS
    assert any("github_actions_status.json" in failure for failure in failures)


def test_ci_artifact_check_requires_github_actions_status_uploads() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    broken = workflow.replace(".pytest_tmp/github_actions_status.md", "")

    failures = validate_workflow_text(broken)

    assert any("github_actions_status.md" in failure for failure in failures)


def test_ci_artifact_check_requires_github_actions_report_validator() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    command = (
        "python scripts/check_github_actions_report.py --report-json .pytest_tmp/github_actions_status.json "
        "--markdown .pytest_tmp/github_actions_status.md"
    )
    broken = workflow.replace(command, "")

    failures = validate_workflow_text(broken)

    assert command in REQUIRED_COMMANDS
    assert any("check_github_actions_report.py" in failure for failure in failures)


def test_ci_artifact_check_requires_contract_report_validator() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    command = (
        "python scripts/check_ci_artifacts_report.py --report-json .pytest_tmp/ci_artifacts_contract.json "
        "--markdown .pytest_tmp/ci_artifacts_contract.md"
    )
    broken = workflow.replace(command, "")

    failures = validate_workflow_text(broken)

    assert command in REQUIRED_COMMANDS
    assert any("check_ci_artifacts_report.py" in failure for failure in failures)


def test_ci_artifact_check_requires_actions_read_permission_and_token_env() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    for snippet in REQUIRED_WORKFLOW_SNIPPETS:
        broken = workflow.replace(snippet, "")
        failures = validate_workflow_text(broken)
        assert any(snippet in failure for failure in failures)


def test_ci_artifact_check_rejects_github_actions_validator_before_generator() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    generator = (
        "      - run: python scripts/check_github_actions.py --json-output "
        ".pytest_tmp/github_actions_status.json --markdown-output .pytest_tmp/github_actions_status.md\n"
        "        env:\n"
        "          GITHUB_TOKEN: ${{ github.token }}"
    )
    validator = (
        "      - run: python scripts/check_github_actions_report.py --report-json "
        ".pytest_tmp/github_actions_status.json --markdown .pytest_tmp/github_actions_status.md"
    )
    broken = workflow.replace(f"{generator}\n{validator}", f"{validator}\n{generator}")

    failures = validate_workflow_text(broken)

    assert any("check_github_actions.py" in failure and "check_github_actions_report.py" in failure for failure in failures)


def test_ci_artifact_check_rejects_release_handoff_before_release_comparison() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    release_compare = (
        "      - run: python scripts/run_self_check.py --mode release --output-dir "
        ".pytest_tmp/self_check_release --compare-latest --write-index --write-plan --fail-on-regression"
    )
    full_ready = (
        "      - run: python scripts/run_next_self_check.py --next-command-json "
        ".pytest_tmp/self_check_release/self_check_next_command.json --json-output "
        ".pytest_tmp/self_check_release/next_self_check_full_ready.json --markdown-output "
        ".pytest_tmp/self_check_release/next_self_check_full_ready.md"
    )
    broken = workflow.replace(f"{release_compare}\n{full_ready}", f"{full_ready}\n{release_compare}")

    failures = validate_workflow_text(broken)

    assert any("self_check_release --compare-latest" in failure for failure in failures)


def test_ci_artifact_check_rejects_quality_upload_before_status_validator() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    upload = "      - uses: actions/upload-artifact@v4\n        if: always()\n        with:\n          name: quality-gate-json"
    validator = (
        "      - run: python scripts/check_github_actions_report.py --report-json "
        ".pytest_tmp/github_actions_status.json --markdown .pytest_tmp/github_actions_status.md"
    )
    broken = workflow.replace(upload, "__UPLOAD__").replace(validator, upload).replace("__UPLOAD__", validator)

    failures = validate_workflow_text(broken)

    assert any("name: quality-gate-json" in failure for failure in failures)


def test_ci_artifact_check_rejects_quality_upload_before_contract_report() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    upload = "      - uses: actions/upload-artifact@v4\n        if: always()\n        with:\n          name: quality-gate-json"
    contract = (
        "      - run: python scripts/check_ci_artifacts.py --json-output .pytest_tmp/ci_artifacts_contract.json "
        "--markdown-output .pytest_tmp/ci_artifacts_contract.md"
    )
    broken = workflow.replace(upload, "__UPLOAD__").replace(contract, upload).replace("__UPLOAD__", contract)

    failures = validate_workflow_text(broken)

    assert any("ci_artifacts_contract.json" in failure and "name: quality-gate-json" in failure for failure in failures)


def test_ci_artifact_check_rejects_quality_upload_before_contract_report_validator() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    upload = "      - uses: actions/upload-artifact@v4\n        if: always()\n        with:\n          name: quality-gate-json"
    validator = (
        "      - run: python scripts/check_ci_artifacts_report.py --report-json "
        ".pytest_tmp/ci_artifacts_contract.json --markdown .pytest_tmp/ci_artifacts_contract.md"
    )
    broken = workflow.replace(upload, "__UPLOAD__").replace(validator, upload).replace("__UPLOAD__", validator)

    failures = validate_workflow_text(broken)

    assert any("check_ci_artifacts_report.py" in failure and "name: quality-gate-json" in failure for failure in failures)
