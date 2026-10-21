from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from hashlib import sha256
import json
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ServiceError
from app.models.agent_evaluation import AgentEvaluation
from app.models.agent_policy import AgentPolicyVersion
from app.models.agent_event import AgentCheckpoint, AgentEvent
from app.models.agent_run import AgentModelCall, AgentRun, AgentToolCall
from app.models.outbox import OutboxMessage
from app.modules.agent_control.comparison import compare_evaluations
from app.modules.agent_control.contracts import (
    AgentControlCommand,
    AgentControlQuery,
    AgentControlResult,
    CompareEvaluations,
    EvaluationCatalog,
    EvaluationDetail,
    EvaluationReceipt,
    EvaluationStatus,
    EvaluationSummary,
    ExecuteEvaluation,
    GetEvaluation,
    GetRunTrace,
    ListEvaluations,
    RecoverEvaluations,
    StartEvaluation,
)
from app.modules.agent_control.executor import EvaluationExecutionError, EvaluationExecutor
from app.modules.agent_control.executor import EvaluationPolicySnapshot
from app.modules.agent_control.policy import current_policy_fingerprint
from app.modules.agent_control.report import (
    EvaluationReportError,
    ValidatedEvaluationReport,
    validate_evaluation_report,
)
from app.modules.agent_control.sanitization import sanitize_fact
from app.modules.agent_control.trace import (
    TraceCheckpointInput,
    TraceEventInput,
    TraceModelCallInput,
    TraceRunInput,
    TraceToolCallInput,
    project_run_trace,
)
from app.modules.agent_control.triage import triage_evaluation_failure
from app.modules.agent_policy.config import canonical_policy_json, policy_config_from_snapshot
from app.modules.agent_policy.contracts import PolicyDetail


SessionFactory = Callable[[], Session]
PolicyResolver = Callable[[str | None], PolicyDetail]
TERMINAL_EVALUATION_STATUSES = {EvaluationStatus.PASSED.value, EvaluationStatus.FAILED.value}


class SqlAgentControl:
    def __init__(
        self,
        session_factory: SessionFactory,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        lease_seconds: int = 900,
        policy_resolver: PolicyResolver | None = None,
    ) -> None:
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        self._sessions = session_factory
        self._clock = clock
        self._lease_seconds = lease_seconds
        self._policy_resolver = policy_resolver

    def submit(self, command: AgentControlCommand) -> EvaluationReceipt:
        if not isinstance(command, StartEvaluation):
            raise TypeError(f"Unsupported AgentControl command: {type(command).__name__}")
        request_id = command.request_id.strip()
        label = command.label.strip()
        if not request_id or len(request_id) > 120:
            raise ServiceError(code="INVALID_EVALUATION_REQUEST_ID", message="Evaluation request id is invalid.", status_code=422)
        if not label or len(label) > 120:
            raise ServiceError(code="INVALID_EVALUATION_LABEL", message="Evaluation label is invalid.", status_code=422)
        policy = self._resolve_policy(command.policy_id)
        payload_hash = _digest(
            {
                "label": label,
                "mode": "deterministic_recording",
                "policy_id": policy.id if policy else None,
                "policy_fingerprint": policy.config_sha256 if policy else current_policy_fingerprint(),
            }
        )
        evaluation_id = str(uuid4())
        try:
            with self._sessions() as session, session.begin():
                existing = session.scalar(
                    select(AgentEvaluation).where(AgentEvaluation.request_id == request_id)
                )
                if existing is not None:
                    return self._replay_or_conflict(existing, payload_hash)
                evaluation = AgentEvaluation(
                    id=evaluation_id,
                    request_id=request_id,
                    request_payload_hash=payload_hash,
                    label=label,
                    mode="deterministic_recording",
                    status=EvaluationStatus.QUEUED.value,
                    policy_fingerprint=(policy.config_sha256 if policy else current_policy_fingerprint()),
                    policy_version_id=policy.id if policy else None,
                    policy_snapshot_json=canonical_policy_json(policy.config) if policy else None,
                    case_count=0,
                    failure_case_count=0,
                    provider_boundary="Deterministic recording only; not a real-model quality benchmark.",
                    attempt=0,
                )
                outbox = OutboxMessage(
                    id=str(uuid4()),
                    topic="agent.evaluate",
                    aggregate_type="agent_evaluation",
                    aggregate_id=evaluation_id,
                    dedupe_key=f"agent.evaluate:{evaluation_id}",
                    payload_json=_canonical_json({"evaluation_id": evaluation_id}),
                    status="pending",
                )
                session.add_all((evaluation, outbox))
            return EvaluationReceipt(
                evaluation_id=evaluation_id,
                status=EvaluationStatus.QUEUED,
                replayed=False,
            )
        except IntegrityError:
            with self._sessions() as session:
                winner = session.scalar(
                    select(AgentEvaluation).where(AgentEvaluation.request_id == request_id)
                )
                if winner is None:
                    raise
                return self._replay_or_conflict(winner, payload_hash)

    def inspect(self, query: AgentControlQuery) -> AgentControlResult:
        with self._sessions() as session:
            if isinstance(query, ListEvaluations):
                statement = select(AgentEvaluation).order_by(
                    AgentEvaluation.created_at.desc(), AgentEvaluation.id.desc()
                )
                if query.status is not None:
                    statement = statement.where(AgentEvaluation.status == query.status.value)
                rows = session.scalars(statement.limit(max(1, min(query.limit, 100)))).all()
                return EvaluationCatalog(items=tuple(self._summary(item) for item in rows))
            if isinstance(query, GetEvaluation):
                return self._detail(self._evaluation(session, query.evaluation_id))
            if isinstance(query, CompareEvaluations):
                if query.left_id == query.right_id:
                    raise ServiceError(
                        code="EVALUATION_COMPARISON_REQUIRES_TWO_SNAPSHOTS",
                        message="Choose two different evaluation snapshots.",
                        status_code=422,
                    )
                left = self._detail(self._evaluation(session, query.left_id))
                right = self._detail(self._evaluation(session, query.right_id))
                return compare_evaluations(left, right)
            if isinstance(query, GetRunTrace):
                return self._trace(session, query.run_id)
        raise TypeError(f"Unsupported AgentControl query: {type(query).__name__}")

    def execute(self, command: ExecuteEvaluation, executor: EvaluationExecutor) -> EvaluationDetail:
        if not command.worker_id.strip():
            raise ValueError("worker_id cannot be empty")
        if not self._claim(command):
            return self.inspect(GetEvaluation(command.evaluation_id))  # type: ignore[return-value]
        try:
            policy_snapshot = self._evaluation_policy_snapshot(command.evaluation_id)
            report = validate_evaluation_report(
                executor.run(command.evaluation_id, policy_snapshot)
                if policy_snapshot is not None
                else executor.run(command.evaluation_id)
            )
            if (
                policy_snapshot is not None
                and report.policy_fingerprint != policy_snapshot.config_sha256
            ):
                raise EvaluationExecutionError(
                    "EVALUATION_POLICY_MISMATCH",
                    "The fixed evaluator report does not match the requested policy fingerprint.",
                )
        except EvaluationReportError as exc:
            self._fail_running(command, code=exc.code, message=str(exc))
        except EvaluationExecutionError as exc:
            self._fail_running(command, code=exc.code, message=str(exc))
        except Exception as exc:  # noqa: BLE001 - convert unknown executor faults into bounded state.
            self._fail_running(command, code="EVALUATION_EXECUTOR_FAILED", message=type(exc).__name__)
        else:
            self._complete(command, report)
        return self.inspect(GetEvaluation(command.evaluation_id))  # type: ignore[return-value]

    def recover(self, command: RecoverEvaluations) -> int:
        with self._sessions() as session, session.begin():
            result = session.execute(
                update(AgentEvaluation)
                .where(
                    AgentEvaluation.status == EvaluationStatus.RUNNING.value,
                    AgentEvaluation.lease_expires_at.is_not(None),
                    AgentEvaluation.lease_expires_at <= command.now,
                )
                .values(
                    status=EvaluationStatus.FAILED.value,
                    error_code="EVALUATION_WORKER_INTERRUPTED",
                    error_message="Evaluation worker lease expired before completion.",
                    lease_owner=None,
                    lease_expires_at=None,
                    finished_at=command.now,
                )
                .execution_options(synchronize_session=False)
            )
            return int(result.rowcount or 0)

    def _claim(self, command: ExecuteEvaluation) -> bool:
        now = self._clock()
        with self._sessions() as session, session.begin():
            if session.get(AgentEvaluation, command.evaluation_id) is None:
                raise ServiceError(code="EVALUATION_NOT_FOUND", message="Evaluation not found.", status_code=404)
            result = session.execute(
                update(AgentEvaluation)
                .where(
                    AgentEvaluation.id == command.evaluation_id,
                    AgentEvaluation.status == EvaluationStatus.QUEUED.value,
                )
                .values(
                    status=EvaluationStatus.RUNNING.value,
                    attempt=AgentEvaluation.attempt + 1,
                    lease_owner=command.worker_id,
                    lease_expires_at=now + timedelta(seconds=self._lease_seconds),
                    started_at=now,
                    error_code=None,
                    error_message=None,
                )
                .execution_options(synchronize_session=False)
            )
            return result.rowcount == 1

    def _complete(self, command: ExecuteEvaluation, report: ValidatedEvaluationReport) -> bool:
        status = EvaluationStatus.PASSED.value if report.status == "passed" else EvaluationStatus.FAILED.value
        with self._sessions() as session, session.begin():
            result = session.execute(
                update(AgentEvaluation)
                .where(
                    AgentEvaluation.id == command.evaluation_id,
                    AgentEvaluation.status == EvaluationStatus.RUNNING.value,
                    AgentEvaluation.lease_owner == command.worker_id,
                )
                .values(
                    status=status,
                    schema_version=report.schema_version,
                    dataset_name=report.dataset_name,
                    dataset_path=report.dataset_path,
                    dataset_sha256=report.dataset_sha256,
                    evaluator_sha256=report.evaluator_sha256,
                    report_sha256=report.report_sha256,
                    case_count=report.case_count,
                    case_pass_rate_millis=round(float(report.metrics["case_pass_rate"]) * 1_000),
                    external_provider_calls=report.external_provider_calls,
                    failure_case_count=len(report.failure_case_ids),
                    category_counts_json=_canonical_json(report.category_counts),
                    metrics_json=_canonical_json(report.metrics),
                    hard_gates_json=_canonical_json(report.hard_gates),
                    failure_case_ids_json=_canonical_json(report.failure_case_ids),
                    report_json=report.canonical_json,
                    provider_boundary=report.provider_boundary,
                    error_code=None if status == EvaluationStatus.PASSED.value else "EVALUATION_GATE_FAILED",
                    error_message=None if status == EvaluationStatus.PASSED.value else "One or more fixed quality gates failed.",
                    lease_owner=None,
                    lease_expires_at=None,
                    finished_at=self._clock(),
                )
                .execution_options(synchronize_session=False)
            )
            return result.rowcount == 1

    def _fail_running(self, command: ExecuteEvaluation, *, code: str, message: str) -> bool:
        with self._sessions() as session, session.begin():
            result = session.execute(
                update(AgentEvaluation)
                .where(
                    AgentEvaluation.id == command.evaluation_id,
                    AgentEvaluation.status == EvaluationStatus.RUNNING.value,
                    AgentEvaluation.lease_owner == command.worker_id,
                )
                .values(
                    status=EvaluationStatus.FAILED.value,
                    error_code=sanitize_fact(code, maximum_length=80),
                    error_message=sanitize_fact(message, maximum_length=500),
                    lease_owner=None,
                    lease_expires_at=None,
                    finished_at=self._clock(),
                )
                .execution_options(synchronize_session=False)
            )
            return result.rowcount == 1

    @staticmethod
    def _replay_or_conflict(evaluation: AgentEvaluation, payload_hash: str) -> EvaluationReceipt:
        if evaluation.request_payload_hash != payload_hash:
            raise ServiceError(
                code="EVALUATION_IDEMPOTENCY_CONFLICT",
                message="Evaluation request id was already used with a different payload.",
                status_code=409,
            )
        return EvaluationReceipt(
            evaluation_id=evaluation.id,
            status=EvaluationStatus(evaluation.status),
            replayed=True,
        )

    @staticmethod
    def _evaluation(session: Session, evaluation_id: str) -> AgentEvaluation:
        evaluation = session.get(AgentEvaluation, evaluation_id)
        if evaluation is None:
            raise ServiceError(code="EVALUATION_NOT_FOUND", message="Evaluation not found.", status_code=404)
        return evaluation

    @staticmethod
    def _summary(row: AgentEvaluation) -> EvaluationSummary:
        return EvaluationSummary(
            id=row.id,
            label=row.label,
            status=EvaluationStatus(row.status),
            mode=row.mode,
            policy_fingerprint=row.policy_fingerprint,
            dataset_sha256=row.dataset_sha256,
            case_count=row.case_count,
            case_pass_rate=(row.case_pass_rate_millis / 1_000 if row.case_pass_rate_millis is not None else None),
            external_provider_calls=row.external_provider_calls,
            failure_case_count=row.failure_case_count,
            created_at=_aware(row.created_at),
            started_at=_aware(row.started_at) if row.started_at else None,
            finished_at=_aware(row.finished_at) if row.finished_at else None,
            policy_version_id=row.policy_version_id,
        )

    def _resolve_policy(self, policy_id: str | None) -> PolicyDetail | None:
        if self._policy_resolver is None:
            if policy_id is not None:
                raise ServiceError(
                    code="POLICY_CONTROL_UNAVAILABLE",
                    message="Candidate policy evaluation is unavailable.",
                    status_code=503,
                )
            return None
        policy = self._policy_resolver(policy_id)
        if not isinstance(policy, PolicyDetail):
            raise ServiceError(
                code="POLICY_STATE_INVALID",
                message="The selected Agent policy is invalid.",
                status_code=500,
            )
        return policy

    def _evaluation_policy_snapshot(self, evaluation_id: str) -> EvaluationPolicySnapshot | None:
        with self._sessions() as session:
            evaluation = self._evaluation(session, evaluation_id)
            values = (
                evaluation.policy_version_id,
                evaluation.policy_snapshot_json,
            )
            if all(value is None for value in values):
                return None
            if any(value is None for value in values):
                raise EvaluationExecutionError(
                    "EVALUATION_POLICY_SNAPSHOT_INVALID",
                    "The persisted evaluation policy snapshot is incomplete.",
                )
            policy = session.get(AgentPolicyVersion, evaluation.policy_version_id)
            if (
                policy is None
                or policy.config_json != evaluation.policy_snapshot_json
                or policy.config_sha256 != evaluation.policy_fingerprint
            ):
                raise EvaluationExecutionError(
                    "EVALUATION_POLICY_SNAPSHOT_INVALID",
                    "The persisted evaluation policy snapshot is inconsistent.",
                )
            try:
                policy_config_from_snapshot(policy.config_json, policy.config_sha256)
            except ValueError as exc:
                raise EvaluationExecutionError(
                    "EVALUATION_POLICY_SNAPSHOT_INVALID",
                    "The persisted evaluation policy snapshot is invalid.",
                ) from exc
            return EvaluationPolicySnapshot(
                policy_id=policy.id,
                policy_version=policy.version,
                config_sha256=policy.config_sha256,
                config_json=policy.config_json,
            )

    def _detail(self, row: AgentEvaluation) -> EvaluationDetail:
        summary = self._summary(row)
        validated: ValidatedEvaluationReport | None = None
        parse_error: EvaluationReportError | None = None
        if row.report_json:
            try:
                raw = json.loads(row.report_json)
                if not isinstance(raw, Mapping):
                    raise EvaluationReportError("EVALUATION_REPORT_INVALID", "Stored report must be an object.")
                validated = validate_evaluation_report(raw)
            except (json.JSONDecodeError, EvaluationReportError) as exc:
                parse_error = (
                    exc
                    if isinstance(exc, EvaluationReportError)
                    else EvaluationReportError("EVALUATION_REPORT_INVALID", "Stored report is invalid JSON.")
                )
        error_code = parse_error.code if parse_error else row.error_code
        hard_gates = validated.hard_gates if validated else _bool_mapping(row.hard_gates_json)
        return EvaluationDetail(
            summary=summary,
            schema_version=validated.schema_version if validated else row.schema_version,
            evaluator_sha256=validated.evaluator_sha256 if validated else row.evaluator_sha256,
            dataset_name=validated.dataset_name if validated else row.dataset_name,
            category_counts=validated.category_counts if validated else _int_mapping(row.category_counts_json),
            metrics=validated.metrics if validated else _number_mapping(row.metrics_json),
            hard_gates=hard_gates,
            cases=validated.cases if validated else (),
            failure_case_ids=validated.failure_case_ids if validated else _string_tuple(row.failure_case_ids_json),
            provider_boundary=sanitize_fact(row.provider_boundary, maximum_length=500),
            triage=triage_evaluation_failure(
                status=row.status,
                error_code=error_code,
                hard_gate_failed=bool(hard_gates) and not all(hard_gates.values()),
            ),
            error_code=error_code,
            error_message=(
                sanitize_fact(str(parse_error), maximum_length=500)
                if parse_error
                else sanitize_fact(row.error_message, maximum_length=500)
                if row.error_message
                else None
            ),
        )

    @staticmethod
    def _trace(session: Session, run_id: str):
        run = session.get(AgentRun, run_id)
        if run is None:
            raise ServiceError(code="RUN_NOT_FOUND", message="Agent run not found.", status_code=404)
        events = tuple(
            TraceEventInput(
                sequence=item.run_sequence,
                run_version=item.run_version,
                event_type=item.event_type,
                visibility=item.visibility,
                payload=_json_mapping(item.payload_json),
                trace_id=item.trace_id,
                created_at=item.created_at,
                step_id=item.step_id,
                tool_call_id=item.tool_call_id,
            )
            for item in session.scalars(
                select(AgentEvent).where(AgentEvent.run_id == run_id).order_by(AgentEvent.run_sequence.asc())
            ).all()
        )
        tools = tuple(
            TraceToolCallInput(
                id=item.id,
                tool_name=item.tool_name,
                tool_version=item.tool_version,
                effect=item.effect,
                status=item.status,
                arguments_digest=item.arguments_digest,
                error_code=item.error_code,
                started_at=item.started_at,
                finished_at=item.finished_at,
            )
            for item in session.scalars(
                select(AgentToolCall).where(AgentToolCall.run_id == run_id).order_by(AgentToolCall.created_at.asc())
            ).all()
        )
        models = tuple(
            TraceModelCallInput(
                id=item.id,
                operation=item.operation,
                provider=item.provider,
                model=item.model,
                status=item.status,
                input_tokens=item.input_tokens,
                output_tokens=item.output_tokens,
                cost_micros=item.cost_micros,
                latency_ms=item.latency_ms,
                retries=item.retries,
                usage_estimated=bool(item.usage_estimated),
                error_code=item.error_code,
            )
            for item in session.scalars(
                select(AgentModelCall).where(AgentModelCall.run_id == run_id).order_by(AgentModelCall.created_at.asc())
            ).all()
        )
        checkpoints = tuple(
            TraceCheckpointInput(checksum=item.checksum, run_version=item.run_version)
            for item in session.scalars(
                select(AgentCheckpoint).where(AgentCheckpoint.run_id == run_id).order_by(AgentCheckpoint.run_version.asc())
            ).all()
        )
        dead_letter = session.scalar(
            select(OutboxMessage.id).where(
                OutboxMessage.aggregate_id == run_id,
                OutboxMessage.topic == "agent.advance",
                OutboxMessage.status == "dead_letter",
            )
        ) is not None
        return project_run_trace(
            TraceRunInput(
                id=run.id,
                trace_id=run.trace_id,
                goal=run.goal,
                requested_mode=run.requested_mode,
                effective_mode=run.effective_mode,
                status=run.status,
                phase=run.phase,
                provider_mode=run.provider_mode,
                created_at=run.created_at,
                started_at=run.started_at,
                finished_at=run.finished_at,
                active_elapsed_ms=run.active_elapsed_ms,
                budget_limits=_int_mapping(run.budget_limits_json),
                budget_usage=_int_mapping(run.budget_usage_json),
                decision_policy_id=run.decision_policy_id,
                decision_policy_version=run.decision_policy_version,
                decision_policy_fingerprint=run.decision_policy_fingerprint,
                termination_reason=run.termination_reason,
                dispatch_dead_letter=dead_letter,
            ),
            events=events,
            tool_calls=tools,
            model_calls=models,
            checkpoints=checkpoints,
        )


def _json_mapping(value: str) -> Mapping[str, object]:
    try:
        parsed = json.loads(value or "{}")
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, Mapping) else {}


def _int_mapping(value: str) -> dict[str, int]:
    return {key: int(item) for key, item in _json_mapping(value).items() if isinstance(item, int) and not isinstance(item, bool)}


def _number_mapping(value: str) -> dict[str, int | float]:
    return {
        key: item
        for key, item in _json_mapping(value).items()
        if isinstance(item, (int, float)) and not isinstance(item, bool)
    }


def _bool_mapping(value: str) -> dict[str, bool]:
    return {key: item for key, item in _json_mapping(value).items() if isinstance(item, bool)}


def _string_tuple(value: str) -> tuple[str, ...]:
    try:
        parsed = json.loads(value or "[]")
    except json.JSONDecodeError:
        return ()
    return tuple(map(str, parsed)) if isinstance(parsed, list) else ()


def _digest(value: object) -> str:
    return sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
