import json
import shutil
import subprocess
import sys

from scripts.run_self_check import (
    build_commands,
    build_paths,
    latest_baseline_path,
    next_command_from_plan,
    prepare_latest_baseline,
    write_manifest_artifacts,
    write_next_command_artifacts,
)


def test_run_self_check_builds_quick_artifact_commands(tmp_path) -> None:
    paths = build_paths(tmp_path / "self_check", "quick")
    commands = build_commands("quick", paths, require_passed=True)

    assert commands[0][:3] == [sys.executable, "scripts/check_all.py", "--quick"]
    assert "--json-report" in commands[0]
    assert commands[1][:2] == [sys.executable, "scripts/summarize_quality_report.py"]
    assert commands[2][:2] == [sys.executable, "scripts/check_quality_artifacts.py"]
    assert "--require-passed" in commands[2]
    assert str(paths.json_report) in commands[0]
    assert str(paths.markdown_summary) in commands[1]


def test_run_self_check_builds_full_artifact_commands(tmp_path) -> None:
    paths = build_paths(tmp_path / "self_check_full", "full")
    commands = build_commands("full", paths, require_passed=True, write_index=True, write_plan=True)

    assert commands[0][:3] == [sys.executable, "scripts/check_all.py", "--full"]
    assert str(paths.json_report) in commands[0]
    assert str(paths.markdown_summary) in commands[1]
    assert "--expected-mode" in commands[2]
    assert "full" in commands[2]
    assert commands[-1][:2] == [sys.executable, "scripts/check_improvement_plan_commands.py"]


def test_run_self_check_builds_optional_comparison_command(tmp_path) -> None:
    paths = build_paths(tmp_path / "self_check", "quick")
    baseline = tmp_path / "baseline.json"
    commands = build_commands("quick", paths, require_passed=True, compare_to=baseline, fail_on_regression=True)
    comparison = commands[-1]

    assert comparison[:2] == [sys.executable, "scripts/compare_quality_reports.py"]
    assert "--base" in comparison
    assert "--current" in comparison
    assert "--json-output" in comparison
    assert "--fail-on-regression" in comparison
    assert str(paths.comparison_report) in comparison
    assert str(paths.comparison_json) in comparison


def test_run_self_check_prepares_latest_baseline_from_existing_report(tmp_path) -> None:
    paths = build_paths(tmp_path / "self_check", "quick")
    paths.output_dir.mkdir(parents=True)
    paths.json_report.write_text('{"mode":"quick","status":"passed"}', encoding="utf-8")

    baseline = prepare_latest_baseline(paths, "quick", dry_run=False)

    assert baseline == latest_baseline_path(paths, "quick")
    assert baseline is not None
    assert not baseline.is_relative_to(paths.output_dir)
    assert baseline.read_text(encoding="utf-8") == '{"mode":"quick","status":"passed"}'


def test_run_self_check_latest_baseline_survives_output_dir_cleanup(tmp_path) -> None:
    paths = build_paths(tmp_path / "self_check_full", "full")
    paths.output_dir.mkdir(parents=True)
    paths.json_report.write_text('{"mode":"full","status":"passed"}', encoding="utf-8")

    baseline = prepare_latest_baseline(paths, "full", dry_run=False)
    shutil.rmtree(paths.output_dir)

    assert baseline is not None
    assert baseline.exists()
    assert baseline.read_text(encoding="utf-8") == '{"mode":"full","status":"passed"}'


def test_run_self_check_skips_latest_baseline_when_no_previous_report(tmp_path) -> None:
    paths = build_paths(tmp_path / "self_check", "quick")
    paths.output_dir.mkdir(parents=True)

    assert prepare_latest_baseline(paths, "quick", dry_run=False) is None


def test_run_self_check_builds_optional_history_index_command(tmp_path) -> None:
    paths = build_paths(tmp_path / "self_check", "quick")
    commands = build_commands("quick", paths, require_passed=True, write_index=True)
    index_command = commands[-1]

    assert index_command[:2] == [sys.executable, "scripts/index_self_checks.py"]
    assert "--input-dir" in index_command
    assert "--markdown-output" in index_command
    assert str(paths.output_dir) in index_command
    assert str(paths.history_index) in index_command
    assert str(paths.history_markdown) in index_command


def test_run_self_check_builds_optional_improvement_plan_command(tmp_path) -> None:
    paths = build_paths(tmp_path / "self_check", "quick")
    commands = build_commands("quick", paths, require_passed=True, write_plan=True)
    plan_command = commands[-2]
    command_validation = commands[-1]

    assert plan_command[:2] == [sys.executable, "scripts/plan_self_check_improvements.py"]
    assert "--index" in plan_command
    assert "--json-output" in plan_command
    assert str(paths.history_index) in plan_command
    assert str(paths.improvement_plan) in plan_command
    assert str(paths.improvement_json) in plan_command
    assert command_validation[:2] == [sys.executable, "scripts/check_improvement_plan_commands.py"]
    assert str(paths.improvement_json) in command_validation


def test_run_self_check_reads_next_command_from_improvement_plan(tmp_path) -> None:
    plan = tmp_path / "plan.json"
    plan.write_text(
        """
{
  "items": [
    {"priority": "P0", "title": "Manual", "command": ""},
    {"priority": "P2", "title": "Add a comparison baseline", "command": "python scripts/run_self_check.py --mode quick --output-dir .pytest_tmp/self_check --compare-latest --write-index --write-plan --fail-on-regression"}
  ]
}
""".strip(),
        encoding="utf-8",
    )

    next_command = next_command_from_plan(plan)

    assert next_command is not None
    assert next_command["priority"] == "P2"
    assert next_command["title"] == "Add a comparison baseline"
    assert "--compare-latest" in next_command["command"]


def test_run_self_check_writes_next_command_artifacts(tmp_path) -> None:
    paths = build_paths(tmp_path / "self_check", "quick")
    paths.output_dir.mkdir(parents=True)
    paths.improvement_json.write_text('{"items":[]}', encoding="utf-8")

    write_next_command_artifacts(
        paths,
        {
            "priority": "P2",
            "title": "Add a comparison baseline",
            "command": "python scripts/run_self_check.py --mode quick --output-dir .pytest_tmp/self_check --compare-latest --write-index --write-plan --fail-on-regression",
        },
    )

    payload = json.loads(paths.next_command_json.read_text(encoding="utf-8"))
    markdown = paths.next_command_markdown.read_text(encoding="utf-8")
    assert payload["status"] == "available"
    assert payload["priority"] == "P2"
    assert payload["title"] == "Add a comparison baseline"
    assert "--compare-latest" in payload["command"]
    assert "Self-Check Next Command" in markdown
    assert "```powershell" in markdown


def test_run_self_check_writes_empty_next_command_artifact(tmp_path) -> None:
    paths = build_paths(tmp_path / "self_check", "quick")
    paths.output_dir.mkdir(parents=True)
    paths.improvement_json.write_text('{"items":[]}', encoding="utf-8")

    write_next_command_artifacts(paths, None)

    payload = json.loads(paths.next_command_json.read_text(encoding="utf-8"))
    markdown = paths.next_command_markdown.read_text(encoding="utf-8")
    assert payload["status"] == "none"
    assert payload["command"] == ""
    assert "- Status: `none`" in markdown


def test_run_self_check_writes_manifest_artifacts(tmp_path) -> None:
    paths = build_paths(tmp_path / "self_check", "quick")
    paths.output_dir.mkdir(parents=True)
    paths.json_report.write_text('{"mode":"quick"}', encoding="utf-8")
    paths.markdown_summary.write_text("# Summary", encoding="utf-8")
    paths.improvement_json.write_text('{"items":[]}', encoding="utf-8")
    paths.next_command_json.write_text('{"status":"available"}', encoding="utf-8")

    write_manifest_artifacts(
        paths,
        mode="quick",
        compare_state="skipped_no_previous_report",
        next_command={
            "priority": "P2",
            "title": "Add a comparison baseline",
            "command": "python scripts/run_self_check.py --mode quick --output-dir .pytest_tmp/self_check --compare-latest --write-index --write-plan --fail-on-regression",
        },
    )

    payload = json.loads(paths.manifest_json.read_text(encoding="utf-8"))
    markdown = paths.manifest_markdown.read_text(encoding="utf-8")
    assert payload["status"] == "passed"
    assert payload["mode"] == "quick"
    assert payload["compare_state"] == "skipped_no_previous_report"
    assert payload["artifact_count"] == 10
    assert payload["next_command"]["priority"] == "P2"
    assert any(item["name"] == "quality_json" and item["exists"] for item in payload["artifacts"])
    assert "Self-Check Manifest" in markdown
    assert "next_command_json" in markdown


def test_run_self_check_dry_run_prints_artifact_paths(tmp_path) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_self_check.py",
            "--mode",
            "release",
            "--output-dir",
            str(tmp_path / "artifacts"),
            "--dry-run",
            "--write-index",
            "--write-plan",
        ],
        text=True,
        capture_output=True,
        check=True,
    )

    assert "self_check=planned" in completed.stdout
    assert "mode=release" in completed.stdout
    assert "check_all_release.json" in completed.stdout
    assert "check_all_release_summary.md" in completed.stdout
    assert "self_check_index.json" in completed.stdout
    assert "self_check_index.md" in completed.stdout
    assert "self_check_improvement_plan.md" in completed.stdout
    assert "self_check_improvement_plan.json" in completed.stdout
    assert "check_improvement_plan_commands.py" in completed.stdout
    assert "next_command=unavailable reason=dry_run" in completed.stdout
    assert "self_check_next_command.json" in completed.stdout
    assert "self_check_next_command.md" in completed.stdout
    assert "self_check_manifest.json" in completed.stdout
    assert "self_check_manifest.md" in completed.stdout


def test_run_self_check_full_dry_run_prints_full_artifact_paths(tmp_path) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_self_check.py",
            "--mode",
            "full",
            "--output-dir",
            str(tmp_path / "full_artifacts"),
            "--dry-run",
            "--write-index",
            "--write-plan",
        ],
        text=True,
        capture_output=True,
        check=True,
    )

    assert "self_check=planned" in completed.stdout
    assert "mode=full" in completed.stdout
    assert "check_all_full.json" in completed.stdout
    assert "check_all_full_summary.md" in completed.stdout
    assert "self_check_manifest.json" in completed.stdout


def test_run_self_check_dry_run_auto_compares_existing_report(tmp_path) -> None:
    output_dir = tmp_path / "artifacts"
    output_dir.mkdir()
    (output_dir / "check_all_quick.json").write_text('{"mode":"quick","status":"passed"}', encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_self_check.py",
            "--mode",
            "quick",
            "--output-dir",
            str(output_dir),
            "--compare-latest",
            "--write-plan",
            "--dry-run",
        ],
        text=True,
        capture_output=True,
        check=True,
    )

    assert "auto_compare=enabled" in completed.stdout
    assert "baseline_check_all_quick.json" in completed.stdout
    assert "check_all_quick_comparison.md" in completed.stdout
    assert "check_all_quick_comparison.json" in completed.stdout
    assert "--comparison" in completed.stdout


def test_run_self_check_dry_run_skips_auto_compare_without_previous_report(tmp_path) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_self_check.py",
            "--mode",
            "quick",
            "--output-dir",
            str(tmp_path / "artifacts"),
            "--compare-latest",
            "--dry-run",
        ],
        text=True,
        capture_output=True,
        check=True,
    )

    assert "auto_compare=skipped reason=no_previous_report" in completed.stdout
    assert "comparison_report=" not in completed.stdout


def test_run_self_check_rejects_missing_comparison_baseline(tmp_path) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_self_check.py",
            "--mode",
            "quick",
            "--output-dir",
            str(tmp_path / "artifacts"),
            "--compare-to",
            str(tmp_path / "missing.json"),
        ],
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 1
    assert "Comparison baseline does not exist" in completed.stderr
