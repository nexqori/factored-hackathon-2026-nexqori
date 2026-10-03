"""Owner-scoped phone receipts and persistent bank conversation workflows."""
from alembic import op
import sqlalchemy as sa

revision = "e2715ba946c0"
down_revision = "b429e013cd55"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('phone_bills',
        sa.Column('id',sa.String(64),primary_key=True),sa.Column('user_id',sa.String(64),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('reference',sa.String(24),nullable=False),sa.Column('period',sa.String(7),nullable=False),sa.Column('due_date',sa.String(10),nullable=False),
        sa.Column('amount_minor',sa.BigInteger,nullable=False),sa.Column('currency',sa.String(3),nullable=False),
        sa.UniqueConstraint('id','user_id'),sa.UniqueConstraint('user_id','reference','period'),sa.CheckConstraint("amount_minor > 0 AND currency = 'MXN'"))
    op.create_index('ix_phone_bills_user_id','phone_bills',['user_id'])
    op.create_table('bill_payments',
        sa.Column('id',sa.String(64),primary_key=True),sa.Column('user_id',sa.String(64),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('bill_id',sa.String(64),nullable=False,unique=True),sa.Column('account_id',sa.String(64),nullable=False),
        sa.Column('transaction_id',sa.String(64),nullable=False,unique=True),sa.Column('request_key',sa.String(64),nullable=False),
        sa.Column('receipt',sa.JSON,nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.ForeignKeyConstraint(['bill_id','user_id'],['phone_bills.id','phone_bills.user_id']),
        sa.ForeignKeyConstraint(['account_id','user_id'],['products.id','products.user_id']),
        sa.ForeignKeyConstraint(['transaction_id','user_id'],['transactions.id','transactions.user_id']),sa.UniqueConstraint('user_id','request_key'))
    op.create_index('ix_bill_payments_user_id','bill_payments',['user_id'])
    op.create_table('conversation_flows',
        sa.Column('conversation_id',sa.String(64),primary_key=True),sa.Column('user_id',sa.String(64),nullable=False),
        sa.Column('state',sa.JSON,nullable=False),sa.Column('request_id',sa.String(64),nullable=True),
        sa.ForeignKeyConstraint(['conversation_id','user_id'],['conversations.id','conversations.user_id']),
        sa.ForeignKeyConstraint(['request_id','user_id'],['requests.id','requests.user_id']))
    op.create_index('ix_conversation_flows_user_id','conversation_flows',['user_id'])
    op.create_table('assistant_turns',
        sa.Column('user_id',sa.String(64),sa.ForeignKey('users.id'),primary_key=True),sa.Column('request_key',sa.String(64),primary_key=True),
        sa.Column('fingerprint',sa.String(64),nullable=False),sa.Column('response',sa.JSON,nullable=False))


def downgrade():
    raise RuntimeError("Restore a verified backup to preserve payment receipts and conversation records.")
