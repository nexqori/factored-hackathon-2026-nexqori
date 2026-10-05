"""Persist a known card kind without guessing the kind of legacy cards."""
from alembic import op
import sqlalchemy as sa

revision = 'fb7218c04a63'
down_revision = 'fa6107d935b2'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('products', table_args=(
        sa.CheckConstraint("type IN ('account','savings','card')"),
        sa.CheckConstraint("currency = 'MXN'"),
    ) if op.get_bind().dialect.name == 'sqlite' else ()) as batch:
        batch.add_column(sa.Column('card_kind', sa.String(8), nullable=True))
        batch.create_check_constraint('ck_products_card_kind', "card_kind IS NULL OR (type = 'card' AND card_kind IN ('credit','debit'))")


def downgrade():
    with op.batch_alter_table('products', table_args=(
        sa.CheckConstraint("type IN ('account','savings','card')"),
        sa.CheckConstraint("currency = 'MXN'"),
    ) if op.get_bind().dialect.name == 'sqlite' else ()) as batch:
        batch.drop_constraint('ck_products_card_kind', type_='check')
        batch.drop_column('card_kind')
