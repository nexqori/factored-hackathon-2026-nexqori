"""Keep owner-confirmed occasional purchases outside future spending baselines."""
from alembic import op
import sqlalchemy as sa

revision = 'fb7208ea46c3'
down_revision = 'fa6107d935b2'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('spending_exceptions',
        sa.Column('transaction_id', sa.String(64), primary_key=True),
        sa.Column('user_id', sa.String(64), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['transaction_id','user_id'], ['transactions.id','transactions.user_id']))
    op.create_index('ix_spending_exceptions_user_id', 'spending_exceptions', ['user_id'])


def downgrade():
    raise RuntimeError('Preserve confirmed exceptions; restore a verified compatible backup instead.')
