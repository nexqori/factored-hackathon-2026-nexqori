"""Self-declared customer experience and a documented local test card."""
from alembic import op
import sqlalchemy as sa

revision = "e104b56a902c"
down_revision = "d92e6047f831"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("customer_profiles",
        sa.Column("user_id", sa.String(64), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("birth_date", sa.Date, nullable=False),
        sa.Column("banking_experience", sa.String(16), nullable=False),
        sa.Column("digital_experience", sa.String(16), nullable=False),
        sa.Column("assistance", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("banking_experience IN ('new','occasional','frequent')"),
        sa.CheckConstraint("digital_experience IN ('new','learning','confident')"),
        sa.CheckConstraint("assistance IN ('auto','guided','standard')"))
    # Only the known fixture card, never an imported or user-added product.
    op.execute(sa.text("UPDATE products SET last4='5556' WHERE id='card-01' AND user_id='andrea' AND type='card' AND last4='8942' AND EXISTS (SELECT 1 FROM card_profiles c WHERE c.product_id=products.id AND c.user_id=products.user_id AND c.provider_ref='local-card-01')"))

def downgrade():
    raise RuntimeError("Restore a verified backup to preserve customer preferences.")
