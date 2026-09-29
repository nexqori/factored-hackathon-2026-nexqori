"""Persist service selection and owned source account, preserving existing cases."""
from alembic import op
import sqlalchemy as sa

revision = "c83d71a6e520"
down_revision = "b721c95d024a"
branch_labels = None
depends_on = None


def upgrade():
    constraints = []
    if op.get_bind().dialect.name == "sqlite":
        constraints = [sa.CheckConstraint("status IN ('received','in_review','handed_off')", name="ck_requests_status"),
                       sa.CheckConstraint("reason IN ('unknown','amount','payment','other')", name="ck_requests_reason"),
                       sa.CheckConstraint("length(details) BETWEEN 10 AND 1000", name="ck_requests_details")]
    with op.batch_alter_table("requests", table_args=tuple(constraints)) as batch:
        batch.add_column(sa.Column("catalog_service_id", sa.String(64), nullable=True))
        batch.add_column(sa.Column("source_product_id", sa.String(64), nullable=True))
        batch.add_column(sa.Column("service_data", sa.JSON(), nullable=True))
        batch.create_foreign_key("fk_requests_source_owner", "products", ["source_product_id", "user_id"], ["id", "user_id"])


def downgrade():
    raise RuntimeError("Restore a verified database backup to preserve service request details.")
