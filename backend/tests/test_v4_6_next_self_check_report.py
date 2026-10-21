import json
import subprocess
import sys
from pathlib import Path
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[2]
SAFE_COMMAND = (
    "python scripts/run_self_check.py --mode quick --output-dir .pytest_tmp/self_check "
    "--compare-latest --write-index --write-plan --fail-on-regression"
)


def artifact_dir() -> Path:
    base = ROOT / ".pytest_tmp" / "next_self_check_report_tests" / uuid4().hex
    base.mkdir(parents=True, exist_ok=True)
    return base


def repo_path(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def write_report(base: Path, payload: dict[str, object]) -> Path:
    path = base / "next_self_check.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def valid_report(base: Path) -> dict[str, object]:
    markdown = base / "next_self_check.md"
    markdown.write_text("# Next Self-Check Command", encoding="utf-8")
    return {
        "schema_version": "1",
        "status": "available",
        "result": "ready",
        "priority": "P2",
        "title": "Add a comparison baseline",
        "command": SAFE_COMMAND,
        "next_command_json": repo_path(base / "self_check_next_command.json"),
        "markdown_output": repo_path(markdown),
        "failure": "",
    }


def run_validator(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "scripts/check_next_self_check_report.py", "--report-json", str(path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )


def test_next_self_check_report_validator_accepts_ready_report() -> None:
    base = artifact_dir()
    report = write_report(base, valid_report(base))

    completed = run_validator(report)

    assert completed.returncode == 0
    assert "next_self_check_report=checked" in completed.stdout
    assert "failures=0" in completed.stdout
    assert "result=passed" in completed.stdout


def test_next_self_check_report_validator_accepts_none_report() -> None:
    base = artifact_dir()
    report = write_report(
        base,
        {
            "schema_version": "1",
            "status": "none",
            "result": "none",
            "priority": "",
            "title": "",
            "command": "",
            "next_command_json": repo_path(base / "self_check_next_command.json"),
            "markdown_output": "",
            "failure": "",
        },
    )

    completed = run_validator(report)

    assert completed.returncode == 0
    assert "result=passed" in completed.stdout


def test_next_self_check_report_validator_rejects_unsafe_command() -> None:
    base = artifact_dir()
    payload = valid_report(base)
    payload["command"] = "python scripts/seed_demo_data.py --reset"
    report = write_report(base, payload)

    completed = run_validator(report)

    assert completed.returncode == 1
    assert "command is unsafe" in completed.stdout


def test_next_self_check_report_validator_rejects_missing_markdown() -> None:
    base = artifact_dir()
    payload = valid_report(base)
    payload["markdown_output"] = repo_path(base / "missing.md")
    report = write_report(base, payload)

    completed = run_validator(report)

    assert completed.returncode == 1
    assert "markdown_output does not exist" in completed.stdout


def test_next_self_check_report_validator_rejects_invalid_result_status_pair() -> None:
    base = artifact_dir()
    payload = valid_report(base)
    payload["status"] = "none"
    report = write_report(base, payload)

    completed = run_validator(report)

    assert completed.returncode == 1
    assert "requires status='available'" in completed.stdout
