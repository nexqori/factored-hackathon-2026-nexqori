"""Verified notification email and single-use operation confirmation codes."""
from alembic import op
import sqlalchemy as sa

revision = 'f5a306c829d1'
down_revision = 'f492b731e845'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('notification_preferences',
        sa.Column('user_id', sa.String(64), sa.ForeignKey('users.id'), primary_key=True),
        sa.Column('email', sa.String(254), nullable=False),
        sa.Column('verified_at', sa.DateTime(timezone=True), nullable=False))
    op.create_table('email_challenges',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('user_id', sa.String(64), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('session_hash', sa.String(64), nullable=False),
        sa.Column('purpose', sa.String(32), nullable=False),
        sa.Column('product_id', sa.String(64), nullable=True),
        sa.Column('email', sa.String(254), nullable=False),
        sa.Column('code_hash', sa.Text, nullable=False),
        sa.Column('created_at', sa.BigInteger, nullable=False),
        sa.Column('expires_at', sa.BigInteger, nullable=False),
        sa.Column('attempts', sa.Integer, nullable=False),
        sa.Column('consumed', sa.Boolean, nullable=False),
        sa.ForeignKeyConstraint(['product_id', 'user_id'], ['products.id', 'products.user_id']),
        sa.CheckConstraint("purpose IN ('notification_email','card_block')"))
    op.create_index('ix_email_challenges_user_id', 'email_challenges', ['user_id'])


def downgrade():
    raise RuntimeError('Restore a verified backup to preserve confirmation history.')
