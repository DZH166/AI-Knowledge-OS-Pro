from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import subprocess
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

EXCLUDED_PARTS = {
    ".git",
    ".next",
    ".pytest_cache",
    ".pytest_tmp",
    "__pycache__",
    "node_modules",
    "releases",
    "backend/data",
    "backend/storage",
    "frontend/.next",
    "frontend/node_modules",
}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".db", ".sqlite", ".sqlite3", ".log", ".tsbuildinfo", ".tmp", ".zip"}
EXCLUDED_NAMES = {".env", ".env.local"}


@dataclass(frozen=True)
class GitChange:
    status: str
    path: str


@dataclass(frozen=True)
class LearningTopic:
    key: str
    name: str
    beginner_explanation: str
    project_usage: str
    review_suggestion: str
    interview_expression: str
    file_patterns: tuple[str, ...]


TOPICS: tuple[LearningTopic, ...] = (
    LearningTopic(
        key="unified_task_model",
        name="Unified Task Model",
        beginner_explanation="Long-running work should have one durable state model, whether the target is a document or media source.",
        project_usage="V3.6 uses target_type plus source_id/document_id so document ingestion and media processing share ingestion_jobs and job_events.",
        review_suggestion="Review task state machines, nullable foreign keys, retry/cancel semantics and worker dispatch.",
        interview_expression="I unified document and media processing under one durable task model, so progress, events, retries and cancellation work consistently across modalities.",
        file_patterns=("ingestion_job", "task_broker", "ingestion_tasks", "routes_ingestion_jobs", "target_type", "source_id"),
    ),
    LearningTopic(
        key="media_task_orchestration",
        name="Media Task Orchestration",
        beginner_explanation="OCR, screenshot analysis, transcription and keyframe extraction are slow processing jobs, not instant UI actions.",
        project_usage="MediaTaskService turns image OCR, visual description, screenshot analysis, audio transcription, video transcription, keyframes, keyframe OCR and full video pipeline into queueable jobs.",
        review_suggestion="Review provider preflight checks, staged progress, JobEvent logging, retry and cancellation.",
        interview_expression="I moved multimodal processing into a task service that records progress and failure details instead of hiding work inside synchronous buttons.",
        file_patterns=("media_task_service", "routes_media", "processMedia", "video_full_pipeline"),
    ),
    LearningTopic(
        key="real_mode_boundaries",
        name="Real-Mode Provider Boundaries",
        beginner_explanation="Uploading a file is not the same as understanding it; missing provider keys must be explicit.",
        project_usage="V3.6 keeps NOT_CONFIGURED behavior for OCR, vision and transcription, and refuses to create fake subtitles or fake learning material.",
        review_suggestion="Review provider adapters, ConfigurationError, NOT_CONFIGURED codes and long-term knowledge-base contamination risk.",
        interview_expression="I kept media management separate from model understanding so real mode never silently writes fake OCR, fake captions or fake notes.",
        file_patterns=("ocr_service", "transcription_service", "VISION_DESCRIPTION_NOT_CONFIGURED", "TRANSCRIPTION_NOT_CONFIGURED", "OCR_NOT_CONFIGURED"),
    ),
    LearningTopic(
        key="citation_deep_links",
        name="Citation Deep Links",
        beginner_explanation="A citation should take the learner back to the evidence, not just name a file.",
        project_usage="Chat citations now carry source_id/document_id and timestamp fields; CitationPanel links to document chunks or media timestamps.",
        review_suggestion="Review citation payloads, URL query parameters, player seek and highlighted transcript chunks.",
        interview_expression="I connected RAG citations to frontend routes so audio and video answers can jump to the exact timestamp that supports the answer.",
        file_patterns=("CitationPanel", "chat_schema", "rag_service", "documents/[id]", "media/sources/[id]"),
    ),
    LearningTopic(
        key="video_keyframes",
        name="Video Keyframes",
        beginner_explanation="Video knowledge includes visible frames, not only the audio track.",
        project_usage="V3.6 extracts multiple deduplicated keyframes, displays them on a timeline, and can run keyframe OCR or visual description with real providers.",
        review_suggestion="Review FFmpeg extraction, perceptual dedupe, VisualFrame, MediaAsset and timestamp locators.",
        interview_expression="I expanded video from a single poster into a traceable keyframe timeline that can feed OCR and visual analysis.",
        file_patterns=("video_service", "extract_keyframes", "VisualFrame", "keyframe", "video_keyframe_ocr", "video_visual_description"),
    ),
    LearningTopic(
        key="source_learning_artifacts",
        name="Source-Based Learning Artifacts",
        beginner_explanation="Learning cards and notes should be traceable to real evidence chunks.",
        project_usage="LearningArtifact records link generated knowledge points, cards, quizzes, notes and interview expressions back to document or multimodal chunks.",
        review_suggestion="Review audit tables, deterministic transformations, chunk locators and refusal when no real text exists.",
        interview_expression="I made source-derived learning material auditable, so every generated card or note can point back to real project evidence.",
        file_patterns=("learning_artifact", "from-source", "LearningArtifact", "createLearningArtifacts"),
    ),
    LearningTopic(
        key="demo_friendly_frontend",
        name="Demo-Friendly Frontend",
        beginner_explanation="A user-facing OS should explain the next action without exposing raw internal fields on primary screens.",
        project_usage="V3.6 improves Upload Center, Task Center and media detail pages with clearer steps, result links, transcript highlighting and keyframe browsing.",
        review_suggestion="Review workflow cards, task filters, media player state, responsive layout and progressive disclosure.",
        interview_expression="I reshaped the frontend around user workflows: upload, process, inspect evidence, ask questions and turn evidence into learning assets.",
        file_patterns=("frontend/app/upload", "frontend/app/tasks", "frontend/app/media/sources", "globals.css"),
    ),
    LearningTopic(
        key="release_verification",
        name="Release Verification",
        beginner_explanation="A release package must be reproducible and must not include dependencies, caches, secrets or user data.",
        project_usage="V4.2 keeps release.py exclusion rules and adds full-regression, RAG and demo-readiness checks before release.",
        review_suggestion="Review zip packaging, SHA256 checks, exclusion rules and acceptance reports.",
        interview_expression="I treated release packaging as part of the product boundary, verifying that generated archives exclude secrets, databases, uploads and build caches.",
        file_patterns=("release.py", "test_release", "stage_delivery_log", "v3_6_acceptance_report"),
    ),
    LearningTopic(
        key="portfolio_documentation",
        name="Portfolio Documentation",
        beginner_explanation="A GitHub portfolio project needs docs that help a stranger run, understand and evaluate it.",
        project_usage="V4.2 keeps README, demo mode, local development, release, versioning, interview QA and roadmap documents aligned with executable checks.",
        review_suggestion="Review README navigation, quickstart commands, demo boundaries and whether planned features are clearly separated.",
        interview_expression="I turned the repository from a code dump into a portfolio-ready project with runnable demo docs, interview notes and honest capability boundaries.",
        file_patterns=("quickstart", "demo_mode", "local_development", "environment_variables", "interview_qa", "Documentation Map"),
    ),
    LearningTopic(
        key="demo_reset_workflow",
        name="Demo Reset Workflow",
        beginner_explanation="A demo should be repeatable; reset scripts make it easy to recover a clean synthetic showcase state.",
        project_usage="V4.2 strengthens demo seed/readiness scripts so the synthetic database proves the source-to-RAG-to-learning walkthrough.",
        review_suggestion="Review path safety checks, synthetic data labels and demo readiness validation.",
        interview_expression="I made the demo reproducible by adding a reset workflow that rebuilds only the isolated synthetic database and verifies required records.",
        file_patterns=("reset_demo_data", "check_demo_ready", "seed_demo_data", "demo_showcase.db"),
    ),
    LearningTopic(
        key="roadmap_specs",
        name="Roadmap Specifications",
        beginner_explanation="Large features should be specified before implementation so docs do not overpromise.",
        project_usage="V4.2 records which V4.0/V4.1 capabilities are implemented and which release-readiness gaps remain.",
        review_suggestion="Review each design doc and mark implemented, requires configuration, demo-only, planned and limitation states.",
        interview_expression="I documented the V4.0 architecture direction before coding it, which keeps roadmap claims honest and reviewable.",
        file_patterns=("rag_evaluation", "hybrid_retrieval", "code_repository_ingestion", "portfolio_system", "interview_system", "observability", "performance_notes"),
    ),
    LearningTopic(
        key="version_governance",
        name="Version Governance",
        beginner_explanation="A visible product version must match backend config, frontend package metadata, README badges and CI release commands.",
        project_usage="V4.2 updates version consistency checks, health tests, package metadata, README badge and CI release artifact naming.",
        review_suggestion="Review check_version.py and every version-bearing file after a version bump.",
        interview_expression="I treated versioning as a testable contract across backend, frontend, docs and CI instead of a README-only label.",
        file_patterns=("check_version", "package.json", "package-lock.json", "app_version", "app_semver", "Version", "V4.2", "V4.3"),
    ),
    LearningTopic(
        key="repository_governance",
        name="Repository Source Governance",
        beginner_explanation="Before releasing, the team must know which branch contains the latest code and whether main is stale.",
        project_usage="V4.2.1 records remote URLs, branch lag, tag status, mainline diff, merge plan, release preparation and branch governance before V4.3 work continues.",
        review_suggestion="Review git remote, branch graph, ahead/behind counts, PR strategy and tag/release preparation.",
        interview_expression="I treated repository state as a release artifact: before adding more features, I audited where the latest code lived and documented the safest PR/tag path.",
        file_patterns=("v4_2_1", "repository_source_audit", "mainline_diff", "merge_plan", "branch_governance"),
    ),
    LearningTopic(
        key="docs_link_integrity",
        name="Documentation Link Integrity",
        beginner_explanation="A portfolio README is only trustworthy if its links and referenced files actually exist.",
        project_usage="V4.3 adds check_docs_links.py to validate local README/docs links and Mermaid fences without requiring network access.",
        review_suggestion="Review Markdown parsing, local-path resolution, archive exclusions and failure messages.",
        interview_expression="I added a docs link gate so GitHub visitors do not hit broken quickstart, demo, roadmap or release references.",
        file_patterns=("check_docs_links", "docs_link_report", "README.md", "quickstart", "demo_showcase"),
    ),
    LearningTopic(
        key="readme_asset_safety",
        name="README Asset Safety",
        beginner_explanation="Screenshots and GIFs should not be referenced until they exist and are safe to publish.",
        project_usage="V4.3 adds check_readme_assets.py to verify local README images, required screenshot files and missing demo GIF risks.",
        review_suggestion="Review screenshot inventory, local image parsing, demo GIF placeholders and sensitive-data boundaries.",
        interview_expression="I made README media part of CI so the portfolio page cannot silently ship broken screenshots or missing demo assets.",
        file_patterns=("check_readme_assets", "assets/screenshots", "assets/demo", "readme_assets"),
    ),
    LearningTopic(
        key="quality_gate_orchestration",
        name="Quality Gate Orchestration",
        beginner_explanation="A release checklist becomes safer when one command can run the same gates consistently.",
        project_usage="V4.3 adds check_all.py with quick, demo, release and full modes for compile, tests, frontend, docs, demo, RAG and release checks.",
        review_suggestion="Review subprocess orchestration, frontend runtime fallback, isolated demo DB paths and release dry-run integration.",
        interview_expression="I grouped the project quality gates into one script with mode-specific scopes, which makes local validation and CI easier to explain and repeat.",
        file_patterns=("check_all", "quality_gate_report", "check_full_regression", "evaluate_rag", "release.py"),
    ),
    LearningTopic(
        key="provider_boundary_regression",
        name="Provider Boundary Regression",
        beginner_explanation="Tests should prove that missing providers fail clearly instead of producing fake AI results.",
        project_usage="V4.3 adds provider-boundary tests for LLM, embeddings, OCR, vision description, transcription and disabled rerank.",
        review_suggestion="Review ConfigurationError codes, provider adapters and tests that avoid calling paid APIs.",
        interview_expression="I locked real-mode boundaries with tests, so missing keys return explicit NOT_CONFIGURED errors and never pollute the knowledge base with fake OCR, transcripts or answers.",
        file_patterns=("test_provider_boundaries", "LLM_NOT_CONFIGURED", "EMBEDDING_NOT_CONFIGURED", "VISION_DESCRIPTION_NOT_CONFIGURED", "TRANSCRIPTION_NOT_CONFIGURED"),
    ),
)


def run(command: list[str], *, check: bool = False) -> str:
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=True,
        )
        return completed.stdout.strip()
    except subprocess.CalledProcessError as exc:
        if check:
            message = (exc.stdout or exc.stderr or str(exc)).strip()
            raise SystemExit(f"Command failed: {' '.join(command)}\n{message}") from exc
        return ""


def git_ref_exists(ref: str) -> bool:
    return (
        subprocess.call(
            ["git", "rev-parse", "--verify", "--quiet", ref],
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        == 0
    )


def should_skip(path: Path) -> bool:
    try:
        relative = path.relative_to(ROOT)
    except ValueError:
        return True
    relative_posix = relative.as_posix()
    if path.name in EXCLUDED_NAMES or path.suffix.lower() in EXCLUDED_SUFFIXES:
        return True
    return any(relative_posix == item or relative_posix.startswith(f"{item}/") for item in EXCLUDED_PARTS)


def expand_untracked(path_text: str) -> list[str]:
    path = ROOT / path_text
    if path.is_dir():
        return sorted(child.relative_to(ROOT).as_posix() for child in path.rglob("*") if child.is_file() and not should_skip(child))
    if path.exists() and not should_skip(path):
        return [path.relative_to(ROOT).as_posix()]
    return [path_text.replace("\\", "/")]


def parse_name_status(raw: str) -> list[GitChange]:
    changes: list[GitChange] = []
    for line in raw.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            status = parts[0]
            path = parts[-1].replace("\\", "/")
            if not should_skip(ROOT / path):
                changes.append(GitChange(status=status, path=path))
    return changes


def collect_git_changes(from_ref: str | None, to_ref: str) -> list[GitChange]:
    if from_ref:
        if not git_ref_exists(from_ref):
            raise SystemExit(f"from-ref does not exist: {from_ref}")
        if not git_ref_exists(to_ref):
            raise SystemExit(f"to-ref does not exist: {to_ref}")
        return parse_name_status(run(["git", "diff", "--name-status", f"{from_ref}..{to_ref}"], check=True))

    raw = run(["git", "diff", "--name-status", to_ref]) if git_ref_exists(to_ref) else ""
    changes = parse_name_status(raw)
    seen = {change.path for change in changes}
    status_raw = subprocess.check_output(
        ["git", "status", "--short"],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    for line in status_raw.splitlines():
        if not line.strip():
            continue
        status = line[:2].strip() or "M"
        candidate = line[3:].strip()
        if " -> " in candidate:
            candidate = candidate.split(" -> ", 1)[1]
        for expanded in expand_untracked(candidate):
            if expanded not in seen:
                changes.append(GitChange(status=status, path=expanded))
                seen.add(expanded)
    return sorted(changes, key=lambda item: item.path)


def collect_git_stat(from_ref: str | None, to_ref: str) -> str:
    if from_ref:
        return run(["git", "diff", "--stat", f"{from_ref}..{to_ref}"])
    diff_stat = run(["git", "diff", "--stat", to_ref]) if git_ref_exists(to_ref) else ""
    return diff_stat or run(["git", "status", "--short"])


def collect_commits(from_ref: str | None, to_ref: str) -> list[str]:
    if not from_ref:
        return []
    return [line for line in run(["git", "log", "--oneline", f"{from_ref}..{to_ref}"]).splitlines() if line.strip()]


def collect_routes() -> list[str]:
    routes: list[str] = []
    for path in sorted((ROOT / "backend" / "app" / "api").glob("routes_*.py")):
        text = path.read_text(encoding="utf-8", errors="replace")
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("@router."):
                routes.append(f"{path.relative_to(ROOT).as_posix()}::{stripped}")
    return routes


def collect_dependency_changes(changes: Iterable[GitChange]) -> list[str]:
    dependency_files = {
        ".env.example",
        "backend/.env.example",
        "backend/requirements.txt",
        "docker-compose.yml",
        "frontend/package.json",
        "frontend/package-lock.json",
    }
    return [change.path for change in changes if change.path in dependency_files]


def collect_migration_changes(changes: Iterable[GitChange]) -> list[str]:
    return [change.path for change in changes if "alembic/versions" in change.path or change.path.endswith("alembic.ini")]


def infer_topics(changes: list[GitChange]) -> list[dict]:
    selected: list[dict] = []
    for topic in TOPICS:
        matched = [change.path for change in changes if any(pattern in change.path for pattern in topic.file_patterns)]
        if matched:
            selected.append(
                {
                    "name": topic.name,
                    "beginner_explanation": topic.beginner_explanation,
                    "project_usage": topic.project_usage,
                    "code_locations": sorted(dict.fromkeys(matched))[:8],
                    "review_suggestion": topic.review_suggestion,
                    "interview_expression": topic.interview_expression,
                }
            )
    return selected


def infer_feature(change: GitChange) -> str:
    path = change.path
    if "media_task_service" in path or "routes_media" in path:
        return "Unified media processing tasks in Task Center."
    if "learning_artifact" in path or "from-source" in path:
        return "Generated traceable learning artifacts from real source chunks."
    if "CitationPanel" in path or "rag_service" in path or "chat_schema" in path:
        return "Added source/document IDs and deep links for RAG citations."
    if "video_service" in path or "keyframe" in path:
        return "Improved multi-keyframe extraction and video visual processing."
    if "frontend/app/media/sources" in path:
        return "Linked media player, transcript, keyframes and learning actions."
    if "frontend/app/upload" in path or "DocumentUploader" in path:
        return "Clarified upload workflows for document, image, audio and video sources."
    if "frontend/app/tasks" in path or "task_event" in path:
        return "Improved task progress, event visibility and recovery controls."
    if "alembic" in path:
        return "Updated database schema migration coverage."
    if "release.py" in path:
        return "Verified release packaging exclusions and SHA256 output."
    return f"Updated {path}."


def responsibility_for(path: str) -> str:
    if "media_task_service" in path:
        return "Media task orchestration, progress, failure and retry/cancel behavior."
    if "learning_artifact" in path:
        return "Auditable source-based learning artifact generation."
    if "CitationPanel" in path or "rag_service" in path or "chat_schema" in path:
        return "Citation payloads, source locators and frontend deep links."
    if "frontend/app/media/sources" in path:
        return "Media detail player sync, transcript highlights, keyframes and learning actions."
    if "frontend/app/upload" in path:
        return "User-facing source intake workflows by modality."
    if "frontend/app/tasks" in path:
        return "Unified Task Center UI for documents and media."
    if "video_service" in path:
        return "Video metadata, audio extraction and multi-keyframe processing."
    if "alembic" in path:
        return "Database schema evolution."
    if "docs" in path:
        return "Version archive, acceptance report or delivery documentation."
    if "scripts" in path:
        return "Learning package or release automation."
    return "Project implementation change."


def infer_major_files(changes: list[GitChange]) -> list[dict]:
    priority_prefixes = ("backend/app", "backend/alembic", "frontend/app", "frontend/components", "frontend/services", "frontend/types", "scripts", "docs")
    files = [change.path for change in changes if change.path.startswith(priority_prefixes)]
    return [{"path": path, "responsibility": responsibility_for(path)} for path in files[:40]]


def read_optional(path_text: str | None) -> str:
    if not path_text:
        return ""
    path = Path(path_text)
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        raise SystemExit(f"Report file does not exist: {path}")
    return path.read_text(encoding="utf-8", errors="replace").strip()


def render_markdown(
    *,
    version: str,
    generated_at: str,
    goal: str,
    changes: list[GitChange],
    routes: list[str],
    dependency_changes: list[str],
    migration_changes: list[str],
    git_stat: str,
    commits: list[str],
    tests: str,
    build: str,
    migrations: str,
    topics: list[dict],
) -> str:
    lines = [
        f"## {version} Learning Package Draft",
        "",
        f"- Generated at: {generated_at}",
        f"- Version goal: {goal}",
        "- Evidence: Git diff/status, backend route scan, dependency changes, migration changes and optional verification reports.",
        "",
        "### Changed Files",
        *[f"- `{change.status}` `{change.path}`" for change in changes[:100]],
        "",
        "### Git Summary",
        "```text",
        git_stat or "No git diff/stat output is available; current workspace status was used.",
        "```",
        "",
        "### Commit Range",
        *([f"- `{commit}`" for commit in commits] if commits else ["- No commit range was provided; the draft is based on the working tree."]),
        "",
        "### Dependency Changes",
        *([f"- `{path}`" for path in dependency_changes] if dependency_changes else ["- No dependency file changes detected."]),
        "",
        "### Migration Changes",
        *([f"- `{path}`" for path in migration_changes] if migration_changes else ["- No migration file changes detected."]),
        "",
        "### API Route Snapshot",
        *[f"- `{route}`" for route in routes[:120]],
        "",
        "### Knowledge Topics",
    ]
    for topic in topics:
        lines.extend(
            [
                f"#### {topic['name']}",
                f"- Beginner explanation: {topic['beginner_explanation']}",
                f"- Project usage: {topic['project_usage']}",
                f"- Code locations: {', '.join(f'`{item}`' for item in topic['code_locations'])}",
                f"- Review suggestion: {topic['review_suggestion']}",
                f"- Interview expression: {topic['interview_expression']}",
                "",
            ]
        )
    lines.extend(
        [
            "### Test Report",
            "```text",
            tests or "No test report file was provided.",
            "```",
            "",
            "### Build Report",
            "```text",
            build or "No build report file was provided.",
            "```",
            "",
            "### Migration Report",
            "```text",
            migrations or "No migration report file was provided.",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def build_package(args: argparse.Namespace) -> dict:
    changes = collect_git_changes(args.from_ref, args.to_ref)
    routes = collect_routes()
    dependency_changes = collect_dependency_changes(changes)
    migration_changes = collect_migration_changes(changes)
    git_stat = collect_git_stat(args.from_ref, args.to_ref)
    commits = collect_commits(args.from_ref, args.to_ref)
    topics = infer_topics(changes)
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    tests = read_optional(args.test_report)
    build = read_optional(args.build_report)
    migrations = read_optional(args.migration_report)
    features = sorted(dict.fromkeys(infer_feature(change) for change in changes))
    normalized_version = args.version.lower().replace(".", "-").replace(" ", "-")
    slug = (
        "v3-6-unified-media-learning"
        if args.version.strip().upper() == "V3.6"
        else f"{normalized_version}-learning-package"
    )
    markdown = render_markdown(
        version=args.version,
        generated_at=generated_at,
        goal=args.goal,
        changes=changes,
        routes=routes,
        dependency_changes=dependency_changes,
        migration_changes=migration_changes,
        git_stat=git_stat,
        commits=commits,
        tests=tests,
        build=build,
        migrations=migrations,
        topics=topics,
    )
    return {
        "version_name": f"{args.version}: {args.goal}",
        "slug": slug,
        "summary": args.goal,
        "implemented_features": features,
        "major_files": infer_major_files(changes),
        "knowledge_points": topics,
        "focus": f"Understand the concrete changes, verification evidence and remaining limits for {args.version}.",
        "review_suggestions": "Review the changed files, command outputs, generated docs, tests, release safety checks and planned follow-up boundaries.",
        "interview_expression": f"In AI Knowledge OS Pro {args.version}, I advanced the project with evidence-backed changes, verified them with tests/builds/checks, and documented both delivered capabilities and remaining limits.",
        "next_version_suggestion": "Continue with the next roadmap stage using measurable tests, honest provider boundaries and append-only learning records.",
        "metadata": {
            "generated_at": generated_at,
            "from_ref": args.from_ref,
            "to_ref": args.to_ref,
            "dependency_changes": dependency_changes,
            "migration_changes": migration_changes,
            "route_count": len(routes),
            "change_count": len(changes),
        },
        "markdown_content": markdown,
    }


def default_output(version: str) -> Path:
    normalized = version.lower().replace(".", "_").replace(" ", "_")
    return DOCS / f"{normalized}_learning_package_draft.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a version learning package draft from real project changes.")
    parser.add_argument("--version", default="V3.6")
    parser.add_argument("--from-ref", help="Git ref/tag/commit to diff from. If omitted, use working tree status.")
    parser.add_argument("--to-ref", default="HEAD", help="Git ref/tag/commit to diff to.")
    parser.add_argument(
        "--goal",
        default="Upgrade the multimodal prototype into a stable, unified and demo-friendly knowledge learning system.",
    )
    parser.add_argument("--test-report", help="Optional text file containing pytest or backend test output.")
    parser.add_argument("--build-report", help="Optional text file containing frontend build/typecheck output.")
    parser.add_argument("--migration-report", help="Optional text file containing Alembic migration output.")
    parser.add_argument("--output", help="Output JSON path. Defaults to docs/<version>_learning_package_draft.json.")
    args = parser.parse_args()

    DOCS.mkdir(exist_ok=True)
    package = build_package(args)
    output = Path(args.output) if args.output else default_output(args.version)
    if not output.is_absolute():
        output = ROOT / output
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.suffix.lower() == ".md":
        output.write_text(package["markdown_content"], encoding="utf-8")
    else:
        output.write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
