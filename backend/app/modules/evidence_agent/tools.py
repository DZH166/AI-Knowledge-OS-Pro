from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
import json
from types import MappingProxyType
from typing import Mapping


class ToolEffect(StrEnum):
    READ_EVIDENCE = "read_evidence"
    MUTATE_LOCAL = "mutate_local"
    EXECUTE_CODE = "execute_code"
    EXTERNAL_SEND = "external_send"


@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    version: str
    effect: ToolEffect
    allowed_arguments: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ToolIntent:
    name: str
    arguments: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class AuthorizedToolCall:
    name: str
    version: str
    effect: ToolEffect
    arguments: Mapping[str, object]
    arguments_digest: str


class ToolPolicyDenied(PermissionError):
    def __init__(self, reason: str) -> None:
        super().__init__(f"Tool policy denied: {reason}")
        self.reason = reason


class ToolRegistry:
    """Closed, schema-shaped registry; evidence text can never add capabilities."""

    def __init__(self, *, specs: tuple[ToolSpec, ...], allow_protected: bool = False) -> None:
        if len({item.name for item in specs}) != len(specs):
            raise ValueError("Tool names must be unique.")
        self.specs = specs
        self._by_name = {item.name: item for item in specs}
        self._allow_protected = allow_protected

    @classmethod
    def production_read_only(cls) -> "ToolRegistry":
        return cls(
            specs=cls._read_only_specs(),
        )

    @classmethod
    def production(cls) -> "ToolRegistry":
        """Production capabilities, including writes that require exact approval."""

        return cls(
            specs=(
                *cls._read_only_specs(),
                ToolSpec(
                    "publish_artifact",
                    "2",
                    ToolEffect.MUTATE_LOCAL,
                    (
                        "artifact_id",
                        "artifact_digest",
                        "expected_status",
                        "run_id",
                    ),
                ),
            ),
            allow_protected=True,
        )

    @staticmethod
    def _read_only_specs() -> tuple[ToolSpec, ...]:
        return (
            ToolSpec("search_evidence", "1", ToolEffect.READ_EVIDENCE, ("query", "revision_ids")),
            ToolSpec("open_evidence", "1", ToolEffect.READ_EVIDENCE, ("evidence_id",)),
            ToolSpec(
                "read_neighbors",
                "1",
                ToolEffect.READ_EVIDENCE,
                ("evidence_id", "before", "after"),
            ),
            ToolSpec("inspect_source", "1", ToolEffect.READ_EVIDENCE, ("source_id",)),
        )

    def validate_proposal(
        self,
        intent: ToolIntent,
        *,
        pinned_revision_ids: tuple[int, ...],
    ) -> AuthorizedToolCall:
        """Validate and freeze a proposal without granting execution authority."""

        return self._validated_call(intent, pinned_revision_ids=pinned_revision_ids)

    def authorize(
        self,
        intent: ToolIntent,
        *,
        pinned_revision_ids: tuple[int, ...],
        approved_digest: str | None = None,
    ) -> AuthorizedToolCall:
        authorized = self._validated_call(
            intent,
            pinned_revision_ids=pinned_revision_ids,
        )
        if authorized.effect is not ToolEffect.READ_EVIDENCE:
            if not self._allow_protected:
                raise ToolPolicyDenied("protected_effect_not_registered")
            if approved_digest != authorized.arguments_digest:
                raise ToolPolicyDenied("approval_digest_mismatch")
        return authorized

    def _validated_call(
        self,
        intent: ToolIntent,
        *,
        pinned_revision_ids: tuple[int, ...],
    ) -> AuthorizedToolCall:
        spec = self._by_name.get(intent.name)
        if spec is None:
            raise ToolPolicyDenied("unknown_tool")
        unknown_arguments = set(intent.arguments) - set(spec.allowed_arguments)
        if unknown_arguments:
            raise ToolPolicyDenied("unknown_arguments")
        revision_ids = intent.arguments.get("revision_ids")
        if revision_ids is not None:
            if not isinstance(revision_ids, (list, tuple)):
                raise ToolPolicyDenied("invalid_scope")
            requested = {int(item) for item in revision_ids}
            if not requested.issubset(set(pinned_revision_ids)):
                raise ToolPolicyDenied("scope_escape")
        if spec.name == "publish_artifact":
            if set(intent.arguments) != set(spec.allowed_arguments):
                raise ToolPolicyDenied("missing_arguments")
            artifact_id = intent.arguments.get("artifact_id")
            artifact_digest = intent.arguments.get("artifact_digest")
            run_id = intent.arguments.get("run_id")
            expected_status = intent.arguments.get("expected_status")
            if (
                not isinstance(artifact_id, str)
                or not artifact_id.strip()
                or not isinstance(artifact_digest, str)
                or len(artifact_digest) != 64
                or any(character not in "0123456789abcdef" for character in artifact_digest.casefold())
                or not isinstance(run_id, str)
                or not run_id.strip()
                or expected_status != "draft"
            ):
                raise ToolPolicyDenied("invalid_arguments")
        digest = self.proposal_digest(intent)
        return AuthorizedToolCall(
            name=spec.name,
            version=spec.version,
            effect=spec.effect,
            arguments=MappingProxyType(dict(intent.arguments)),
            arguments_digest=digest,
        )

    @staticmethod
    def proposal_digest(intent: ToolIntent) -> str:
        payload = json.dumps(
            {"name": intent.name, "arguments": dict(intent.arguments)},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return sha256(payload.encode("utf-8")).hexdigest()


def artifact_content_digest(
    *,
    title: str,
    body_markdown: str,
    structured_payload_json: str,
) -> str:
    payload = json.dumps(
        {
            "title": title,
            "body_markdown": body_markdown,
            "structured_payload_json": structured_payload_json,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(payload.encode("utf-8")).hexdigest()
