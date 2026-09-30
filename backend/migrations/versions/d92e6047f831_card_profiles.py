"""Card metadata; no PAN or CVV storage. Preserve all existing records."""
from alembic import op
import sqlalchemy as sa

revision = "d92e6047f831"
down_revision = "c83d71a6e520"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("card_profiles",
        sa.Column("product_id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("provider_ref", sa.String(64), unique=True, nullable=False),
        sa.Column("expiry_month", sa.Integer, nullable=False),
        sa.Column("expiry_year", sa.Integer, nullable=False),
        sa.ForeignKeyConstraint(["product_id", "user_id"], ["products.id", "products.user_id"]),
        sa.CheckConstraint("expiry_month BETWEEN 1 AND 12"),
        sa.CheckConstraint("expiry_year BETWEEN 2000 AND 2200"))
    op.create_index("ix_card_profiles_user_id", "card_profiles", ["user_id"])
    # Only the known local fixture. Never infer issuer credentials for other cards.
    op.execute(sa.text("INSERT INTO card_profiles(product_id,user_id,provider_ref,expiry_month,expiry_year) SELECT id,user_id,'local-card-01',12,2029 FROM products WHERE id='card-01' AND user_id='andrea' AND type='card' AND last4='8942'"))

def downgrade():
    raise RuntimeError("Restore a verified backup to preserve card metadata.")
