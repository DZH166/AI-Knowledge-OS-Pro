from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from hashlib import sha256
import json
import time
from typing import Callable
from uuid import uuid4

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.core.errors import ServiceError
from app.models.agent_policy import AgentPolicyActivation, AgentPolicyCommand, AgentPolicyVersion
from app.models.agent_run import AgentRun
from app.modules.agent_control.sanitization import contains_sensitive_text, sanitize_fact
from app.modules.agent_policy.activation_gate import require_matching_fixed_evaluation
from app.modules.agent_policy.comparison import compare_policy_configs
from app.modules.agent_policy.config import (
    RetrievalPolicyConfig,
    canonical_policy_json,
    policy_fingerprint,
)
from app.modules.agent_policy.contracts import (
    ActivatePolicy,
    AgentPolicyCommand as PolicyCommand,
    AgentPolicyQuery,
    AgentPolicyResult,
    ComparePolicies,
    CreatePolicy,
    GetActivePolicy,
    GetPolicy,
    ListPolicies,
    PolicyCatalog,
    PolicyComparison,
    PolicyDetail,
    PolicyReceipt,
    PolicySimulation,
    PolicyStatus,
    PolicySummary,
    RollbackPolicy,
    SimulatePolicy,
)
from app.modules.agent_policy.simulation import simulate_policy_decisions
from app.modules.agent_policy.recorded_decisions import load_recorded_policy_decisions


SessionFactory = Callable[[], Session]
_CREATE_ATTEMPTS = 6


class SqlAgentPolicy:
    def __init__(
        self,
        session_factory: SessionFactory,
        *,
        utcnow: Callable[[], datetime] | None = None,
    ) -> None:
        self._sessions = session_factory
        self._utcnow = utcnow or (lambda: datetime.now(UTC))

    def submit(self, command: PolicyCommand) -> PolicyReceipt:
        if isinstance(command, CreatePolicy):
            return self._create(command)
        if isinstance(command, ActivatePolicy):
            return self._activate(command)
        if isinstance(command, RollbackPolicy):
            return self._rollback(command)
        raise TypeError(f"Unsupported Agent policy command: {type(command).__name__}")

    def inspect(self, query: AgentPolicyQuery) -> AgentPolicyResult:
        with self._sessions() as session:
            if isinstance(query, ListPolicies):
                statement = select(AgentPolicyVersion).order_by(
                    AgentPolicyVersion.version.desc(),
                    AgentPolicyVersion.id.desc(),
                )
                if query.status is not None:
                    statement = statement.where(AgentPolicyVersion.status == query.status.value)
                rows = session.scalars(statement.limit(max(1, min(query.limit, 100)))).all()
                return PolicyCatalog(items=tuple(self._summary(item) for item in rows))
            if isinstance(query, GetPolicy):
                return self._detail(self._required_policy(session, query.policy_id))
            if isinstance(query, GetActivePolicy):
                return self._detail(self._active_policy(session))
            if isinstance(query, ComparePolicies):
                left = self._detail(self._required_policy(session, query.left_id))
                right = self._detail(self._required_policy(session, query.right_id))
                comparison = compare_policy_configs(left.config, right.config)
                return PolicyComparison(
                    left_id=left.id,
                    right_id=right.id,
                    left_fingerprint=left.config_sha256,
                    right_fingerprint=right.config_sha256,
                    compatible=comparison.compatible,
                    incompatibility_reasons=comparison.incompatibility_reasons,
                    changes=comparison.changes,
                )
        raise TypeError(f"Unsupported Agent policy query: {type(query).__name__}")

    def simulate(self, query: SimulatePolicy) -> PolicySimulation:
        with self._sessions() as session:
            run = session.get(AgentRun, query.run_id)
            if run is None:
                raise ServiceError(code="RUN_NOT_FOUND", message="Agent run not found.", status_code=404)
            policy = self._detail(self._required_policy(session, query.policy_id))
            recorded = load_recorded_policy_decisions(session, run.id)
        return simulate_policy_decisions(
            run_id=run.id,
            policy_id=policy.id,
            policy_version=policy.version,
            config=policy.config,
            recorded=recorded,
        )

    def _create(self, command: CreatePolicy) -> PolicyReceipt:
        label, payload_hash = self._prepare_create(command)
        for attempt in range(_CREATE_ATTEMPTS):
            try:
                with self._sessions() as session, session.begin():
                    return self._insert_draft(session, command, label, payload_hash)
            except (IntegrityError, OperationalError) as exc:
                replay = self._replay_after_conflict(command.request_id, payload_hash)
                if replay is not None:
                    return replay
                if attempt + 1 >= _CREATE_ATTEMPTS:
                    raise ServiceError(
                        code="POLICY_WRITE_CONFLICT",
                        message="Concurrent policy creation could not allocate a version; retry.",
                        status_code=409,
                    ) from exc
                time.sleep(0.01 * (attempt + 1))
        raise AssertionError("Policy create retry loop exited unexpectedly.")

    def create_in_transaction(self, session: Session, command: CreatePolicy) -> PolicyReceipt:
        """SQL composition seam: caller owns commit/rollback, including its audit."""
        label, payload_hash = self._prepare_create(command)
        return self._insert_draft(session, command, label, payload_hash)

    def _prepare_create(self, command: CreatePolicy) -> tuple[str, str]:
        label = command.label.strip()
        self._validate_identifier(command.request_id, "request_id")
        self._validate_identifier(command.base_policy_id, "base_policy_id")
        if not label or len(label) > 120 or contains_sensitive_text(label):
            raise ServiceError(
                code="POLICY_INPUT_REJECTED",
                message="Policy label is blank, too long, or secret-looking.",
                status_code=422,
            )
        payload_hash = self._payload_hash(
            {
                "command": "create",
                "label": label,
                "base_policy_id": command.base_policy_id,
                "config": command.config.as_dict(),
            }
        )
        return label, payload_hash

    def _insert_draft(
        self, session: Session, command: CreatePolicy, label: str, payload_hash: str
    ) -> PolicyReceipt:
        session.execute(update(AgentPolicyVersion).where(
            AgentPolicyVersion.id == command.base_policy_id
        ).values(id=AgentPolicyVersion.id).execution_options(synchronize_session=False))
        replay = self._replay(session, command.request_id, payload_hash)
        if replay is not None:
            return replay
        base = self._required_policy(session, command.base_policy_id)
        version = int(
            session.scalar(
                select(func.coalesce(func.max(AgentPolicyVersion.version), 0)).where(
                    AgentPolicyVersion.policy_key == base.policy_key
                )
            )
            or 0
        ) + 1
        policy = AgentPolicyVersion(
            id=str(uuid4()),
            policy_key=base.policy_key,
            version=version,
            label=label,
            status=PolicyStatus.DRAFT.value,
            config_schema_version=command.config.schema_version,
            config_json=canonical_policy_json(command.config),
            config_sha256=policy_fingerprint(command.config),
            base_policy_id=base.id,
            created_by="user:local",
            has_been_active=0,
        )
        session.add(policy)
        session.flush([policy])
        receipt = PolicyReceipt(
            command_id=str(uuid4()),
            policy_id=policy.id,
            version=policy.version,
            status=PolicyStatus.DRAFT,
            active_policy_id=self._active_policy(session).id,
        )
        self._record_command(
            session,
            receipt.command_id,
            command.request_id,
            "create",
            payload_hash,
            receipt,
        )
        return receipt

    def _activate(self, command: ActivatePolicy) -> PolicyReceipt:
        payload_hash = self._payload_hash(asdict(command) | {"command": "activate"})
        return self._change_active(
            request_id=command.request_id,
            payload_hash=payload_hash,
            target_policy_id=command.policy_id,
            expected_active_policy_id=command.expected_active_policy_id,
            action="activate",
            evaluation_id=command.evaluation_id,
        )

    def _rollback(self, command: RollbackPolicy) -> PolicyReceipt:
        payload_hash = self._payload_hash(asdict(command) | {"command": "rollback"})
        return self._change_active(
            request_id=command.request_id,
            payload_hash=payload_hash,
            target_policy_id=command.policy_id,
            expected_active_policy_id=command.expected_active_policy_id,
            action="rollback",
            evaluation_id=None,
        )

    def _change_active(
        self,
        *,
        request_id: str,
        payload_hash: str,
        target_policy_id: str,
        expected_active_policy_id: str,
        action: str,
        evaluation_id: str | None,
    ) -> PolicyReceipt:
        for value, label in (
            (request_id, "request_id"),
            (target_policy_id, "policy_id"),
            (expected_active_policy_id, "expected_active_policy_id"),
        ):
            self._validate_identifier(value, label)
        if action == "activate":
            self._validate_identifier(evaluation_id or "", "evaluation_id")
        try:
            with self._sessions() as session, session.begin():
                replay = self._replay(session, request_id, payload_hash)
                if replay is not None:
                    return replay
                active = self._active_policy(session)
                if active.id != expected_active_policy_id:
                    raise ServiceError(
                        code="POLICY_ACTIVE_CONFLICT",
                        message="The active policy changed; reload before applying this command.",
                        status_code=409,
                    )
                target = self._required_policy(session, target_policy_id)
                if target.id == active.id:
                    raise ServiceError(
                        code="POLICY_ALREADY_ACTIVE",
                        message="The selected policy is already active.",
                        status_code=409,
                    )
                if action == "activate":
                    if target.status != PolicyStatus.DRAFT.value:
                        raise ServiceError(
                            code="POLICY_NOT_ACTIVATABLE",
                            message="Only a draft policy can be activated.",
                            status_code=409,
                        )
                    require_matching_fixed_evaluation(session, target, evaluation_id or "")
                elif target.status != PolicyStatus.RETIRED.value or not target.has_been_active:
                    raise ServiceError(
                        code="POLICY_NOT_ROLLBACK_TARGET",
                        message="Rollback requires a previously active retired policy.",
                        status_code=409,
                    )
                now = self._utcnow()
                active.status = PolicyStatus.RETIRED.value
                active.retired_at = now
                session.flush([active])
                target.status = PolicyStatus.ACTIVE.value
                target.has_been_active = 1
                target.activated_at = now
                target.retired_at = None
                session.flush([target])
                receipt = PolicyReceipt(
                    command_id=str(uuid4()),
                    policy_id=target.id,
                    version=target.version,
                    status=PolicyStatus.ACTIVE,
                    active_policy_id=target.id,
                )
                self._record_command(
                    session,
                    receipt.command_id,
                    request_id,
                    action,
                    payload_hash,
                    receipt,
                )
                session.flush()
                session.add(
                    AgentPolicyActivation(
                        id=str(uuid4()),
                        command_id=receipt.command_id,
                        action=action,
                        policy_id=target.id,
                        previous_policy_id=active.id,
                        evaluation_id=evaluation_id,
                    )
                )
                return receipt
        except (IntegrityError, OperationalError) as exc:
            replay = self._replay_after_conflict(request_id, payload_hash)
            if replay is not None:
                return replay
            raise ServiceError(
                code="POLICY_WRITE_CONFLICT",
                message="Concurrent policy activation conflicted; reload and retry.",
                status_code=409,
            ) from exc

    def _required_policy(self, session: Session, policy_id: str) -> AgentPolicyVersion:
        policy = session.get(AgentPolicyVersion, policy_id)
        if policy is None:
            raise ServiceError(code="POLICY_NOT_FOUND", message="Agent policy not found.", status_code=404)
        return policy

    @staticmethod
    def _active_policy(session: Session) -> AgentPolicyVersion:
        policies = session.scalars(
            select(AgentPolicyVersion).where(AgentPolicyVersion.status == PolicyStatus.ACTIVE.value).limit(2)
        ).all()
        if len(policies) != 1:
            raise ServiceError(
                code="POLICY_ACTIVE_STATE_INVALID",
                message="Exactly one active Agent policy is required.",
                status_code=503,
            )
        return policies[0]

    @staticmethod
    def _config(policy: AgentPolicyVersion) -> RetrievalPolicyConfig:
        try:
            payload = json.loads(policy.config_json)
            if not isinstance(payload, dict):
                raise ValueError("not an object")
            config = RetrievalPolicyConfig(**payload)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ServiceError(
                code="POLICY_STATE_INVALID",
                message="Stored Agent policy configuration is invalid.",
                status_code=500,
            ) from exc
        if canonical_policy_json(config) != policy.config_json or policy_fingerprint(config) != policy.config_sha256:
            raise ServiceError(
                code="POLICY_STATE_INVALID",
                message="Stored Agent policy fingerprint does not match its configuration.",
                status_code=500,
            )
        return config

    def _detail(self, policy: AgentPolicyVersion) -> PolicyDetail:
        summary = self._summary(policy)
        return PolicyDetail(**asdict(summary), config=self._config(policy))

    @staticmethod
    def _summary(policy: AgentPolicyVersion) -> PolicySummary:
        return PolicySummary(
            id=policy.id,
            policy_key=policy.policy_key,
            version=policy.version,
            label=sanitize_fact(policy.label, maximum_length=120),
            status=PolicyStatus(policy.status),
            config_sha256=policy.config_sha256,
            base_policy_id=policy.base_policy_id,
            has_been_active=bool(policy.has_been_active),
            created_at=_aware(policy.created_at),
            activated_at=_aware(policy.activated_at) if policy.activated_at else None,
            retired_at=_aware(policy.retired_at) if policy.retired_at else None,
        )

    @staticmethod
    def _validate_identifier(value: str, label: str) -> None:
        if not value.strip() or len(value) > 120 or contains_sensitive_text(value):
            raise ServiceError(
                code="POLICY_INPUT_REJECTED",
                message=f"{label} is blank, too long, or secret-looking.",
                status_code=422,
            )

    @staticmethod
    def _payload_hash(payload: object) -> str:
        rendered = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        return sha256(rendered.encode("utf-8")).hexdigest()

    @staticmethod
    def _record_command(
        session: Session,
        command_id: str,
        request_id: str,
        command_type: str,
        payload_hash: str,
        receipt: PolicyReceipt,
    ) -> None:
        session.add(
            AgentPolicyCommand(
                id=command_id,
                request_id=request_id,
                command_type=command_type,
                payload_hash=payload_hash,
                receipt_json=json.dumps(asdict(receipt), sort_keys=True, separators=(",", ":")),
            )
        )

    def _replay_after_conflict(self, request_id: str, payload_hash: str) -> PolicyReceipt | None:
        with self._sessions() as session:
            return self._replay(session, request_id, payload_hash)

    @staticmethod
    def _replay(session: Session, request_id: str, payload_hash: str) -> PolicyReceipt | None:
        command = session.scalar(
            select(AgentPolicyCommand).where(AgentPolicyCommand.request_id == request_id)
        )
        if command is None:
            return None
        if command.payload_hash != payload_hash:
            raise ServiceError(
                code="POLICY_IDEMPOTENCY_CONFLICT",
                message="The request id was already used with a different policy command.",
                status_code=409,
            )
        payload = json.loads(command.receipt_json)
        return PolicyReceipt(
            command_id=str(payload["command_id"]),
            policy_id=str(payload["policy_id"]),
            version=int(payload["version"]),
            status=PolicyStatus(payload["status"]),
            active_policy_id=str(payload["active_policy_id"]),
            replayed=True,
        )


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
