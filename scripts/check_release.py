from __future__ import annotations

import argparse
from collections import Counter
from contextlib import ExitStack
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import stat
import tempfile
from typing import BinaryIO, Iterable
import zipfile
import zlib

if __package__:
    from scripts import release as release_builder
    from scripts.release import (
        HASH_CHUNK_SIZE,
        RELEASE_MANIFEST,
        RELEASE_MANIFEST_DIGEST,
        RELEASE_MANIFEST_SCHEMA,
    )
else:
    import release as release_builder
    from release import (
        HASH_CHUNK_SIZE,
        RELEASE_MANIFEST,
        RELEASE_MANIFEST_DIGEST,
        RELEASE_MANIFEST_SCHEMA,
    )


ROOT = Path(__file__).resolve().parents[1]
RELEASES = ROOT / "releases"
FORBIDDEN_PATTERNS = (
    re.compile(r"(^|/)node_modules/"),
    re.compile(r"(^|/)\.next/"),
    re.compile(r"(^|/)\.env$"),
    re.compile(r"(^|/)\.env\.local$"),
    re.compile(r"(^|/)releases/"),
    re.compile(r"(^|/)\.git/"),
    re.compile(r"(^|/)\.(agents|codex)/"),
    re.compile(r"(^|/)backend/(data|storage)/"),
    re.compile(r"(^|/)(uploads|logs?)/"),
    re.compile(
        r"(^|/)(qdrant_storage|redis_data|media_cache|transcripts_cache|keyframes_cache)/"
    ),
    re.compile(r"(^|/)sub2api/"),
    re.compile(r"(^|/)__pycache__/"),
    re.compile(r"\.(db|sqlite|sqlite3|log|pyc|tsbuildinfo)$"),
)
COMMON_REQUIRED_ENTRIES = {
    ".github/workflows/ci.yml",
    "CONTRIBUTING.md",
    "LICENSE",
    "README.md",
    "SECURITY.md",
    "backend/app/main.py",
    "docs/archive/v3/v3_6_acceptance_report.md",
    "frontend/package.json",
    "scripts/check_encoding.py",
}

VERSION_REQUIRED_ENTRIES = {
    "V4.2": {
        "docs/v4_2_acceptance_report.md",
        "docs/v4_2_full_regression_report.md",
    },
    "V4.3": {
        "docs/v4_3_release_readiness_report.md",
        "docs/v4_3_quality_gate_report.md",
        "docs/v4_3_readme_asset_report.md",
        "docs/v4_3_ux_error_state_report.md",
        "docs/v4_4_planning.md",
        "scripts/check_all.py",
        "scripts/check_docs_links.py",
        "scripts/check_readme_assets.py",
    },
    "V4.4": {
        "docs/v4_4_acceptance_report.md",
        "docs/v4_4_browser_e2e_report.md",
        "docs/v4_4_citation_jump_report.md",
        "docs/v4_4_observability_report.md",
        "docs/v4_4_provider_eval_report.md",
        "docs/v4_4_quality_gate_report.md",
        "docs/v4_4_release_notes.md",
        "frontend/e2e/demo-smoke.spec.ts",
        "frontend/playwright.config.ts",
        "scripts/check_e2e.py",
        "scripts/evaluate_providers.py",
    },
    "V4.5": {
        "docs/v4_5_acceptance_report.md",
        "docs/v4_5_citation_jump_e2e_report.md",
        "docs/v4_5_live_e2e_report.md",
        "docs/v4_5_learning_package_draft.md",
        "docs/v4_5_observability_e2e_report.md",
        "docs/v4_5_quality_gate_report.md",
        "docs/v4_5_release_doc_hygiene_report.md",
        "docs/v4_5_release_notes.md",
        "docs/release_checklist.md",
        "frontend/e2e/demo-smoke.spec.ts",
        "frontend/e2e/citation-jump.spec.ts",
        "frontend/e2e/system-observability.spec.ts",
        "frontend/playwright.config.ts",
        "scripts/check_e2e.py",
        "scripts/run_demo_e2e.py",
    },
    "V4.7": {
        "docs/v4_7_acceptance_report.md",
        "docs/v4_7_button_latency_map.md",
        "docs/v4_7_cleanup_plan.md",
        "docs/v4_7_dead_code_second_pass_report.md",
        "docs/v4_7_frontend_performance_report.md",
        "docs/v4_7_interaction_performance_audit.md",
        "docs/v4_7_navigation_audit.md",
        "docs/v4_7_performance_budget_report.md",
        "docs/v4_7_predevelopment_audit.md",
        "docs/v4_7_project_structure_visual_redesign_report.md",
        "docs/v4_7_release_notes.md",
        "docs/v4_7_script_sprawl_audit.md",
        "docs/v4_7_test_report.md",
        "docs/v4_7_test_sprawl_audit.md",
        "docs/v4_7_visual_ux_report.md",
        "frontend/app/learning/project-structure/page.tsx",
        "scripts/check_interaction_feedback.py",
        "scripts/check_ui_performance_budget.py",
    },
    "V4.8": {
        "backend/app/api/routes_performance.py",
        "backend/app/services/performance_service.py",
        "backend/app/schemas/performance_schema.py",
        "backend/tests/test_v4_8_performance_observability.py",
        "backend/tests/test_v4_8_request_cache_static.py",
        "docs/v4_8_acceptance_report.md",
        "docs/v4_8_button_latency_map.md",
        "docs/v4_8_interaction_runtime_report.md",
        "docs/v4_8_learning_package_draft.md",
        "docs/v4_8_medium_risk_interaction_cleanup_report.md",
        "docs/v4_8_performance_dashboard_report.md",
        "docs/v4_8_predevelopment_audit.md",
        "docs/v4_8_release_notes.md",
        "docs/v4_8_release_zip_user_experience_report.md",
        "docs/v4_8_request_cache_report.md",
        "docs/v4_8_runtime_performance_report.md",
        "docs/v4_8_script_maintenance_migration_report.md",
        "docs/v4_8_test_report.md",
        "frontend/app/system/performance/page.tsx",
        "frontend/services/page-metrics.ts",
        "frontend/services/request-cache.ts",
        "frontend/services/interaction-metrics.ts",
        "scripts/check_request_cache.py",
    },
    "V5.0": {
        "backend/alembic/versions/0007_v5_evidence_index.py",
        "backend/alembic/versions/0008_v5_agent_runtime.py",
        "backend/app/modules/evidence_agent/controller.py",
        "backend/app/modules/evidence_index/sql.py",
        "docs/v5_agentic_rag/acceptance_report.md",
        "docs/v5_agentic_rag/evaluation_report.json",
        "evaluation/v5/cases.jsonl",
        "frontend/app/workbench/page.tsx",
        "frontend/app/runs/[runId]/page.tsx",
        "frontend/app/artifacts/[artifactId]/page.tsx",
        "frontend/e2e/v5-evidence-agent.spec.ts",
        "scripts/check_v5_acceptance.py",
        "scripts/evaluate_agentic_rag.py",
        "scripts/reconcile_evidence_index.py",
    },
    "V5.1": {
        "backend/alembic/versions/0007_v5_evidence_index.py",
        "backend/alembic/versions/0008_v5_agent_runtime.py",
        "backend/app/modules/evidence_agent/controller.py",
        "backend/app/modules/evidence_index/sql.py",
        "backend/app/services/outbox_dispatcher.py",
        "backend/app/worker.py",
        "backend/tests/test_v5_1_runtime_e2e.py",
        "docs/v5_1_integration_report.md",
        "docs/v5_1_runtime_e2e/acceptance_report.md",
        "docs/v5_1_runtime_e2e/checklist.md",
        "docs/v5_agentic_rag/evaluation_report.json",
        "evaluation/v5/cases.jsonl",
        "frontend/app/workbench/page.tsx",
        "frontend/app/runs/[runId]/page.tsx",
        "frontend/app/artifacts/[artifactId]/page.tsx",
        "frontend/e2e/v5-evidence-agent.spec.ts",
        "scripts/check_v5_acceptance.py",
        "scripts/evaluate_agentic_rag.py",
        "scripts/reconcile_evidence_index.py",
        "scripts/run_demo_e2e.py",
    },
    "V5.2": {
        "backend/alembic/versions/0007_v5_evidence_index.py",
        "backend/alembic/versions/0008_v5_agent_runtime.py",
        "backend/alembic/versions/0009_v5_2_agent_control.py",
        "backend/app/api/routes_agent_control.py",
        "backend/app/models/agent_evaluation.py",
        "backend/app/modules/agent_control/service.py",
        "backend/app/modules/agent_control/executor.py",
        "backend/app/modules/agent_control/report.py",
        "backend/app/modules/evidence_agent/controller.py",
        "backend/app/modules/evidence_index/sql.py",
        "backend/app/services/outbox_dispatcher.py",
        "backend/app/worker.py",
        "backend/tests/test_v5_2_agent_control_api.py",
        "backend/tests/test_v5_2_agent_control_migration.py",
        "backend/tests/test_v5_2_agent_control_pure.py",
        "backend/tests/test_v5_2_agent_control_sql.py",
        "backend/tests/test_v5_2_agent_control_worker.py",
        "docs/v5_2_agent_control_center/acceptance_report.md",
        "docs/v5_2_agent_control_center/checklist.md",
        "docs/v5_2_agent_control_center/plain_language_guide.md",
        "docs/v5_agentic_rag/evaluation_report.json",
        "evaluation/v5/cases.jsonl",
        "frontend/app/evaluations/page.tsx",
        "frontend/app/evaluations/[evaluationId]/page.tsx",
        "frontend/app/runs/[runId]/trace/page.tsx",
        "frontend/app/workbench/page.tsx",
        "frontend/components/agent-control/EvaluationDetailView.tsx",
        "frontend/components/agent-control/EvaluationIndex.tsx",
        "frontend/components/agent-control/RunTraceView.tsx",
        "frontend/e2e/v5-2-agent-control.spec.ts",
        "frontend/e2e/v5-evidence-agent.spec.ts",
        "scripts/check_v5_acceptance.py",
        "scripts/evaluate_agentic_rag.py",
        "scripts/run_demo_e2e.py",
    },
}

VERSION_REQUIRED_ENTRIES["V5.3"] = VERSION_REQUIRED_ENTRIES["V5.2"] | {
    "backend/alembic/versions/0010_v5_3_agent_policy.py",
    "backend/app/api/routes_agent_policy.py",
    "backend/app/models/agent_policy.py",
    "backend/app/modules/agent_policy/config.py",
    "backend/app/modules/agent_policy/contracts.py",
    "backend/app/modules/agent_policy/decision.py",
    "backend/app/modules/agent_policy/service.py",
    "backend/app/modules/agent_policy/simulation.py",
    "backend/app/schemas/agent_policy_schema.py",
    "backend/tests/test_v5_3_agent_policy_api.py",
    "backend/tests/test_v5_3_agent_policy_evaluation.py",
    "backend/tests/test_v5_3_agent_policy_migration.py",
    "backend/tests/test_v5_3_agent_policy_pure.py",
    "backend/tests/test_v5_3_agent_policy_run_pinning.py",
    "backend/tests/test_v5_3_agent_policy_runtime.py",
    "backend/tests/test_v5_3_agent_policy_sql.py",
    "docs/v5_3_adaptive_policy_retrieval/acceptance_report.md",
    "docs/v5_3_adaptive_policy_retrieval/checklist.md",
    "docs/v5_3_adaptive_policy_retrieval/plain_language_guide.md",
    "docs/v5_3_adaptive_policy_retrieval/plan.md",
    "docs/v5_3_adaptive_policy_retrieval/spec.md",
    "docs/v5_3_adaptive_policy_retrieval/task.md",
    "frontend/app/policies/page.tsx",
    "frontend/app/policies/[policyId]/page.tsx",
    "frontend/components/agent-policy/PolicyDetailView.tsx",
    "frontend/components/agent-policy/PolicyLab.tsx",
    "frontend/e2e/v5-3-agent-policy.spec.ts",
    "frontend/modules/agent-policy/client.ts",
    "frontend/modules/agent-policy/contract.ts",
}

VERSION_REQUIRED_ENTRIES["V5.7"] = VERSION_REQUIRED_ENTRIES["V5.3"] | {
    "backend/alembic/versions/0011_v5_4_retrieval_optimizer.py",
    "backend/alembic/versions/0012_v5_5_optimizer_closed_loop.py",
    "backend/alembic/versions/0013_v5_6_bayesian_optimizer.py",
    "backend/alembic/versions/0014_v5_7_workbench_backend.py",
    "backend/alembic/versions/0015_v5_7_integration.py",
    "backend/app/api/routes_optimizer.py",
    "backend/app/api/routes_agent_run_share.py",
    "backend/app/modules/agent_policy_optimizer/service.py",
    "backend/app/modules/agent_policy_optimizer/comparison_exporter.py",
    "backend/app/modules/agent_policy_optimizer/draft_conversion.py",
    "backend/app/modules/agent_policy_optimizer/internal.py",
    "backend/app/modules/agent_policy_optimizer/trial_inspection.py",
    "backend/app/modules/agent_policy_optimizer/workbench_projection.py",
    "backend/app/modules/agent_policy_optimizer/terminal_commands.py",
    "backend/app/modules/agent_run_share/service.py",
    "backend/app/modules/agent_run_share/contracts.py",
    "backend/tests/test_v5_7_integration_migration.py",
    "backend/tests/test_v5_7_workbench_api.py",
    "backend/tests/test_v5_7_workbench_sql.py",
    "docs/v5_7_integration_ui/acceptance_report.md",
    "docs/v5_7_integration_ui/plain_language_guide.md",
    "docs/v5_7_integration_ui/spec.md",
    "frontend/app/policies/optimizer/page.tsx",
    "frontend/app/policies/optimizer/[studyId]/page.tsx",
    "frontend/components/optimizer/OptimizerLab.tsx",
    "frontend/components/optimizer/OptimizerStudyView.tsx",
    "frontend/modules/agent-run-share/client.ts",
    "frontend/modules/agent-run-share/contract.ts",
    "frontend/modules/optimizer/client.ts",
    "frontend/e2e/v5-7-optimizer-workbench.spec.ts",
}


VERSION_REQUIRED_ENTRIES["V5.7.1"] = VERSION_REQUIRED_ENTRIES["V5.7"] | {
    "backend/alembic/versions/0016_optimizer_audit.py",
    "backend/app/modules/agent_policy_optimizer/evaluation_facts.py",
    "backend/tests/test_optimizer_release_audit.py",
    "backend/tests/test_optimizer_audit_migration.py",
    "docs/v5_7_1_audit/spec.md",
    "docs/v5_7_1_audit/acceptance_report.md",
    "docs/v5_7_1_audit/evaluation_report.json",
    "docs/v5_7_1_audit/evaluation_acceptance.json",
    "docs/v5_7_1_audit/upgrade_explained.md",
    "frontend/modules/optimizer/command-identity.ts",
}


@dataclass(frozen=True)
class ReleaseCheckResult:
    archive_path: Path
    payload_files: int
    archive_sha256: str


class ReleaseValidationError(ValueError):
    def __init__(
        self,
        errors: Iterable[str],
        *,
        forbidden: Iterable[str] = (),
        missing: Iterable[str] = (),
    ) -> None:
        self.errors = tuple(errors)
        self.forbidden = tuple(forbidden)
        self.missing = tuple(missing)
        super().__init__("; ".join((*self.errors, *self.forbidden, *self.missing)))


@dataclass
class _StableFileSnapshot:
    path: Path
    label: str
    stream: BinaryIO
    digest: str
    size: int
    path_stat: os.stat_result

    def close(self) -> None:
        self.stream.close()


@dataclass
class _CurrentSourceSnapshot:
    name: str
    path: Path
    stream: BinaryIO
    opened_stat: os.stat_result
    digest: str
    size: int


def _absolute_without_resolving(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _is_link_or_reparse(stat_result: os.stat_result) -> bool:
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return stat.S_ISLNK(stat_result.st_mode) or bool(
        getattr(stat_result, "st_file_attributes", 0) & reparse_flag
    )


def _same_snapshot_identity(left: os.stat_result, right: os.stat_result) -> bool:
    return (
        os.path.samestat(left, right)
        and left.st_size == right.st_size
        and left.st_mtime_ns == right.st_mtime_ns
        and left.st_ctime_ns == right.st_ctime_ns
    )


def _same_source_identity_and_metadata(
    left: os.stat_result,
    right: os.stat_result,
) -> bool:
    return (
        os.path.samestat(left, right)
        and left.st_size == right.st_size
        and left.st_mtime_ns == right.st_mtime_ns
    )


def _take_stable_file_snapshot(
    path: Path,
    *,
    label: str,
    maximum_size: int | None = None,
) -> _StableFileSnapshot:
    absolute_path = _absolute_without_resolving(path)
    try:
        path_stat = os.lstat(absolute_path)
    except OSError as exc:
        raise ReleaseValidationError(
            [f"{label} is missing or unreadable: {exc}"]
        ) from exc
    if _is_link_or_reparse(path_stat) or not stat.S_ISREG(path_stat.st_mode):
        raise ReleaseValidationError(
            [f"{label} must be a regular non-reparse file: {absolute_path}"]
        )

    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    snapshot = tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024, mode="w+b")
    digest = hashlib.sha256()
    size = 0
    try:
        descriptor = os.open(absolute_path, flags)
        with os.fdopen(descriptor, "rb") as source:
            opened_stat = os.fstat(source.fileno())
            if not stat.S_ISREG(opened_stat.st_mode) or not os.path.samestat(
                path_stat, opened_stat
            ):
                raise ReleaseValidationError([f"{label} changed while it was opened"])
            while chunk := source.read(HASH_CHUNK_SIZE):
                size += len(chunk)
                if maximum_size is not None and size > maximum_size:
                    raise ReleaseValidationError(
                        [f"{label} exceeds the {maximum_size}-byte limit"]
                    )
                snapshot.write(chunk)
                digest.update(chunk)
            finished_stat = os.fstat(source.fileno())
            if not _same_snapshot_identity(opened_stat, finished_stat):
                raise ReleaseValidationError(
                    [f"{label} changed while it was snapshotted"]
                )
        snapshot.seek(0)
        return _StableFileSnapshot(
            path=absolute_path,
            label=label,
            stream=snapshot,
            digest=digest.hexdigest(),
            size=size,
            path_stat=path_stat,
        )
    except BaseException:
        snapshot.close()
        raise


def _assert_snapshot_path_unchanged(snapshot: _StableFileSnapshot) -> None:
    try:
        current_stat = os.lstat(snapshot.path)
    except OSError as exc:
        raise ReleaseValidationError(
            [f"{snapshot.label} path changed during validation: {exc}"]
        ) from exc
    if _is_link_or_reparse(current_stat) or not _same_snapshot_identity(
        snapshot.path_stat, current_stat
    ):
        raise ReleaseValidationError(
            [f"{snapshot.label} path changed during validation"]
        )


def _stream_sha256(stream: BinaryIO) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    while chunk := stream.read(HASH_CHUNK_SIZE):
        digest.update(chunk)
        size += len(chunk)
    return digest.hexdigest(), size


def _read_archive_bytes(
    archive: zipfile.ZipFile,
    name: str,
    errors: list[str],
) -> bytes | None:
    try:
        return archive.read(name)
    except (zipfile.BadZipFile, RuntimeError, EOFError, OSError, zlib.error) as exc:
        errors.append(f"cannot read archive entry: {name} ({exc})")
        return None


def _archive_path_error(name: str) -> str | None:
    if not name or "\x00" in name or "\\" in name:
        return "empty, NUL, or backslash path"
    pure = PurePosixPath(name)
    if pure.is_absolute() or PureWindowsPath(name).drive:
        return "absolute or drive-qualified path"
    if pure.as_posix() != name or any(part in {"", ".", ".."} for part in pure.parts):
        return "non-canonical or traversing path"
    return None


def _object_without_duplicate_keys(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _portable_path_conflict_error(scope: str, names: Iterable[str]) -> str | None:
    conflicts = release_builder.portable_path_ancestor_conflicts(names)
    if not conflicts:
        return None
    details = ", ".join(
        f"{ancestor!r} -> {descendant!r}" for ancestor, descendant in conflicts
    )
    return f"portable {scope} path ancestor conflict: {details}"


def _portable_path_collision_error(scope: str, names: Iterable[str]) -> str | None:
    groups: dict[str, list[str]] = {}
    for name in names:
        groups.setdefault(name.casefold(), []).append(name)
    collisions = [values for values in groups.values() if len(values) > 1]
    if not collisions:
        return None
    details = ", ".join(
        " = ".join(
            repr(name)
            for name in sorted(values, key=lambda value: (value.casefold(), value))
        )
        for values in sorted(collisions, key=lambda values: values[0].casefold())
    )
    return f"portable {scope} path collision: {details}"


def _current_source_records(
    root: Path,
    files: Iterable[Path],
    source_stack: ExitStack,
) -> tuple[
    dict[str, tuple[str, int]],
    list[_CurrentSourceSnapshot],
    list[str],
]:
    records: dict[str, tuple[str, int]] = {}
    snapshots: list[_CurrentSourceSnapshot] = []
    errors: list[str] = []
    for source in files:
        try:
            validated = release_builder.validate_release_source(root, source)
            flags = (
                os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
            )
            descriptor = os.open(validated.path, flags)
            try:
                stream = os.fdopen(descriptor, "rb")
            except BaseException:
                os.close(descriptor)
                raise
            source_stack.callback(stream.close)
            opened_stat = os.fstat(stream.fileno())
            if not stat.S_ISREG(
                opened_stat.st_mode
            ) or not _same_source_identity_and_metadata(
                validated.stat_result,
                opened_stat,
            ):
                raise ValueError(
                    "source identity or metadata changed while it was opened"
                )
            digest_and_size = _stream_sha256(stream)
            hashed_stat = os.fstat(stream.fileno())
            current = release_builder.validate_release_source(root, source)
            if not _same_source_identity_and_metadata(
                opened_stat,
                hashed_stat,
            ) or not _same_source_identity_and_metadata(
                opened_stat,
                current.stat_result,
            ):
                raise ValueError(
                    "source identity or metadata changed while it was hashed"
                )
            name = validated.archive_name
        except FileNotFoundError:
            errors.append(f"worktree source missing: {source}")
            continue
        except (OSError, ValueError) as exc:
            errors.append(f"unsafe worktree source {source}: {exc}")
            continue
        if path_error := _archive_path_error(name):
            errors.append(f"unsafe worktree source path {name!r}: {path_error}")
            continue
        if name in records:
            errors.append(f"duplicate worktree source path: {name}")
            continue
        records[name] = digest_and_size
        snapshots.append(
            _CurrentSourceSnapshot(
                name=name,
                path=validated.path,
                stream=stream,
                opened_stat=opened_stat,
                digest=digest_and_size[0],
                size=digest_and_size[1],
            )
        )
    if len(records) != len({name.casefold() for name in records}):
        errors.append("case-insensitive duplicate worktree source paths")
    portable_source_names = (*records, RELEASE_MANIFEST, RELEASE_MANIFEST_DIGEST)
    if collision_error := _portable_path_collision_error(
        "worktree source",
        portable_source_names,
    ):
        errors.append(collision_error)
    if conflict_error := _portable_path_conflict_error(
        "worktree source",
        portable_source_names,
    ):
        errors.append(conflict_error)
    return records, snapshots, errors


def _current_source_fence(
    root: Path,
    snapshots: Iterable[_CurrentSourceSnapshot],
) -> list[str]:
    source_snapshots = list(snapshots)
    errors: list[str] = []
    failed_names: set[str] = set()
    for snapshot in source_snapshots:
        try:
            before_hash = os.fstat(snapshot.stream.fileno())
            current_before = release_builder.validate_release_source(
                root, snapshot.path
            )
            if not _same_source_identity_and_metadata(
                snapshot.opened_stat,
                before_hash,
            ) or not _same_source_identity_and_metadata(
                snapshot.opened_stat,
                current_before.stat_result,
            ):
                raise ValueError("identity or metadata changed")

            snapshot.stream.seek(0)
            digest, size = _stream_sha256(snapshot.stream)
            after_hash = os.fstat(snapshot.stream.fileno())
            current_after = release_builder.validate_release_source(root, snapshot.path)
            if (
                digest != snapshot.digest
                or size != snapshot.size
                or not _same_source_identity_and_metadata(
                    snapshot.opened_stat, after_hash
                )
                or not _same_source_identity_and_metadata(
                    snapshot.opened_stat,
                    current_after.stat_result,
                )
            ):
                raise ValueError("content, identity, or metadata changed")
        except (OSError, ValueError) as exc:
            failed_names.add(snapshot.name)
            errors.append(
                f"worktree source changed after freshness hash: {snapshot.name} ({exc})"
            )

    # Digest every source first, then place one cheap all-source identity/metadata
    # barrier immediately before returning. This prevents an early source from
    # changing while a later, larger source is still being rehashed.
    for snapshot in source_snapshots:
        if snapshot.name in failed_names:
            continue
        try:
            final_handle_stat = os.fstat(snapshot.stream.fileno())
            final_path_stat = release_builder.validate_release_source(
                root,
                snapshot.path,
            ).stat_result
            if not _same_source_identity_and_metadata(
                snapshot.opened_stat,
                final_handle_stat,
            ) or not _same_source_identity_and_metadata(
                snapshot.opened_stat,
                final_path_stat,
            ):
                raise ValueError("final identity or metadata fence changed")
        except (OSError, ValueError) as exc:
            errors.append(
                f"worktree source changed after freshness hash: {snapshot.name} ({exc})"
            )
    return errors


def validate_release_archive(
    archive_path: Path,
    *,
    version: str,
    root: Path = ROOT,
    expected_files: Iterable[Path] | None = None,
    required_entries: set[str] | None = None,
) -> ReleaseCheckResult:
    """Validate archive integrity and equality with the current source snapshot."""

    archive_path = _absolute_without_resolving(archive_path)
    errors: list[str] = []
    forbidden: list[str] = []
    missing: list[str] = []
    payload_count = 0

    archive_snapshot = _take_stable_file_snapshot(archive_path, label="release archive")
    sidecar_path = archive_path.with_suffix(archive_path.suffix + ".sha256")
    try:
        sidecar_snapshot = _take_stable_file_snapshot(
            sidecar_path,
            label="release checksum sidecar",
            maximum_size=1024,
        )
    except BaseException:
        archive_snapshot.close()
        raise
    with sidecar_snapshot.stream:
        actual_sidecar = sidecar_snapshot.stream.read()

    try:
        archive = zipfile.ZipFile(archive_snapshot.stream)
    except (zipfile.BadZipFile, OSError) as exc:
        archive_snapshot.close()
        raise ReleaseValidationError([f"invalid release archive: {exc}"]) from exc

    with archive_snapshot.stream, archive:
        infos = archive.infolist()
        names = [info.filename for info in infos]
        name_counts = Counter(names)
        duplicate_names = sorted(
            name for name, count in name_counts.items() if count != 1
        )
        if duplicate_names:
            errors.append(f"duplicate archive entries: {', '.join(duplicate_names)}")
        if len(names) != len({name.casefold() for name in names}):
            errors.append("case-insensitive duplicate archive entries")
        if conflict_error := _portable_path_conflict_error(
            "archive",
            (*names, RELEASE_MANIFEST, RELEASE_MANIFEST_DIGEST),
        ):
            errors.append(conflict_error)

        for info in infos:
            if path_error := _archive_path_error(info.filename):
                errors.append(f"unsafe archive path {info.filename!r}: {path_error}")
            if info.is_dir():
                errors.append(f"directory entries are not allowed: {info.filename}")
            unix_type = stat.S_IFMT(info.external_attr >> 16)
            if unix_type not in {0, stat.S_IFREG}:
                errors.append(
                    f"non-regular archive entry is not allowed: {info.filename}"
                )

        unique_names = set(names)
        forbidden = sorted(
            name
            for name in unique_names
            if any(pattern.search(name) for pattern in FORBIDDEN_PATTERNS)
        )
        required = (
            set(required_entries)
            if required_entries is not None
            else COMMON_REQUIRED_ENTRIES | VERSION_REQUIRED_ENTRIES.get(version, set())
        )
        missing = sorted(required - unique_names)

        manifest_records: dict[str, tuple[str, int]] = {}
        metadata_names = {RELEASE_MANIFEST, RELEASE_MANIFEST_DIGEST}
        payload_infos = [info for info in infos if info.filename not in metadata_names]
        payload_count = len(payload_infos)

        if name_counts[RELEASE_MANIFEST] != 1:
            errors.append(f"archive must contain exactly one {RELEASE_MANIFEST}")
        if name_counts[RELEASE_MANIFEST_DIGEST] != 1:
            errors.append(f"archive must contain exactly one {RELEASE_MANIFEST_DIGEST}")

        manifest_bytes: bytes | None = None
        if name_counts[RELEASE_MANIFEST] == 1:
            manifest_bytes = _read_archive_bytes(archive, RELEASE_MANIFEST, errors)
        if manifest_bytes is not None and name_counts[RELEASE_MANIFEST_DIGEST] == 1:
            expected_line = f"{hashlib.sha256(manifest_bytes).hexdigest()}  {RELEASE_MANIFEST}\n".encode(
                "ascii"
            )
            actual_line = _read_archive_bytes(archive, RELEASE_MANIFEST_DIGEST, errors)
            if actual_line is not None and actual_line != expected_line:
                errors.append("release manifest self-digest mismatch")

        manifest: object | None = None
        if manifest_bytes is not None:
            try:
                manifest = json.loads(
                    manifest_bytes.decode("utf-8"),
                    object_pairs_hook=_object_without_duplicate_keys,
                )
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
                errors.append(f"invalid release manifest: {exc}")

        if isinstance(manifest, dict):
            if manifest.get("schema") != RELEASE_MANIFEST_SCHEMA:
                errors.append("unsupported release manifest schema")
            if manifest.get("version") != version:
                errors.append("release manifest version mismatch")
            if manifest.get("hash_algorithm") != "sha256":
                errors.append("release manifest hash algorithm must be sha256")
            raw_records = manifest.get("files")
            if not isinstance(raw_records, list):
                errors.append("release manifest files must be a list")
            else:
                record_names: list[str] = []
                for index, record in enumerate(raw_records):
                    if not isinstance(record, dict):
                        errors.append(
                            f"release manifest file record {index} must be an object"
                        )
                        continue
                    name = record.get("path")
                    digest = record.get("sha256")
                    size = record.get("size")
                    if not isinstance(name, str):
                        errors.append(
                            f"release manifest file record {index} has no valid path"
                        )
                        continue
                    record_names.append(name)
                    if path_error := _archive_path_error(name):
                        errors.append(f"unsafe manifest path {name!r}: {path_error}")
                        continue
                    if name in metadata_names:
                        errors.append(
                            f"release manifest cannot list reserved metadata entry: {name}"
                        )
                        continue
                    if (
                        not isinstance(digest, str)
                        or re.fullmatch(r"[0-9a-f]{64}", digest) is None
                    ):
                        errors.append(f"release manifest has invalid sha256 for {name}")
                        continue
                    if not isinstance(size, int) or isinstance(size, bool) or size < 0:
                        errors.append(f"release manifest has invalid size for {name}")
                        continue
                    if name in manifest_records:
                        errors.append(f"duplicate release manifest path: {name}")
                        continue
                    manifest_records[name] = (digest, size)
                if len(record_names) != len(set(record_names)):
                    errors.append("duplicate paths in release manifest")
                if len(record_names) != len({name.casefold() for name in record_names}):
                    errors.append(
                        "case-insensitive duplicate paths in release manifest"
                    )
                portable_manifest_names = (
                    *record_names,
                    RELEASE_MANIFEST,
                    RELEASE_MANIFEST_DIGEST,
                )
                if collision_error := _portable_path_collision_error(
                    "manifest",
                    portable_manifest_names,
                ):
                    errors.append(collision_error)
                if conflict_error := _portable_path_conflict_error(
                    "manifest",
                    portable_manifest_names,
                ):
                    errors.append(conflict_error)
        elif manifest is not None:
            errors.append("release manifest root must be an object")

        payload_by_name = {
            info.filename: info
            for info in payload_infos
            if name_counts[info.filename] == 1
        }
        payload_names = set(payload_by_name)
        manifest_names = set(manifest_records)
        extra_payload = sorted(payload_names - manifest_names)
        missing_payload = sorted(manifest_names - payload_names)
        if extra_payload:
            errors.append(
                f"archive entries absent from manifest: {', '.join(extra_payload)}"
            )
        if missing_payload:
            errors.append(
                f"manifest entries absent from archive: {', '.join(missing_payload)}"
            )

        for name in sorted(payload_names & manifest_names):
            try:
                with archive.open(payload_by_name[name]) as stream:
                    actual_digest, actual_size = _stream_sha256(stream)
            except (
                zipfile.BadZipFile,
                RuntimeError,
                EOFError,
                OSError,
                zlib.error,
            ) as exc:
                errors.append(f"cannot read archive entry: {name} ({exc})")
                continue
            expected_digest, expected_size = manifest_records[name]
            if actual_size != expected_size:
                errors.append(f"archive content size mismatch: {name}")
            if actual_digest != expected_digest:
                errors.append(f"archive content hash mismatch: {name}")

    current_files = (
        expected_files
        if expected_files is not None
        else release_builder.release_files()
    )
    with ExitStack() as source_stack:
        current_records, source_snapshots, source_errors = _current_source_records(
            root,
            current_files,
            source_stack,
        )
        errors.extend(source_errors)
        current_names = set(current_records)
        manifest_names = set(manifest_records)
        newer_sources = sorted(current_names - manifest_names)
        stale_archive_entries = sorted(manifest_names - current_names)
        if newer_sources:
            errors.append(
                f"worktree sources absent from archive: {', '.join(newer_sources)}"
            )
        if stale_archive_entries:
            errors.append(
                f"archive sources absent from worktree: {', '.join(stale_archive_entries)}"
            )
        for name in sorted(current_names & manifest_names):
            if current_records[name] != manifest_records[name]:
                errors.append(f"stale worktree content differs from archive: {name}")

        archive_digest = archive_snapshot.digest
        expected_sidecar = f"{archive_digest}  {archive_path.name}\n".encode("ascii")
        if actual_sidecar != expected_sidecar:
            errors.append(
                "release checksum sidecar does not match the validated archive"
            )

        if errors or forbidden or missing:
            raise ReleaseValidationError(errors, forbidden=forbidden, missing=missing)

        _assert_snapshot_path_unchanged(archive_snapshot)
        _assert_snapshot_path_unchanged(sidecar_snapshot)
        source_fence_errors = _current_source_fence(root, source_snapshots)
        if source_fence_errors:
            raise ReleaseValidationError(source_fence_errors)

        return ReleaseCheckResult(
            archive_path=archive_path,
            payload_files=payload_count,
            archive_sha256=archive_digest,
        )


def latest_release(version: str) -> Path:
    candidates = sorted(
        RELEASES.glob(f"AI-Knowledge-OS-Pro-{version}-*.zip"),
        key=lambda item: item.stat().st_mtime,
    )
    if not candidates:
        raise SystemExit(f"No release zip found for {version}.")
    return candidates[-1]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inspect an AI Knowledge OS Pro release archive."
    )
    parser.add_argument("--version", default="V5.7.1")
    parser.add_argument("--path", type=Path)
    args = parser.parse_args()

    archive_path = args.path if args.path else latest_release(args.version)
    try:
        result = validate_release_archive(archive_path, version=args.version)
    except ReleaseValidationError as exc:
        if exc.forbidden:
            print("Forbidden release entries:")
            for name in exc.forbidden:
                print(f"- {name}")
        if exc.missing:
            print("Missing required release entries:")
            for name in exc.missing:
                print(f"- {name}")
        if exc.errors:
            print("Release integrity errors:")
            for error in exc.errors:
                print(f"- {error}")
        raise SystemExit(1)

    print(f"Release check passed: {result.archive_path.name}")
    print(
        f"files={result.payload_files} forbidden=0 missing=0 manifest=verified freshness=current"
    )
    print(f"sha256={result.archive_sha256}")


if __name__ == "__main__":
    main()
