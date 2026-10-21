from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from hashlib import sha256
import json


@dataclass(frozen=True, slots=True)
class RetrievalPolicyConfig:
    schema_version: int = 1
    factual_top_k: int = 8
    comparative_top_k: int = 14
    temporal_top_k: int = 12
    minimum_score_millis: int = 0
    max_hits_per_source: int = 3
    neighbor_before: int = 1
    neighbor_after: int = 1

    def __post_init__(self) -> None:
        values = asdict(self)
        if any(type(values[item.name]) is not int for item in fields(self)):
            raise ValueError("Every retrieval policy value must be an integer.")
        if self.schema_version != 1:
            raise ValueError("Only retrieval policy schema_version 1 is supported.")
        for name in ("factual_top_k", "comparative_top_k", "temporal_top_k"):
            if not 1 <= values[name] <= 50:
                raise ValueError(f"{name} must be between 1 and 50.")
        if not 0 <= self.minimum_score_millis <= 1_000:
            raise ValueError("minimum_score_millis must be between 0 and 1000.")
        if not 1 <= self.max_hits_per_source <= 20:
            raise ValueError("max_hits_per_source must be between 1 and 20.")
        for name in ("neighbor_before", "neighbor_after"):
            if not 0 <= values[name] <= 3:
                raise ValueError(f"{name} must be between 0 and 3.")

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


def canonical_policy_json(config: RetrievalPolicyConfig) -> str:
    return json.dumps(
        config.as_dict(),
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def policy_fingerprint(config: RetrievalPolicyConfig) -> str:
    return sha256(canonical_policy_json(config).encode("utf-8")).hexdigest()


def policy_config_from_snapshot(value: str, expected_fingerprint: str) -> RetrievalPolicyConfig:
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError("Policy snapshot is not valid JSON.") from exc
    if not isinstance(payload, dict):
        raise ValueError("Policy snapshot must be a JSON object.")
    try:
        config = RetrievalPolicyConfig(**payload)
    except (TypeError, ValueError) as exc:
        raise ValueError("Policy snapshot does not match the strict configuration schema.") from exc
    if canonical_policy_json(config) != value or policy_fingerprint(config) != expected_fingerprint:
        raise ValueError("Policy snapshot does not match its canonical fingerprint.")
    return config
