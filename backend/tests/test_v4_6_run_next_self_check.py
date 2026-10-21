import json
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

from scripts.run_next_self_check import command_tokens, parse_next_command, run_next_command


ROOT = Path(__file__).resolve().parents[2]
SAFE_COMMAND = (
    "python scripts/run_self_check.py --mode quick --output-dir .pytest_tmp/self_check "
    "--compare-latest --write-index --write-plan --fail-on-regression"
)


def artifact_path(name: str) -> Path:
    base = ROOT / ".pytest_tmp" / "run_next_self_check_tests" / uuid4().hex
    base.mkdir(parents=True, exist_ok=True)
    return base / name


def write_next_command(path: Path, payload: dict[str, object]) -> Path:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def run_cli(path: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "scripts/run_next_self_check.py", "--next-command-json", str(path), *extra],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )


def test_run_next_self_check_reports_ready_command_without_executing() -> None:
    path = write_next_command(
        artifact_path("self_check_next_command.json"),
        {
            "status": "available",
            "source_plan": ".pytest_tmp/self_check/self_check_improvement_plan.json",
            "priority": "P2",
            "title": "Add a comparison baseline",
            "command": SAFE_COMMAND,
        },
    )

    completed = run_cli(path)

    assert completed.returncode == 0
    assert "next_self_check=checked" in completed.stdout
    assert "status=available" in completed.stdout
    assert "result=ready" in completed.stdout
    assert SAFE_COMMAND in completed.stdout


def test_run_next_self_check_writes_json_output() -> None:
    path = write_next_command(
        artifact_path("self_check_next_command.json"),
        {
            "status": "available",
            "source_plan": ".pytest_tmp/self_check/self_check_improvement_plan.json",
            "priority": "P2",
            "title": "Add a comparison baseline",
            "command": SAFE_COMMAND,
        },
    )
    output = Path(".pytest_tmp/run_next_self_check_tests") / uuid4().hex / "next_self_check.json"

    completed = run_cli(path, "--json-output", output.as_posix())

    payload = json.loads((ROOT / output).read_text(encoding="utf-8"))
    assert completed.returncode == 0
    assert "json_output=" in completed.stdout
    assert payload["schema_version"] == "1"
    assert payload["status"] == "available"
    assert payload["result"] == "ready"
    assert payload["priority"] == "P2"
    assert payload["command"] == SAFE_COMMAND
    assert payload["failure"] == ""


def test_run_next_self_check_writes_markdown_output() -> None:
    path = write_next_command(
        artifact_path("self_check_next_command.json"),
        {
            "status": "available",
            "source_plan": ".pytest_tmp/self_check/self_check_improvement_plan.json",
            "priority": "P2",
            "title": "Add a comparison baseline",
            "command": SAFE_COMMAND,
        },
    )
    output = Path(".pytest_tmp/run_next_self_check_tests") / uuid4().hex / "next_self_check.md"

    completed = run_cli(path, "--markdown-output", output.as_posix())

    markdown = (ROOT / output).read_text(encoding="utf-8")
    assert completed.returncode == 0
    assert "markdown_output=" in completed.stdout
    assert "Next Self-Check Command" in markdown
    assert "Result: `ready`" in markdown
    assert SAFE_COMMAND in markdown


def test_run_next_self_check_rejects_markdown_output_outside_pytest_tmp() -> None:
    path = write_next_command(
        artifact_path("self_check_next_command.json"),
        {
            "status": "none",
            "source_plan": ".pytest_tmp/self_check/self_check_improvement_plan.json",
            "priority": "",
            "title": "",
            "command": "",
        },
    )

    completed = run_cli(path, "--markdown-output", "docs/next_self_check.md")

    assert completed.returncode == 1
    assert "result=failed" in completed.stdout
    assert "Markdown output must be a relative .pytest_tmp path" in completed.stdout


def test_run_next_self_check_rejects_json_output_outside_pytest_tmp() -> None:
    path = write_next_command(
        artifact_path("self_check_next_command.json"),
        {
            "status": "none",
            "source_plan": ".pytest_tmp/self_check/self_check_improvement_plan.json",
            "priority": "",
            "title": "",
            "command": "",
        },
    )

    completed = run_cli(path, "--json-output", "docs/next_self_check.json")

    assert completed.returncode == 1
    assert "result=failed" in completed.stdout
    assert "relative .pytest_tmp path" in completed.stdout


def test_run_next_self_check_accepts_empty_none_artifact() -> None:
    path = write_next_command(
        artifact_path("self_check_next_command.json"),
        {
            "status": "none",
            "source_plan": ".pytest_tmp/self_check/self_check_improvement_plan.json",
            "priority": "",
            "title": "",
            "command": "",
        },
    )

    completed = run_cli(path)

    assert completed.returncode == 0
    assert "status=none" in completed.stdout
    assert "result=none" in completed.stdout


def test_run_next_self_check_rejects_unsafe_command() -> None:
    path = write_next_command(
        artifact_path("self_check_next_command.json"),
        {
            "status": "available",
            "priority": "P0",
            "title": "Unsafe command",
            "command": "python scripts/seed_demo_data.py --reset",
        },
    )

    completed = run_cli(path)

    assert completed.returncode == 1
    assert "result=failed" in completed.stdout
    assert "command is unsafe" in completed.stdout


def test_run_next_self_check_writes_failed_json_output_for_unsafe_command() -> None:
    path = write_next_command(
        artifact_path("self_check_next_command.json"),
        {
            "status": "available",
            "priority": "P0",
            "title": "Unsafe command",
            "command": "python scripts/seed_demo_data.py --reset",
        },
    )
    output = Path(".pytest_tmp/run_next_self_check_tests") / uuid4().hex / "unsafe_next_self_check.json"

    completed = run_cli(path, "--json-output", output.as_posix())

    payload = json.loads((ROOT / output).read_text(encoding="utf-8"))
    assert completed.returncode == 1
    assert payload["status"] == "invalid"
    assert payload["result"] == "failed"
    assert "command is unsafe" in payload["failure"]


def test_run_next_self_check_writes_failed_markdown_output_for_unsafe_command() -> None:
    path = write_next_command(
        artifact_path("self_check_next_command.json"),
        {
            "status": "available",
            "priority": "P0",
            "title": "Unsafe command",
            "command": "python scripts/seed_demo_data.py --reset",
        },
    )
    output = Path(".pytest_tmp/run_next_self_check_tests") / uuid4().hex / "unsafe_next_self_check.md"

    completed = run_cli(path, "--markdown-output", output.as_posix())

    markdown = (ROOT / output).read_text(encoding="utf-8")
    assert completed.returncode == 1
    assert "Result: `failed`" in markdown
    assert "command is unsafe" in markdown


def test_run_next_command_execute_uses_current_python_without_shell() -> None:
    next_command = parse_next_command(
        {
            "status": "available",
            "priority": "P2",
            "title": "Add a comparison baseline",
            "command": SAFE_COMMAND,
        }
    )
    calls: list[tuple[list[str], dict[str, object]]] = []

    def fake_runner(tokens, **kwargs):
        calls.append((tokens, kwargs))
        return subprocess.CompletedProcess(tokens, 0)

    result = run_next_command(next_command, execute=True, runner=fake_runner)

    assert result == "executed"
    assert calls
    assert calls[0][0] == command_tokens(SAFE_COMMAND)
    assert calls[0][0][0] == sys.executable
    assert calls[0][1]["cwd"] == ROOT
    assert calls[0][1]["check"] is True
