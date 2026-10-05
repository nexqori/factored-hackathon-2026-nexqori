"""Track claim acceptance and approval separately from the existing refund ledger."""
from alembic import op
import sqlalchemy as sa

revision = 'fa6107d935b2'
down_revision = 'eab672514c90'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('claim_reviews',
        sa.Column('request_id', sa.String(64), primary_key=True),
        sa.Column('user_id', sa.String(64), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('stage', sa.String(16), nullable=False),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('actor_id', sa.String(64), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['request_id','user_id'], ['requests.id','requests.user_id']),
        sa.CheckConstraint("stage IN ('delivered','in_review','approved')"),
        sa.CheckConstraint("stage <> 'approved' OR (note IS NOT NULL AND length(note) BETWEEN 10 AND 1000)"))
    op.create_index('ix_claim_reviews_user_id', 'claim_reviews', ['user_id'])


def downgrade():
    raise RuntimeError('Preserve claim decisions; restore a verified compatible backup instead.')
