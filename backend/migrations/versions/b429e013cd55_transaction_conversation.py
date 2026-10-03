"""Persist owner-scoped transaction context and its audit reference."""
from alembic import op
import sqlalchemy as sa

revision = "b429e013cd55"
down_revision = "a318d902bc44"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("conversations") as batch:
        batch.add_column(sa.Column("transaction_id", sa.String(64), nullable=True))
        batch.create_foreign_key("fk_conversation_transaction_owner", "transactions", ["transaction_id", "user_id"], ["id", "user_id"])
    with op.batch_alter_table("audit_events") as batch:
        batch.add_column(sa.Column("transaction_id", sa.String(64), nullable=True))
        batch.create_foreign_key("fk_audit_transaction_owner", "transactions", ["transaction_id", "user_id"], ["id", "user_id"])
        batch.create_index("ix_audit_events_transaction_id", ["transaction_id"])


def downgrade():
    raise RuntimeError("Restore a verified backup to preserve transaction conversation references.")
