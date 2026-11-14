from __future__ import annotations

import argparse
from dataclasses import asdict
from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any
from urllib.error import HTTPError
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request
from urllib.request import urlopen


def _repo_root() -> Path:
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "backend").exists() and (candidate / "frontend").exists():
            return candidate
    raise RuntimeError("Repository root not found.")


ROOT = _repo_root()
DEFAULT_WORKFLOW_NAME = "CI"


@dataclass(frozen=True)
class GitHubActionsReport:
    schema_version: str
    result: str
    status: str
    conclusion: str
    repo: str
    branch: str
    commit: str
    workflow_name: str
    run_id: str
    run_url: str
    run_head_sha: str
    run_head_branch: str
    source: str
    failure: str


def git_output(args: list[str]) -> str | None:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    value = completed.stdout.strip()
    return value or None


def parse_github_repo(remote: str) -> str | None:
    value = remote.strip()
    if value.startswith("https://github.com/"):
        repo = value.removeprefix("https://github.com/")
    elif value.startswith("http://github.com/"):
        repo = value.removeprefix("http://github.com/")
    elif value.startswith("git@github.com:"):
        repo = value.removeprefix("git@github.com:")
    else:
        return None
    repo = repo.removesuffix(".git").strip("/")
    if repo.count("/") != 1:
        return None
    return repo


def default_repo() -> str:
    remote = git_output(["remote", "get-url", "origin"]) or ""
    return parse_github_repo(remote) or "DZH166/AI-Knowledge-OS-Pro"


def default_branch() -> str:
    return git_output(["branch", "--show-current"]) or os.environ.get("GITHUB_REF_NAME") or "unknown"


def default_commit() -> str:
    return git_output(["rev-parse", "HEAD"]) or os.environ.get("GITHUB_SHA") or "unknown"


def auth_token() -> str:
    return os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""


def api_headers(token: str) -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "AI-Knowledge-OS-Pro-self-check",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def fetch_actions_payload(repo: str, branch: str, token: str) -> tuple[dict[str, Any] | None, str]:
    query = urlencode({"branch": branch, "per_page": "20"})
    url = f"https://api.github.com/repos/{repo}/actions/runs?{query}"
    request = Request(url, headers=api_headers(token))
    try:
        with urlopen(request, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        return None, f"github_api_http_{exc.code}"
    except (OSError, URLError, json.JSONDecodeError) as exc:
        return None, f"github_api_unavailable: {exc.__class__.__name__}"
    if not isinstance(payload, dict):
        return None, "github_api_invalid_payload"
    return payload, ""


def commit_matches(run_sha: str, expected: str) -> bool:
    if not expected or expected == "unknown":
        return True
    return run_sha == expected or run_sha.startswith(expected)


def select_workflow_run(payload: dict[str, Any], *, branch: str, commit: str, workflow_name: str) -> dict[str, Any] | None:
    runs = payload.get("workflow_runs")
    if not isinstance(runs, list):
        raise ValueError("GitHub Actions payload must include a workflow_runs list.")
    for run in runs:
        if not isinstance(run, dict):
            continue
        if workflow_name and str(run.get("name") or "") != workflow_name:
            continue
        if branch != "unknown" and str(run.get("head_branch") or "") != branch:
            continue
        run_sha = str(run.get("head_sha") or "")
        if not commit_matches(run_sha, commit):
            continue
        return run
    return None


def result_from_run(status: str, conclusion: str) -> str:
    if status == "completed":
        return "passed" if conclusion == "success" else "failed"
    if status in {"queued", "in_progress", "waiting", "requested", "pending"}:
        return "pending"
    return "unavailable"


def report_from_run(
    run: dict[str, Any],
    *,
    repo: str,
    branch: str,
    commit: str,
    workflow_name: str,
    source: str,
) -> GitHubActionsReport:
    status = str(run.get("status") or "unknown")
    conclusion = str(run.get("conclusion") or "")
    return GitHubActionsReport(
        schema_version="1",
        result=result_from_run(status, conclusion),
        status=status,
        conclusion=conclusion,
        repo=repo,
        branch=branch,
        commit=commit,
        workflow_name=workflow_name,
        run_id=str(run.get("id") or ""),
        run_url=str(run.get("html_url") or ""),
        run_head_sha=str(run.get("head_sha") or ""),
        run_head_branch=str(run.get("head_branch") or ""),
        source=source,
        failure="",
    )


def unavailable_report(
    *,
    repo: str,
    branch: str,
    commit: str,
    workflow_name: str,
    source: str,
    failure: str,
) -> GitHubActionsReport:
    return GitHubActionsReport(
        schema_version="1",
        result="unavailable",
        status="unavailable",
        conclusion="",
        repo=repo,
        branch=branch,
        commit=commit,
        workflow_name=workflow_name,
        run_id="",
        run_url="",
        run_head_sha="",
        run_head_branch="",
        source=source,
        failure=failure,
    )


def build_report(
    payload: dict[str, Any] | None,
    *,
    repo: str,
    branch: str,
    commit: str,
    workflow_name: str,
    source: str,
    failure: str = "",
) -> GitHubActionsReport:
    if payload is None:
        return unavailable_report(
            repo=repo,
            branch=branch,
            commit=commit,
            workflow_name=workflow_name,
            source=source,
            failure=failure or "GitHub Actions payload is unavailable.",
        )
    try:
        run = select_workflow_run(payload, branch=branch, commit=commit, workflow_name=workflow_name)
    except ValueError as exc:
        return unavailable_report(
            repo=repo,
            branch=branch,
            commit=commit,
            workflow_name=workflow_name,
            source=source,
            failure=str(exc),
        )
    if run is None:
        return unavailable_report(
            repo=repo,
            branch=branch,
            commit=commit,
            workflow_name=workflow_name,
            source=source,
            failure=f"No {workflow_name!r} workflow run matched branch={branch!r} commit={commit!r}.",
        )
    return report_from_run(run, repo=repo, branch=branch, commit=commit, workflow_name=workflow_name, source=source)


def resolve_repo_path(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def resolve_artifact_output_path(path: Path, *, label: str) -> Path:
    resolved = resolve_repo_path(path)
    try:
        relative = resolved.relative_to(ROOT)
    except ValueError as exc:
        raise ValueError(f"{label} output must stay inside the repository.") from exc
    if not relative.parts or relative.parts[0] != ".pytest_tmp":
        raise ValueError(f"{label} output must be written under .pytest_tmp.")
    return resolved


def write_json_report(path: Path, report: GitHubActionsReport) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(report), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_markdown_report(path: Path, report: GitHubActionsReport) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GitHub Actions Status",
        "",
        f"- Result: `{report.result}`",
        f"- Status: `{report.status}`",
        f"- Conclusion: `{report.conclusion or '-'}`",
        f"- Repository: `{report.repo}`",
        f"- Branch: `{report.branch}`",
        f"- Commit: `{report.commit}`",
        f"- Workflow: `{report.workflow_name}`",
        f"- Source: `{report.source}`",
        f"- Run id: `{report.run_id or '-'}`",
        f"- Run URL: {report.run_url or '-'}",
    ]
    if report.failure:
        lines.extend(["", "## Failure", "", f"`{report.failure}`"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def print_report(report: GitHubActionsReport) -> None:
    print("github_actions=checked")
    print(f"repo={report.repo}")
    print(f"branch={report.branch}")
    print(f"commit={report.commit}")
    print(f"workflow={report.workflow_name}")
    print(f"status={report.status}")
    if report.conclusion:
        print(f"conclusion={report.conclusion}")
    if report.run_id:
        print(f"run_id={report.run_id}")
    if report.run_url:
        print(f"run_url={report.run_url}")
    if report.failure:
        print(f"failure: {report.failure}")
    print(f"result={report.result}")


def validate_report_artifact(path: Path, markdown: Path | None = None) -> None:
    command = [sys.executable, "scripts/check_github_actions_report.py", "--report-json", str(path)]
    if markdown:
        command.extend(["--markdown", str(markdown)])
    print(">", " ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Check the latest GitHub Actions status for the current branch/commit.")
    parser.add_argument("--repo", default=default_repo(), help="GitHub repository in owner/name form.")
    parser.add_argument("--branch", default=default_branch(), help="Branch name to match.")
    parser.add_argument("--commit", default=default_commit(), help="Commit SHA to match. Use `unknown` to match by branch only.")
    parser.add_argument("--workflow-name", default=DEFAULT_WORKFLOW_NAME, help="Workflow display name to match.")
    parser.add_argument("--input-json", type=Path, help="Offline GitHub API response JSON for tests or saved evidence.")
    parser.add_argument("--json-output", type=Path, help="Write a machine-readable report under .pytest_tmp.")
    parser.add_argument("--markdown-output", type=Path, help="Write a human-readable report under .pytest_tmp.")
    parser.add_argument("--require-success", action="store_true", help="Exit nonzero unless the matched workflow run passed.")
    args = parser.parse_args()

    try:
        json_output = resolve_artifact_output_path(args.json_output, label="JSON") if args.json_output else None
        markdown_output = resolve_artifact_output_path(args.markdown_output, label="Markdown") if args.markdown_output else None
    except ValueError as exc:
        report = unavailable_report(
            repo=args.repo,
            branch=args.branch,
            commit=args.commit,
            workflow_name=args.workflow_name,
            source="local",
            failure=str(exc),
        )
        print_report(report)
        raise SystemExit(1) from exc

    if args.input_json:
        source = "input_json"
        try:
            payload = json.loads(resolve_repo_path(args.input_json).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            payload = None
            failure = f"Input JSON is unavailable: {exc.__class__.__name__}"
        else:
            failure = ""
        if payload is not None and not isinstance(payload, dict):
            payload = None
            failure = "Input JSON must contain an object."
    else:
        payload, failure = fetch_actions_payload(args.repo, args.branch, auth_token())
        source = "github_api"

    report = build_report(
        payload,
        repo=args.repo,
        branch=args.branch,
        commit=args.commit,
        workflow_name=args.workflow_name,
        source=source,
        failure=failure,
    )
    if json_output:
        write_json_report(json_output, report)
    if markdown_output:
        write_markdown_report(markdown_output, report)
    if json_output:
        validate_report_artifact(json_output, markdown_output)
    print_report(report)
    if json_output:
        print(f"json_output={json_output}")
    if markdown_output:
        print(f"markdown_output={markdown_output}")
    if args.require_success and report.result != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
