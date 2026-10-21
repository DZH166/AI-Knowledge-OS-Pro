import json
import subprocess
import sys
from pathlib import Path
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[2]
SAFE_COMMAND = (
    "python scripts/run_self_check.py --mode quick --output-dir .pytest_tmp/self_check_loop "
    "--compare-latest --write-index --write-plan --fail-on-regression"
)


def artifact_dir() -> Path:
    base = ROOT / ".pytest_tmp" / "self_check_loop_report_tests" / uuid4().hex
    base.mkdir(parents=True, exist_ok=True)
    return base


def repo_path(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def write_report(base: Path, payload: dict[str, object]) -> Path:
    path = base / "self_check_loop.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def readiness_file(base: Path, name: str = "next_self_check_step_1.json") -> Path:
    path = base / name
    path.write_text('{"result":"ready"}', encoding="utf-8")
    return path


def valid_report(base: Path) -> dict[str, object]:
    readiness = readiness_file(base)
    readiness_markdown = base / "next_self_check_step_1.md"
    readiness_markdown.write_text("# Next Self-Check Command", encoding="utf-8")
    markdown = base / "self_check_loop.md"
    markdown.write_text("# Self-Check Loop Report", encoding="utf-8")
    return {
        "schema_version": "1",
        "status": "passed",
        "mode": "quick",
        "output_dir": repo_path(base),
        "max_steps": 1,
        "execute_next": False,
        "dry_run": False,
        "initial_command": "python scripts/run_self_check.py --mode quick --output-dir .pytest_tmp/self_check_loop --write-index --write-plan",
        "markdown_output": repo_path(markdown),
        "steps": [
            {
                "index": 1,
                "next_command_json": repo_path(base / "self_check_next_command.json"),
                "readiness_json": repo_path(readiness),
                "readiness_markdown": repo_path(readiness_markdown),
                "result": "ready",
                "priority": "P2",
                "title": "Add a comparison baseline",
                "command": SAFE_COMMAND,
                "failure": "",
            }
        ],
        "step_count": 1,
    }


def run_validator(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "scripts/check_self_check_loop_report.py", "--loop-json", str(path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )


def test_self_check_loop_report_validator_accepts_valid_report() -> None:
    base = artifact_dir()
    report = write_report(base, valid_report(base))

    completed = run_validator(report)

    assert completed.returncode == 0
    assert "self_check_loop_report=checked" in completed.stdout
    assert "failures=0" in completed.stdout
    assert "result=passed" in completed.stdout


def test_self_check_loop_report_validator_accepts_planned_dry_run() -> None:
    base = artifact_dir()
    report = write_report(
        base,
        {
            "schema_version": "1",
            "status": "planned",
            "mode": "quick",
            "output_dir": repo_path(base),
            "max_steps": 1,
            "execute_next": False,
            "dry_run": True,
            "initial_command": "python scripts/run_self_check.py --mode quick --output-dir .pytest_tmp/self_check_loop --write-index --write-plan",
            "steps": [],
        },
    )

    completed = run_validator(report)

    assert completed.returncode == 0
    assert "result=passed" in completed.stdout


def test_self_check_loop_report_validator_rejects_step_count_mismatch() -> None:
    base = artifact_dir()
    payload = valid_report(base)
    payload["step_count"] = 3
    report = write_report(base, payload)

    completed = run_validator(report)

    assert completed.returncode == 1
    assert "step_count=3" in completed.stdout
    assert "result=failed" in completed.stdout


def test_self_check_loop_report_validator_rejects_unsafe_step_command() -> None:
    base = artifact_dir()
    payload = valid_report(base)
    payload["steps"][0]["command"] = "python scripts/seed_demo_data.py --reset"  # type: ignore[index]
    report = write_report(base, payload)

    completed = run_validator(report)

    assert completed.returncode == 1
    assert "Step 1 command is unsafe" in completed.stdout


def test_self_check_loop_report_validator_rejects_unsafe_paths() -> None:
    base = artifact_dir()
    payload = valid_report(base)
    payload["output_dir"] = "docs/self_check_loop"
    report = write_report(base, payload)

    completed = run_validator(report)

    assert completed.returncode == 1
    assert "output_dir must be a relative .pytest_tmp path" in completed.stdout


def test_self_check_loop_report_validator_rejects_missing_readiness_file() -> None:
    base = artifact_dir()
    payload = valid_report(base)
    payload["steps"][0]["readiness_json"] = repo_path(base / "missing.json")  # type: ignore[index]
    report = write_report(base, payload)

    completed = run_validator(report)

    assert completed.returncode == 1
    assert "readiness_json does not exist" in completed.stdout


def test_self_check_loop_report_validator_rejects_missing_readiness_markdown() -> None:
    base = artifact_dir()
    payload = valid_report(base)
    payload["steps"][0]["readiness_markdown"] = repo_path(base / "missing.md")  # type: ignore[index]
    report = write_report(base, payload)

    completed = run_validator(report)

    assert completed.returncode == 1
    assert "readiness_markdown does not exist" in completed.stdout


def test_self_check_loop_report_validator_rejects_missing_markdown_output() -> None:
    base = artifact_dir()
    payload = valid_report(base)
    payload["markdown_output"] = repo_path(base / "missing.md")
    report = write_report(base, payload)

    completed = run_validator(report)

    assert completed.returncode == 1
    assert "markdown_output does not exist" in completed.stdout
