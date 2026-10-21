from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
VALID_RESULTS = {"passed", "failed", "pending", "unavailable"}
PENDING_STATUSES = {"queued", "in_progress", "waiting", "requested", "pending"}
VALID_STATUSES = {"completed", "unavailable", *PENDING_STATUSES}
VALID_SOURCES = {"github_api", "input_json", "local"}
REQUIRED_FIELDS = {
    "schema_version",
    "result",
    "status",
    "conclusion",
    "repo",
    "branch",
    "commit",
    "workflow_name",
    "run_id",
    "run_url",
    "run_head_sha",
    "run_head_branch",
    "source",
    "failure",
}


def resolve_repo_path(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def repo_display_path(path: Path) -> str:
    resolved = resolve_repo_path(path)
    return resolved.relative_to(ROOT).as_posix() if resolved.is_relative_to(ROOT) else resolved.as_posix()


def load_report(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("GitHub Actions report must be a JSON object.")
    return payload


def is_owner_repo(value: object) -> bool:
    return isinstance(value, str) and value.count("/") == 1 and all(part.strip() for part in value.split("/"))


def github_actions_run_url(repo: str, value: str) -> bool:
    return value.startswith(f"https://github.com/{repo}/actions/runs/")


def validate_report(payload: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    missing = sorted(REQUIRED_FIELDS - set(payload))
    if missing:
        failures.append(f"Report is missing fields: {', '.join(missing)}.")

    if payload.get("schema_version") != "1":
        failures.append("schema_version must be `1`.")
    result = payload.get("result")
    status = payload.get("status")
    conclusion = payload.get("conclusion")
    source = payload.get("source")
    repo = payload.get("repo")
    branch = payload.get("branch")
    commit = payload.get("commit")
    workflow_name = payload.get("workflow_name")
    run_id = payload.get("run_id")
    run_url = payload.get("run_url")
    run_head_sha = payload.get("run_head_sha")
    run_head_branch = payload.get("run_head_branch")
    failure = payload.get("failure")

    if result not in VALID_RESULTS:
        failures.append(f"result must be one of {sorted(VALID_RESULTS)}, got {result!r}.")
    if status not in VALID_STATUSES:
        failures.append(f"status must be one of {sorted(VALID_STATUSES)}, got {status!r}.")
    if source not in VALID_SOURCES:
        failures.append(f"source must be one of {sorted(VALID_SOURCES)}, got {source!r}.")
    if not is_owner_repo(repo):
        failures.append(f"repo must use owner/name form, got {repo!r}.")

    for field_name, value in (
        ("branch", branch),
        ("commit", commit),
        ("workflow_name", workflow_name),
        ("run_id", run_id),
        ("run_url", run_url),
        ("run_head_sha", run_head_sha),
        ("run_head_branch", run_head_branch),
        ("conclusion", conclusion),
        ("failure", failure),
    ):
        if not isinstance(value, str):
            failures.append(f"{field_name} must be a string.")

    if result == "passed" and (status != "completed" or conclusion != "success"):
        failures.append("result='passed' requires status='completed' and conclusion='success'.")
    if result == "failed" and (status != "completed" or not conclusion or conclusion == "success"):
        failures.append("result='failed' requires status='completed' and a non-success conclusion.")
    if result == "pending" and (status not in PENDING_STATUSES or conclusion):
        failures.append("result='pending' requires a pending status and an empty conclusion.")
    if result == "unavailable" and status != "unavailable":
        failures.append("result='unavailable' requires status='unavailable'.")
    if result == "unavailable" and not failure:
        failures.append("result='unavailable' requires failure text.")
    if result != "unavailable" and failure:
        failures.append(f"result={result!r} must not include failure text.")

    if isinstance(repo, str) and isinstance(run_url, str) and run_url and not github_actions_run_url(repo, run_url):
        failures.append(f"run_url must point to the repository Actions run, got {run_url!r}.")
    if result in {"passed", "failed", "pending"}:
        if not run_id:
            failures.append(f"result={result!r} requires run_id.")
        if not run_url:
            failures.append(f"result={result!r} requires run_url.")
        if not run_head_sha:
            failures.append(f"result={result!r} requires run_head_sha.")
        if branch != "unknown" and run_head_branch != branch:
            failures.append(f"run_head_branch={run_head_branch!r} must match branch={branch!r}.")
    return failures


def validate_markdown(path: Path, payload: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    text = path.read_text(encoding="utf-8")
    required_snippets = [
        "# GitHub Actions Status",
        f"- Result: `{payload.get('result')}`",
        f"- Status: `{payload.get('status')}`",
        f"- Repository: `{payload.get('repo')}`",
        f"- Branch: `{payload.get('branch')}`",
        f"- Commit: `{payload.get('commit')}`",
        f"- Workflow: `{payload.get('workflow_name')}`",
        f"- Source: `{payload.get('source')}`",
    ]
    for snippet in required_snippets:
        if snippet not in text:
            failures.append(f"Markdown report is missing required text: {snippet}")
    if payload.get("failure") and "## Failure" not in text:
        failures.append("Markdown report must include a Failure section when failure text exists.")
    return failures


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate GitHub Actions status JSON and Markdown reports.")
    parser.add_argument("--report-json", required=True, type=Path, help="Path to github_actions_status.json.")
    parser.add_argument("--markdown", type=Path, help="Optional github_actions_status.md report.")
    args = parser.parse_args()

    report_path = resolve_repo_path(args.report_json)
    failures = validate_report(load_report(report_path))
    markdown_path: Path | None = None
    if args.markdown:
        markdown_path = resolve_repo_path(args.markdown)
        if not markdown_path.exists():
            failures.append(f"Markdown report does not exist: {repo_display_path(markdown_path)}.")
        else:
            failures.extend(validate_markdown(markdown_path, load_report(report_path)))

    print("github_actions_report=checked")
    print(f"report_json={report_path}")
    if markdown_path:
        print(f"markdown={markdown_path}")
    print(f"failures={len(failures)}")
    if failures:
        print("result=failed")
        for failure in failures:
            print(f"failure: {failure}")
        raise SystemExit(1)
    print("result=passed")


if __name__ == "__main__":
    main()
