"""Add owner-scoped service conditions; no changes to bills or balances."""
from alembic import op
import sqlalchemy as sa

revision = 'eab672514c90'
down_revision = 'c84ab091fa22'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('service_agreements',
        sa.Column('id',sa.String(64),primary_key=True),
        sa.Column('user_id',sa.String(64),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('service_id',sa.String(64),nullable=False),
        sa.Column('reference',sa.String(64),nullable=False),
        sa.Column('provider_id',sa.String(64),nullable=False),
        sa.Column('plan_id',sa.String(64),nullable=False),
        sa.Column('plan_name',sa.String(100),nullable=False),
        sa.Column('version',sa.Integer(),nullable=False),
        sa.Column('valid_from',sa.Date(),nullable=False),
        sa.Column('valid_until',sa.Date(),nullable=False),
        sa.Column('monthly_minor',sa.Integer(),nullable=False),
        sa.Column('currency',sa.String(3),nullable=False),
        sa.Column('taxes_included',sa.Boolean(),nullable=False),
        sa.Column('extras_require_approval',sa.Boolean(),nullable=False),
        sa.Column('source',sa.String(32),nullable=False),
        sa.UniqueConstraint('user_id','service_id','reference','version'),
        sa.CheckConstraint('monthly_minor > 0'),sa.CheckConstraint('version > 0'),
        sa.CheckConstraint('valid_until >= valid_from'))
    op.create_index('ix_service_agreements_user_id','service_agreements',['user_id'])


def downgrade():
    op.drop_table('service_agreements')
