"""Local card blocks and reviewed refunds, preserving existing banking rows."""
from alembic import op
import sqlalchemy as sa

revision = "a318d902bc44"
down_revision = "f217a8e309bc"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("card_profiles", table_args=(sa.CheckConstraint("expiry_month BETWEEN 1 AND 12"), sa.CheckConstraint("expiry_year BETWEEN 2000 AND 2200"))) as batch:
        batch.add_column(sa.Column("status", sa.String(16), nullable=False, server_default="active"))
        batch.add_column(sa.Column("blocked_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("block_request_key", sa.String(64), nullable=True))
        batch.add_column(sa.Column("settlement_product_id", sa.String(64), nullable=True))
        batch.create_check_constraint("ck_card_status", "status IN ('active','blocked')")
        batch.create_unique_constraint("uq_card_block_key", ["user_id", "block_request_key"])
        batch.create_foreign_key("fk_card_settlement_owner", "products", ["settlement_product_id", "user_id"], ["id", "user_id"])
    # Only this known fixture has an established settlement account. Do not infer other mappings.
    op.execute(sa.text("UPDATE card_profiles SET settlement_product_id='account-01' WHERE product_id='card-01' AND user_id='andrea' AND provider_ref='local-card-01' AND EXISTS (SELECT 1 FROM products WHERE id='account-01' AND user_id='andrea' AND type='account')"))
    with op.batch_alter_table("requests") as batch:
        batch.create_unique_constraint("uq_request_owner", ["id", "user_id"])
    with op.batch_alter_table("audit_events") as batch:
        batch.add_column(sa.Column("product_id", sa.String(64), nullable=True))
        batch.create_foreign_key("fk_audit_product", "products", ["product_id"], ["id"])
    op.create_table("refunds",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("request_id", sa.String(64), nullable=False, unique=True),
        sa.Column("transaction_id", sa.String(64), nullable=False, unique=True),
        sa.Column("destination_product_id", sa.String(64), nullable=False),
        sa.Column("amount_minor", sa.BigInteger, nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("request_key", sa.String(64), nullable=False),
        sa.Column("decision_key", sa.String(64), nullable=True),
        sa.Column("decision_note", sa.Text, nullable=True),
        sa.Column("decided_by", sa.String(64), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("credit_transaction_id", sa.String(64), nullable=True, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["request_id", "user_id"], ["requests.id", "requests.user_id"]),
        sa.ForeignKeyConstraint(["transaction_id", "user_id"], ["transactions.id", "transactions.user_id"]),
        sa.ForeignKeyConstraint(["credit_transaction_id", "user_id"], ["transactions.id", "transactions.user_id"]),
        sa.ForeignKeyConstraint(["destination_product_id", "user_id"], ["products.id", "products.user_id"]),
        sa.UniqueConstraint("user_id", "request_key"),
        sa.UniqueConstraint("decided_by", "decision_key"),
        sa.CheckConstraint("amount_minor > 0 AND currency = 'MXN'"),
        sa.CheckConstraint("status IN ('pending','approved','rejected')"),
        sa.CheckConstraint("(status = 'pending' AND decided_by IS NULL AND decided_at IS NULL AND decision_key IS NULL AND decision_note IS NULL AND credit_transaction_id IS NULL) OR (status IN ('approved','rejected') AND decided_by IS NOT NULL AND decided_at IS NOT NULL AND decision_key IS NOT NULL AND decision_note IS NOT NULL)"),
        sa.CheckConstraint("(status = 'approved' AND credit_transaction_id IS NOT NULL) OR (status <> 'approved' AND credit_transaction_id IS NULL)"))
    op.create_index("ix_refunds_user_id", "refunds", ["user_id"])


def downgrade():
    raise RuntimeError("Restore a verified backup; never discard operation history.")
