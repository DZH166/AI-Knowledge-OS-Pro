"""V5 durable agent runtime, event ledger, and evidence graph.

Revision ID: 0008_v5_agent_runtime
Revises: 0007_v5_evidence_index
Create Date: 2026-08-15
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from alembic import op
import sqlalchemy as sa


revision = "0008_v5_agent_runtime"
down_revision = "0007_v5_evidence_index"
branch_labels = None
depends_on = None


IndexDefinition = tuple[str, Sequence[str], bool]


def upgrade() -> None:
    _create_agent_runs()
    _create_run_children()
    _create_event_ledger()
    _create_evidence_graph()


def downgrade() -> None:
    # Reverse the foreign-key dependency graph.  Runtime data is intentionally
    # removed when downgrading because none of these tables exists before V5.
    for table_name in (
        "claim_evidence",
        "agent_claims",
        "agent_artifacts",
        "requirement_evidence",
        "agent_evidence",
        "agent_checkpoints",
        "agent_events",
        "agent_commands",
        "agent_model_calls",
        "agent_tool_calls",
        "agent_gates",
        "agent_requirements",
        "agent_plans",
        "agent_runs",
    ):
        op.drop_table(table_name)


def _created_at_column() -> sa.Column:
    return sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    )


def _updated_at_column() -> sa.Column:
    return sa.Column(
        "updated_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    )


def _create_indexes(table_name: str, definitions: Iterable[IndexDefinition]) -> None:
    for name, columns, unique in definitions:
        op.create_index(name, table_name, list(columns), unique=unique)


def _create_agent_runs() -> None:
    op.create_table(
        "agent_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column(
            "space_id",
            sa.Integer(),
            sa.ForeignKey("knowledge_spaces.id"),
            nullable=False,
        ),
        sa.Column("goal", sa.Text(), nullable=False),
        sa.Column("requested_mode", sa.String(length=30), nullable=False),
        sa.Column("effective_mode", sa.String(length=30), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("phase", sa.String(length=40), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("execution_epoch", sa.Integer(), nullable=False),
        sa.Column("scope_snapshot_json", sa.Text(), nullable=False),
        sa.Column("scope_digest", sa.String(length=64), nullable=False),
        sa.Column("deliverable_json", sa.Text(), nullable=False),
        sa.Column("policy_snapshot_json", sa.Text(), nullable=False),
        sa.Column("budget_limits_json", sa.Text(), nullable=False),
        sa.Column("budget_usage_json", sa.Text(), nullable=False),
        sa.Column("provider_mode", sa.String(length=30), nullable=False),
        sa.Column("current_plan_version", sa.Integer(), nullable=True),
        sa.Column("pending_gate_id", sa.String(length=36), nullable=True),
        sa.Column("final_artifact_id", sa.String(length=36), nullable=True),
        sa.Column("termination_reason", sa.String(length=120), nullable=True),
        sa.Column("lease_owner", sa.String(length=120), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trace_id", sa.String(length=64), nullable=False),
        sa.Column("active_elapsed_ms", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        _created_at_column(),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        _updated_at_column(),
        sa.CheckConstraint(
            "version >= 1",
            name="ck_agent_runs_version_positive",
        ),
        sa.CheckConstraint(
            "execution_epoch >= 0",
            name="ck_agent_runs_epoch_non_negative",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    _create_indexes(
        "agent_runs",
        (
            ("ix_agent_runs_space_id", ("space_id",), False),
            ("ix_agent_runs_requested_mode", ("requested_mode",), False),
            ("ix_agent_runs_effective_mode", ("effective_mode",), False),
            ("ix_agent_runs_status", ("status",), False),
            ("ix_agent_runs_phase", ("phase",), False),
            ("ix_agent_runs_scope_digest", ("scope_digest",), False),
            ("ix_agent_runs_provider_mode", ("provider_mode",), False),
            ("ix_agent_runs_pending_gate_id", ("pending_gate_id",), False),
            ("ix_agent_runs_final_artifact_id", ("final_artifact_id",), False),
            ("ix_agent_runs_lease_expires_at", ("lease_expires_at",), False),
            ("ix_agent_runs_retry_at", ("retry_at",), False),
            ("ix_agent_runs_trace_id", ("trace_id",), False),
            ("ix_agent_runs_expires_at", ("expires_at",), False),
            ("ix_agent_runs_created_at", ("created_at",), False),
        ),
    )


def _create_run_children() -> None:
    op.create_table(
        "agent_plans",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column(
            "run_id",
            sa.String(length=36),
            sa.ForeignKey("agent_runs.id"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("strategy", sa.String(length=80), nullable=False),
        sa.Column("created_by", sa.String(length=40), nullable=False),
        sa.Column("summary_json", sa.Text(), nullable=False),
        _created_at_column(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "run_id",
            "version",
            name="uq_agent_plan_run_version",
        ),
    )
    _create_indexes(
        "agent_plans",
        (("ix_agent_plans_run_id", ("run_id",), False),),
    )

    op.create_table(
        "agent_requirements",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column(
            "run_id",
            sa.String(length=36),
            sa.ForeignKey("agent_runs.id"),
            nullable=False,
        ),
        sa.Column("plan_version", sa.Integer(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("kind", sa.String(length=30), nullable=False),
        sa.Column("priority", sa.String(length=20), nullable=False),
        sa.Column("depends_on_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        _created_at_column(),
        _updated_at_column(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "run_id",
            "plan_version",
            "ordinal",
            name="uq_agent_requirement_position",
        ),
    )
    _create_indexes(
        "agent_requirements",
        (
            ("ix_agent_requirements_run_id", ("run_id",), False),
            ("ix_agent_requirements_status", ("status",), False),
        ),
    )

    op.create_table(
        "agent_gates",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column(
            "run_id",
            sa.String(length=36),
            sa.ForeignKey("agent_runs.id"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("response_schema_json", sa.Text(), nullable=False),
        sa.Column("proposed_tool_call_id", sa.String(length=36), nullable=True),
        sa.Column("arguments_digest", sa.String(length=64), nullable=True),
        sa.Column("policy_reason", sa.Text(), nullable=True),
        sa.Column(
            "opened_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", sa.String(length=120), nullable=True),
        sa.Column("response_json", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    _create_indexes(
        "agent_gates",
        (
            ("ix_agent_gates_run_id", ("run_id",), False),
            ("ix_agent_gates_kind", ("kind",), False),
            ("ix_agent_gates_status", ("status",), False),
            (
                "ix_agent_gates_proposed_tool_call_id",
                ("proposed_tool_call_id",),
                False,
            ),
        ),
    )

    op.create_table(
        "agent_tool_calls",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column(
            "run_id",
            sa.String(length=36),
            sa.ForeignKey("agent_runs.id"),
            nullable=False,
        ),
        sa.Column("invocation_key", sa.String(length=160), nullable=False),
        sa.Column("tool_name", sa.String(length=80), nullable=False),
        sa.Column("tool_version", sa.String(length=40), nullable=False),
        sa.Column("effect", sa.String(length=40), nullable=False),
        sa.Column("arguments_json", sa.Text(), nullable=False),
        sa.Column("arguments_digest", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("result_json", sa.Text(), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("execution_epoch", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        _created_at_column(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "run_id",
            "invocation_key",
            name="uq_agent_tool_invocation",
        ),
    )
    _create_indexes(
        "agent_tool_calls",
        (
            ("ix_agent_tool_calls_run_id", ("run_id",), False),
            ("ix_agent_tool_calls_tool_name", ("tool_name",), False),
            ("ix_agent_tool_calls_status", ("status",), False),
        ),
    )

    op.create_table(
        "agent_model_calls",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column(
            "run_id",
            sa.String(length=36),
            sa.ForeignKey("agent_runs.id"),
            nullable=False,
        ),
        sa.Column("invocation_key", sa.String(length=160), nullable=False),
        sa.Column("operation", sa.String(length=80), nullable=False),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("model", sa.String(length=160), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("cost_micros", sa.Integer(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("retries", sa.Integer(), nullable=False),
        sa.Column("usage_estimated", sa.Integer(), nullable=False),
        sa.Column("execution_epoch", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        _created_at_column(),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "run_id",
            "invocation_key",
            name="uq_agent_model_invocation",
        ),
    )
    _create_indexes(
        "agent_model_calls",
        (
            ("ix_agent_model_calls_run_id", ("run_id",), False),
            ("ix_agent_model_calls_operation", ("operation",), False),
            ("ix_agent_model_calls_status", ("status",), False),
        ),
    )


def _create_event_ledger() -> None:
    op.create_table(
        "agent_commands",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("request_id", sa.String(length=120), nullable=False),
        sa.Column(
            "run_id",
            sa.String(length=36),
            sa.ForeignKey("agent_runs.id"),
            nullable=False,
        ),
        sa.Column("command_type", sa.String(length=40), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("receipt_json", sa.Text(), nullable=False),
        _created_at_column(),
        sa.PrimaryKeyConstraint("id"),
    )
    _create_indexes(
        "agent_commands",
        (
            ("ix_agent_commands_request_id", ("request_id",), True),
            ("ix_agent_commands_run_id", ("run_id",), False),
            ("ix_agent_commands_command_type", ("command_type",), False),
        ),
    )

    op.create_table(
        "agent_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column(
            "run_id",
            sa.String(length=36),
            sa.ForeignKey("agent_runs.id"),
            nullable=False,
        ),
        sa.Column("run_sequence", sa.Integer(), nullable=False),
        sa.Column("run_version", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("visibility", sa.String(length=20), nullable=False),
        sa.Column("step_id", sa.String(length=36), nullable=True),
        sa.Column("tool_call_id", sa.String(length=36), nullable=True),
        sa.Column("checkpoint_id", sa.String(length=36), nullable=True),
        sa.Column("trace_id", sa.String(length=64), nullable=False),
        _created_at_column(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "run_id",
            "run_sequence",
            name="uq_agent_event_run_sequence",
        ),
    )
    _create_indexes(
        "agent_events",
        (
            ("ix_agent_events_event_id", ("event_id",), True),
            ("ix_agent_events_run_id", ("run_id",), False),
            ("ix_agent_events_event_type", ("event_type",), False),
            ("ix_agent_events_visibility", ("visibility",), False),
            ("ix_agent_events_step_id", ("step_id",), False),
            ("ix_agent_events_tool_call_id", ("tool_call_id",), False),
            ("ix_agent_events_checkpoint_id", ("checkpoint_id",), False),
            ("ix_agent_events_trace_id", ("trace_id",), False),
            ("ix_agent_events_created_at", ("created_at",), False),
        ),
    )

    op.create_table(
        "agent_checkpoints",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column(
            "run_id",
            sa.String(length=36),
            sa.ForeignKey("agent_runs.id"),
            nullable=False,
        ),
        sa.Column("run_version", sa.Integer(), nullable=False),
        sa.Column("last_event_cursor", sa.Integer(), nullable=False),
        sa.Column("state_schema_version", sa.Integer(), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("state_json", sa.Text(), nullable=False),
        sa.Column("execution_epoch", sa.Integer(), nullable=False),
        sa.Column("scope_digest", sa.String(length=64), nullable=False),
        _created_at_column(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "run_id",
            "run_version",
            name="uq_agent_checkpoint_run_version",
        ),
    )
    _create_indexes(
        "agent_checkpoints",
        (("ix_agent_checkpoints_run_id", ("run_id",), False),),
    )


def _create_evidence_graph() -> None:
    op.create_table(
        "agent_evidence",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column(
            "run_id",
            sa.String(length=36),
            sa.ForeignKey("agent_runs.id"),
            nullable=False,
        ),
        sa.Column(
            "source_id",
            sa.Integer(),
            sa.ForeignKey("sources.id"),
            nullable=False,
        ),
        sa.Column(
            "revision_id",
            sa.Integer(),
            sa.ForeignKey("source_revisions.id"),
            nullable=False,
        ),
        sa.Column(
            "index_revision_id",
            sa.Integer(),
            sa.ForeignKey("index_revisions.id"),
            nullable=False,
        ),
        sa.Column(
            "chunk_id",
            sa.Integer(),
            sa.ForeignKey("multimodal_chunks.id"),
            nullable=False,
        ),
        sa.Column("source_type", sa.String(length=40), nullable=False),
        sa.Column("locator_json", sa.Text(), nullable=False),
        sa.Column("locator_digest", sa.String(length=64), nullable=False),
        sa.Column("revision_content_hash", sa.String(length=64), nullable=False),
        sa.Column("evidence_content_hash", sa.String(length=64), nullable=False),
        sa.Column("excerpt_preview", sa.Text(), nullable=False),
        sa.Column(
            "retrieved_by_tool_call_id",
            sa.String(length=36),
            sa.ForeignKey("agent_tool_calls.id"),
            nullable=True,
        ),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("retrieval_scores_json", sa.Text(), nullable=False),
        sa.Column("trust_level", sa.String(length=30), nullable=False),
        sa.Column("active_at_snapshot", sa.Integer(), nullable=False),
        _created_at_column(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "run_id",
            "revision_id",
            "chunk_id",
            "locator_digest",
            name="uq_agent_evidence_identity",
        ),
    )
    _create_indexes(
        "agent_evidence",
        (
            ("ix_agent_evidence_run_id", ("run_id",), False),
            ("ix_agent_evidence_source_id", ("source_id",), False),
            ("ix_agent_evidence_revision_id", ("revision_id",), False),
            (
                "ix_agent_evidence_index_revision_id",
                ("index_revision_id",),
                False,
            ),
            ("ix_agent_evidence_chunk_id", ("chunk_id",), False),
            ("ix_agent_evidence_source_type", ("source_type",), False),
            (
                "ix_agent_evidence_retrieved_by_tool_call_id",
                ("retrieved_by_tool_call_id",),
                False,
            ),
        ),
    )

    op.create_table(
        "requirement_evidence",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "requirement_id",
            sa.String(length=36),
            sa.ForeignKey("agent_requirements.id"),
            nullable=False,
        ),
        sa.Column(
            "evidence_id",
            sa.String(length=36),
            sa.ForeignKey("agent_evidence.id"),
            nullable=False,
        ),
        sa.Column("relation", sa.String(length=30), nullable=False),
        sa.Column("method", sa.String(length=30), nullable=False),
        sa.Column("confidence_millis", sa.Integer(), nullable=True),
        sa.Column("reason_code", sa.String(length=80), nullable=False),
        _created_at_column(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "requirement_id",
            "evidence_id",
            "relation",
            name="uq_requirement_evidence_relation",
        ),
    )
    _create_indexes(
        "requirement_evidence",
        (
            (
                "ix_requirement_evidence_requirement_id",
                ("requirement_id",),
                False,
            ),
            ("ix_requirement_evidence_evidence_id", ("evidence_id",), False),
            ("ix_requirement_evidence_relation", ("relation",), False),
        ),
    )

    op.create_table(
        "agent_artifacts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column(
            "producing_run_id",
            sa.String(length=36),
            sa.ForeignKey("agent_runs.id"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("body_markdown", sa.Text(), nullable=False),
        sa.Column("structured_payload_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        _created_at_column(),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    _create_indexes(
        "agent_artifacts",
        (
            (
                "ix_agent_artifacts_producing_run_id",
                ("producing_run_id",),
                True,
            ),
            ("ix_agent_artifacts_kind", ("kind",), False),
            ("ix_agent_artifacts_status", ("status",), False),
        ),
    )

    op.create_table(
        "agent_claims",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column(
            "artifact_id",
            sa.String(length=36),
            sa.ForeignKey("agent_artifacts.id"),
            nullable=False,
        ),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("kind", sa.String(length=30), nullable=False),
        sa.Column("verification_status", sa.String(length=30), nullable=False),
        _created_at_column(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "artifact_id",
            "ordinal",
            name="uq_agent_claim_position",
        ),
    )
    _create_indexes(
        "agent_claims",
        (
            ("ix_agent_claims_artifact_id", ("artifact_id",), False),
            (
                "ix_agent_claims_verification_status",
                ("verification_status",),
                False,
            ),
        ),
    )

    op.create_table(
        "claim_evidence",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "claim_id",
            sa.String(length=36),
            sa.ForeignKey("agent_claims.id"),
            nullable=False,
        ),
        sa.Column(
            "evidence_id",
            sa.String(length=36),
            sa.ForeignKey("agent_evidence.id"),
            nullable=False,
        ),
        sa.Column("relation", sa.String(length=30), nullable=False),
        sa.Column("verifier_method", sa.String(length=40), nullable=False),
        sa.Column("confidence_millis", sa.Integer(), nullable=True),
        sa.Column("reason_code", sa.String(length=80), nullable=False),
        _created_at_column(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "claim_id",
            "evidence_id",
            "relation",
            name="uq_claim_evidence_relation",
        ),
    )
    _create_indexes(
        "claim_evidence",
        (
            ("ix_claim_evidence_claim_id", ("claim_id",), False),
            ("ix_claim_evidence_evidence_id", ("evidence_id",), False),
            ("ix_claim_evidence_relation", ("relation",), False),
        ),
    )
