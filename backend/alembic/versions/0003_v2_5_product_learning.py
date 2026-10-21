"""V2.5 product learning workflow extensions.

Revision ID: 0003_v2_5_product_learning
Revises: 0002_v2_schema
Create Date: 2026-06-11
"""

from alembic import op
import sqlalchemy as sa

revision = "0003_v2_5_product_learning"
down_revision = "0002_v2_schema"
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _columns(table_name: str) -> set[str]:
    if table_name not in _tables():
        return set()
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def _add_column(table_name: str, column: sa.Column) -> None:
    if table_name in _tables() and column.name not in _columns(table_name):
        op.add_column(table_name, column)


def _drop_column(table_name: str, column_name: str) -> None:
    if table_name in _tables() and column_name in _columns(table_name):
        op.drop_column(table_name, column_name)


def upgrade() -> None:
    tables = _tables()
    if "onboarding_states" not in tables:
        op.create_table(
            "onboarding_states",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_key", sa.String(length=80), nullable=False, server_default="local"),
            sa.Column("steps_json", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("dismissed", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_index("ix_onboarding_states_user_key", "onboarding_states", ["user_key"], unique=True)

    if "chat_sessions" not in tables:
        op.create_table(
            "chat_sessions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("space_id", sa.Integer(), sa.ForeignKey("knowledge_spaces.id"), nullable=False),
            sa.Column("title", sa.String(length=160), nullable=False, server_default="新的知识问答"),
            sa.Column("answer_mode", sa.String(length=30), nullable=False, server_default="normal"),
            sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_index("ix_chat_sessions_space_id", "chat_sessions", ["space_id"])

    if "chat_messages" not in tables:
        op.create_table(
            "chat_messages",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("session_id", sa.Integer(), sa.ForeignKey("chat_sessions.id"), nullable=False),
            sa.Column("qa_log_id", sa.Integer(), sa.ForeignKey("qa_logs.id"), nullable=True),
            sa.Column("role", sa.String(length=20), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("answer_mode", sa.String(length=30), nullable=True),
            sa.Column("citations_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("used_citation_ids_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("related_chunks_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("retrieval_status", sa.String(length=40), nullable=True),
            sa.Column("answer_confidence", sa.String(length=30), nullable=True),
            sa.Column("is_favorite", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_index("ix_chat_messages_session_id", "chat_messages", ["session_id"])
        op.create_index("ix_chat_messages_qa_log_id", "chat_messages", ["qa_log_id"])

    if "learning_notes" not in tables:
        op.create_table(
            "learning_notes",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("title", sa.String(length=180), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("tags_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("knowledge_point_id", sa.Integer(), sa.ForeignKey("knowledge_points.id"), nullable=True),
            sa.Column("document_id", sa.Integer(), sa.ForeignKey("documents.id"), nullable=True),
            sa.Column("qa_log_id", sa.Integer(), sa.ForeignKey("qa_logs.id"), nullable=True),
            sa.Column("version_slug", sa.String(length=80), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_index("ix_learning_notes_knowledge_point_id", "learning_notes", ["knowledge_point_id"])
        op.create_index("ix_learning_notes_document_id", "learning_notes", ["document_id"])
        op.create_index("ix_learning_notes_qa_log_id", "learning_notes", ["qa_log_id"])
        op.create_index("ix_learning_notes_version_slug", "learning_notes", ["version_slug"])

    for column in [
        sa.Column("last_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_review_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("difficulty", sa.String(length=30), nullable=False, server_default="normal"),
    ]:
        _add_column("learning_cards", column)


def downgrade() -> None:
    _drop_column("learning_cards", "difficulty")
    _drop_column("learning_cards", "review_count")
    _drop_column("learning_cards", "next_review_at")
    _drop_column("learning_cards", "last_reviewed_at")

    for table_name in ["learning_notes", "chat_messages", "chat_sessions", "onboarding_states"]:
        if table_name in _tables():
            op.drop_table(table_name)
