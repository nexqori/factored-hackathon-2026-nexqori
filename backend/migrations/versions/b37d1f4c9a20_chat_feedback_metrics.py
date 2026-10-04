"""Persist chatbot satisfaction scores and response timings.

Revision ID: b37d1f4c9a20
Revises: a649a6f7e838
Create Date: 2026-10-03 07:16:14
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b37d1f4c9a20"
down_revision: Union[str, Sequence[str], None] = "a649a6f7e838"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "chat_feedback",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("submission_id", sa.String(length=36), nullable=False),
        sa.Column("metric", sa.String(length=8), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("locale", sa.String(length=2), nullable=False),
        sa.Column("form_duration_ms", sa.Integer(), nullable=False),
        sa.Column("conversation_duration_ms", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("metric IN ('nps','csat','ces')"),
        sa.CheckConstraint(
            "(metric = 'nps' AND score BETWEEN 0 AND 10) OR "
            "(metric = 'csat' AND score BETWEEN 1 AND 5) OR "
            "(metric = 'ces' AND score BETWEEN 1 AND 7)"
        ),
        sa.CheckConstraint("locale IN ('es','en','pt')"),
        sa.CheckConstraint("form_duration_ms BETWEEN 0 AND 86400000"),
        sa.CheckConstraint("conversation_duration_ms BETWEEN 0 AND 604800000"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "submission_id"),
    )
    op.create_index(op.f("ix_chat_feedback_user_id"), "chat_feedback", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_chat_feedback_user_id"), table_name="chat_feedback")
    op.drop_table("chat_feedback")
