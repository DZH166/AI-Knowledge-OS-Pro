from __future__ import annotations

from dataclasses import fields

from app.modules.agent_policy.config import RetrievalPolicyConfig
from app.modules.agent_policy.contracts import PolicyConfigChange, PolicyConfigComparison


def compare_policy_configs(
    left: RetrievalPolicyConfig,
    right: RetrievalPolicyConfig,
) -> PolicyConfigComparison:
    if left.schema_version != right.schema_version:
        return PolicyConfigComparison(
            compatible=False,
            incompatibility_reasons=("schema_version_mismatch",),
            changes=(),
        )
    changes = tuple(
        PolicyConfigChange(
            field=item.name,
            left=getattr(left, item.name),
            right=getattr(right, item.name),
        )
        for item in fields(RetrievalPolicyConfig)
        if item.name != "schema_version" and getattr(left, item.name) != getattr(right, item.name)
    )
    return PolicyConfigComparison(
        compatible=True,
        incompatibility_reasons=(),
        changes=changes,
    )
