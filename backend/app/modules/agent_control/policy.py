from __future__ import annotations

from hashlib import sha256
import json


_POLICY_FACTS = {
    "agent_control": "1",
    "claim_calibration": "conflict_abstention_v1",
    "evaluation_agent": "evaluation-agent-v1",
    "evidence_tool_selection": "evidence-gap-readonly:1",
    "projection_replay": "1",
}


def current_policy_fingerprint() -> str:
    rendered = json.dumps(_POLICY_FACTS, sort_keys=True, separators=(",", ":"))
    return sha256(rendered.encode("utf-8")).hexdigest()
