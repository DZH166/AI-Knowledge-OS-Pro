"""Persist source-pinned feedback, one terminal review and one reviewed sample.

Downgrade removes V5.8 feedback/sample data, not pre-existing research data.
Back up the database before a downgrade with real feedback.
"""
from alembic import op
import sqlalchemy as sa


revision = "0017_reviewed_feedback"
down_revision = "0016_optimizer_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "research_feedback",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("request_id", sa.String(80), nullable=False, unique=True),
        sa.Column("request_sha256", sa.String(64), nullable=False),
        sa.Column("artifact_id", sa.String(36), sa.ForeignKey("agent_artifacts.id"), nullable=False),
        sa.Column("claim_id", sa.String(36), sa.ForeignKey("agent_claims.id"), nullable=True),
        sa.Column("provider_mode", sa.String(30), nullable=False),
        sa.Column("issue", sa.String(40), nullable=False),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("snapshot_json", sa.Text(), nullable=False),
        sa.Column("snapshot_sha256", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("review_request_id", sa.String(80), nullable=True, unique=True),
        sa.Column("review_sha256", sa.String(64), nullable=True),
        sa.Column("review_json", sa.Text(), nullable=True),
        sa.CheckConstraint("status IN ('pending', 'accepted', 'rejected')", name="ck_feedback_status"),
        sa.CheckConstraint("version >= 1", name="ck_feedback_version"),
        sa.CheckConstraint("issue IN ('missing_evidence', 'incorrect_answer', 'unsupported_citation', 'incomplete_answer')",
                           name="ck_feedback_issue"),
    )
    for field in ("artifact_id", "provider_mode", "status"):
        op.create_index(f"ix_research_feedback_{field}", "research_feedback", [field])
    op.create_table(
        "feedback_samples",
        sa.Column("feedback_id", sa.Integer(), sa.ForeignKey("research_feedback.id"), primary_key=True),
        sa.Column("split", sa.String(20), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("payload_sha256", sa.String(64), nullable=False),
        sa.CheckConstraint("split IN ('tuning', 'holdout')", name="ck_feedback_sample_split"),
    )
    op.create_index("ix_feedback_samples_split", "feedback_samples", ["split"])


def downgrade() -> None:
    op.drop_table("feedback_samples")
    op.drop_table("research_feedback")
