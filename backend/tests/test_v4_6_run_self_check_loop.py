import json
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

from scripts.run_self_check_loop import (
    ROOT,
    build_initial_command,
    next_artifact_from_command,
    run_loop,
)


def tmp_artifact_dir(name: str) -> Path:
    return Path(".pytest_tmp") / "run_self_check_loop_tests" / uuid4().hex / name


def test_self_check_loop_builds_initial_command() -> None:
    output_dir = Path(".pytest_tmp/self_check_loop")

    command = build_initial_command(
        mode="quick",
        output_dir=ROOT / output_dir,
        compare_latest=True,
        fail_on_regression=True,
    )

    assert command[:2] == [sys.executable, "scripts/run_self_check.py"]
    assert "--mode" in command
    assert "quick" in command
    assert "--output-dir" in command
    assert ".pytest_tmp/self_check_loop" in command
    assert "--compare-latest" in command
    assert "--fail-on-regression" in command


def test_self_check_loop_finds_next_artifact_for_self_check_command() -> None:
    artifact = next_artifact_from_command(
        "python scripts/run_self_check.py --mode full --output-dir .pytest_tmp/self_check_full --write-index --write-plan"
    )

    assert artifact == ROOT / ".pytest_tmp/self_check_full/self_check_next_command.json"


def test_self_check_loop_dry_run_writes_planned_report() -> None:
    output_dir = tmp_artifact_dir("self_check")
    report_path = tmp_artifact_dir("loop_report.json")
    markdown_path = tmp_artifact_dir("loop_report.md")

    report = run_loop(
        mode="quick",
        output_dir=output_dir,
        max_steps=2,
        execute_next=False,
        compare_latest=False,
        fail_on_regression=False,
        json_output=report_path,
        markdown_output=markdown_path,
        dry_run=True,
    )

    payload = json.loads((ROOT / report_path).read_text(encoding="utf-8"))
    markdown = (ROOT / markdown_path).read_text(encoding="utf-8")
    assert report["status"] == "planned"
    assert payload["status"] == "planned"
    assert payload["markdown_output"] == markdown_path.as_posix()
    assert payload["steps"] == []
    assert "scripts/run_self_check.py" in payload["initial_command"]
    assert "Self-Check Loop Report" in markdown
    assert "No next-command steps" in markdown


def test_self_check_loop_validate_only_stops_after_ready_step() -> None:
    output_dir = tmp_artifact_dir("self_check")
    report_path = tmp_artifact_dir("loop_report.json")
    markdown_path = tmp_artifact_dir("loop_report.md")
    safe_command = (
        "python scripts/run_self_check.py --mode quick --output-dir .pytest_tmp/self_check_loop_next "
        "--compare-latest --write-index --write-plan --fail-on-regression"
    )

    def fake_runner(command, **kwargs):
        assert kwargs["cwd"] == ROOT
        assert kwargs["check"] is True
        if command[1] == "scripts/run_self_check.py":
            target = ROOT / output_dir / "self_check_next_command.json"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(
                json.dumps(
                    {
                        "status": "available",
                        "priority": "P2",
                        "title": "Add a comparison baseline",
                        "command": safe_command,
                    }
                ),
                encoding="utf-8",
            )
        elif command[1] == "scripts/run_next_self_check.py":
            output = ROOT / Path(command[command.index("--json-output") + 1])
            markdown = ROOT / Path(command[command.index("--markdown-output") + 1])
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(
                json.dumps(
                    {
                        "schema_version": "1",
                        "status": "available",
                        "result": "ready",
                        "priority": "P2",
                        "title": "Add a comparison baseline",
                        "command": safe_command,
                        "next_command_json": ".pytest_tmp/self_check_loop/self_check_next_command.json",
                        "failure": "",
                    }
                ),
                encoding="utf-8",
            )
            markdown.write_text("# Next Self-Check Command", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0)

    report = run_loop(
        mode="quick",
        output_dir=output_dir,
        max_steps=3,
        execute_next=False,
        compare_latest=False,
        fail_on_regression=False,
        json_output=report_path,
        markdown_output=markdown_path,
        dry_run=False,
        runner=fake_runner,
    )

    markdown = (ROOT / markdown_path).read_text(encoding="utf-8")
    assert report["status"] == "passed"
    assert report["step_count"] == 1
    assert report["steps"][0]["result"] == "ready"
    assert report["steps"][0]["readiness_markdown"].endswith("next_self_check_step_1.md")
    assert "Step 1 Command" in markdown
    assert "next_self_check_step_1.md" in markdown
    assert safe_command in markdown


def test_self_check_loop_execute_advances_to_next_self_check_artifact() -> None:
    output_dir = tmp_artifact_dir("self_check")
    report_path = tmp_artifact_dir("loop_report.json")
    next_output = tmp_artifact_dir("next_self_check")
    safe_command = (
        f"python scripts/run_self_check.py --mode quick --output-dir {next_output.as_posix()} "
        "--compare-latest --write-index --write-plan --fail-on-regression"
    )

    def fake_runner(command, **kwargs):
        if command[1] == "scripts/run_self_check.py":
            target = ROOT / output_dir / "self_check_next_command.json"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(
                json.dumps(
                    {
                        "status": "available",
                        "priority": "P2",
                        "title": "Add a comparison baseline",
                        "command": safe_command,
                    }
                ),
                encoding="utf-8",
            )
        elif command[1] == "scripts/run_next_self_check.py":
            output = ROOT / Path(command[command.index("--json-output") + 1])
            markdown = ROOT / Path(command[command.index("--markdown-output") + 1])
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(
                json.dumps(
                    {
                        "schema_version": "1",
                        "status": "available",
                        "result": "executed",
                        "priority": "P2",
                        "title": "Add a comparison baseline",
                        "command": safe_command,
                        "next_command_json": (output_dir / "self_check_next_command.json").as_posix(),
                        "failure": "",
                    }
                ),
                encoding="utf-8",
            )
            markdown.write_text("# Next Self-Check Command", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0)

    report = run_loop(
        mode="quick",
        output_dir=output_dir,
        max_steps=1,
        execute_next=True,
        compare_latest=False,
        fail_on_regression=False,
        json_output=report_path,
        markdown_output=None,
        dry_run=False,
        runner=fake_runner,
    )

    assert report["step_count"] == 1
    assert report["steps"][0]["result"] == "executed"
    assert report["steps"][0]["readiness_markdown"].endswith("next_self_check_step_1.md")
    assert next_artifact_from_command(report["steps"][0]["command"]) == ROOT / next_output / "self_check_next_command.json"
