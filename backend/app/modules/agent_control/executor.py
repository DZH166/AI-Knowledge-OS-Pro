from __future__ import annotations

import json
from hashlib import sha256
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from typing import Callable, Mapping, Protocol

from app.modules.agent_policy.config import policy_config_from_snapshot


class EvaluationExecutionError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class EvaluationExecutor(Protocol):
    def run(
        self,
        evaluation_id: str,
        policy_snapshot: "EvaluationPolicySnapshot | None" = None,
    ) -> Mapping[str, object]: ...


@dataclass(frozen=True, slots=True)
class EvaluationPolicySnapshot:
    policy_id: str
    policy_version: int
    config_sha256: str
    config_json: str

    def __post_init__(self) -> None:
        if not self.policy_id.strip() or self.policy_version <= 0:
            raise ValueError("Evaluation policy identity must be non-empty and positive.")
        policy_config_from_snapshot(self.config_json, self.config_sha256)


RunProcess = Callable[..., subprocess.CompletedProcess[str]]
ROOT = Path(__file__).resolve().parents[4]
_MAX_REPORT_BYTES = 5 * 1024 * 1024
_ALLOWED_ENVIRONMENT_KEYS = frozenset(
    {
        "APPDATA",
        "COMSPEC",
        "HOME",
        "LANG",
        "LC_ALL",
        "LOCALAPPDATA",
        "PATH",
        "PATHEXT",
        "SYSTEMROOT",
        "TEMP",
        "TMP",
        "TMPDIR",
        "TZ",
        "USERPROFILE",
        "WINDIR",
    }
)
_DISABLED_PROVIDER_KEYS = (
    "EMBEDDING_API_KEY",
    "LLM_API_KEY",
    "OCR_API_KEY",
    "OPENAI_API_KEY",
    "QDRANT_API_KEY",
    "RERANK_API_KEY",
    "TRANSCRIPTION_API_KEY",
)


class FixedSubprocessEvaluationAdapter:
    """Execute only the reviewed fixed deterministic evaluator in an isolated directory."""

    def __init__(
        self,
        *,
        root: Path = ROOT,
        timeout_seconds: int = 900,
        temporary_root: Path | None = None,
        run_process: RunProcess = subprocess.run,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._root = root.resolve()
        self._timeout_seconds = timeout_seconds
        self._temporary_root = temporary_root.resolve() if temporary_root else None
        self._run_process = run_process

    def run(
        self,
        evaluation_id: str,
        policy_snapshot: EvaluationPolicySnapshot | None = None,
    ) -> Mapping[str, object]:
        script = self._root / "scripts" / "evaluate_agentic_rag.py"
        dataset = self._root / "evaluation" / "v5" / "cases.jsonl"
        if not script.is_file() or not dataset.is_file():
            raise EvaluationExecutionError(
                "EVALUATION_RUNTIME_MISSING",
                "The fixed evaluator or dataset is unavailable.",
            )
        if self._temporary_root is not None:
            self._temporary_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix=f"suzhi-evaluation-{_safe_identifier(evaluation_id)}-",
            dir=self._temporary_root,
        ) as directory:
            workspace = Path(directory)
            database_path = workspace / "evaluation.db"
            report_path = workspace / "report.json"
            policy_path = workspace / "policy.json"
            command = [
                sys.executable,
                str(script),
                "--mode",
                "demo",
                "--database-path",
                str(database_path),
                "--dataset",
                str(dataset),
                "--output",
                str(report_path),
            ]
            if policy_snapshot is not None:
                policy_payload = {
                    "policy_id": policy_snapshot.policy_id,
                    "policy_version": policy_snapshot.policy_version,
                    "config_sha256": policy_snapshot.config_sha256,
                    "config": json.loads(policy_snapshot.config_json),
                }
                policy_path.write_text(
                    json.dumps(policy_payload, sort_keys=True, separators=(",", ":")) + "\n",
                    encoding="utf-8",
                )
                command.extend(("--policy-config", str(policy_path)))
            try:
                completed = self._run_process(
                    command,
                    cwd=self._root,
                    env=_scrubbed_environment(),
                    text=True,
                    capture_output=True,
                    timeout=self._timeout_seconds,
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                raise EvaluationExecutionError(
                    "EVALUATION_TIMEOUT",
                    "The fixed deterministic evaluation exceeded its time budget.",
                ) from exc
            except OSError as exc:
                raise EvaluationExecutionError(
                    "EVALUATION_EXECUTOR_FAILED",
                    "The fixed deterministic evaluator could not be started.",
                ) from exc
            if completed.returncode not in {0, 1}:
                raise EvaluationExecutionError(
                    "EVALUATION_EXECUTOR_FAILED",
                    f"The fixed evaluator exited with code {completed.returncode}.",
                )
            if report_path.is_symlink() or not report_path.is_file():
                raise EvaluationExecutionError(
                    "EVALUATION_REPORT_INVALID",
                    "The fixed evaluator did not produce a regular report file.",
                )
            if report_path.stat().st_size > _MAX_REPORT_BYTES:
                raise EvaluationExecutionError(
                    "EVALUATION_REPORT_INVALID",
                    "The fixed evaluator report exceeded the size limit.",
                )
            try:
                payload = json.loads(report_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                raise EvaluationExecutionError(
                    "EVALUATION_REPORT_INVALID",
                    "The fixed evaluator report is not valid UTF-8 JSON.",
                ) from exc
            if not isinstance(payload, Mapping):
                raise EvaluationExecutionError(
                    "EVALUATION_REPORT_INVALID",
                    "The fixed evaluator report must be a JSON object.",
                )
            provenance = payload.get("provenance")
            dataset_info = payload.get("dataset")
            def digest(path: Path) -> str:
                return sha256(path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")).hexdigest()
            if (
                not isinstance(provenance, Mapping) or not isinstance(dataset_info, Mapping)
                or provenance.get("evaluator_sha256") != digest(script)
                or dataset_info.get("sha256") != digest(dataset)
            ):
                raise EvaluationExecutionError(
                    "EVALUATION_PROVENANCE_MISMATCH",
                    "Report does not identify the fixed evaluator and dataset that were executed.",
                )
            return payload


def _scrubbed_environment() -> dict[str, str]:
    environment = {
        key.upper(): value
        for key, value in os.environ.items()
        if key.upper() in _ALLOWED_ENVIRONMENT_KEYS
    }
    environment.update(
        {
            "DEMO_MODE": "true",
            "PYTHONIOENCODING": "utf-8",
            **{key: "" for key in _DISABLED_PROVIDER_KEYS},
        }
    )
    return environment


def _safe_identifier(value: str) -> str:
    safe = "".join(character if character.isalnum() else "-" for character in value).strip("-")
    return (safe or "run")[:48]
