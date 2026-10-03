"""Documents, service receipts and transfers; preserve existing financial records."""
from alembic import op
import sqlalchemy as sa

revision = 'f381a620d734'
down_revision = 'e2715ba946c0'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('products', table_args=(sa.CheckConstraint("type IN ('account','savings','card')"), sa.CheckConstraint("currency = 'MXN'"))) as b:
        b.add_column(sa.Column('transfer_reference', sa.String(18), nullable=True))
        b.create_unique_constraint('uq_product_transfer_reference', ['transfer_reference'])
    # Naming convention also identifies the unnamed constraints on SQLite.
    convention = {'uq': '%(table_name)s_%(column_0_name)s_key'}
    bind = op.get_bind()
    bill_unique = next(c['name'] or 'phone_bills_user_id_key' for c in sa.inspect(bind).get_unique_constraints('phone_bills') if c['column_names'] == ['user_id','reference','period'])
    with op.batch_alter_table('phone_bills', naming_convention=convention, table_args=(sa.CheckConstraint("amount_minor > 0 AND currency = 'MXN'"),)) as b:
        b.add_column(sa.Column('service_id', sa.String(64), nullable=False, server_default='phone-bill'))
        b.add_column(sa.Column('allow_partial', sa.Boolean, nullable=False, server_default=sa.false()))
        b.alter_column('reference', existing_type=sa.String(24), type_=sa.String(64))
        b.drop_constraint(bill_unique, type_='unique')
        b.create_unique_constraint('uq_bill_service_period', ['user_id','service_id','reference','period'])
    payment_unique = next(c['name'] or 'bill_payments_bill_id_key' for c in sa.inspect(bind).get_unique_constraints('bill_payments') if c['column_names'] == ['bill_id'])
    with op.batch_alter_table('bill_payments', naming_convention=convention) as b:
        b.drop_constraint(payment_unique, type_='unique')
        b.add_column(sa.Column('fingerprint', sa.String(64), nullable=True))
        b.create_index('ix_bill_payments_bill_id', ['bill_id'])
    op.create_table('transfer_quotes',
        sa.Column('id',sa.String(64),primary_key=True), sa.Column('user_id',sa.String(64),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('recipient_user_id',sa.String(64),nullable=False), sa.Column('recipient_product_id',sa.String(64),nullable=False),
        sa.Column('expires_at',sa.BigInteger,nullable=False),
        sa.ForeignKeyConstraint(['recipient_product_id','recipient_user_id'],['products.id','products.user_id']))
    op.create_index('ix_transfer_quotes_user_id','transfer_quotes',['user_id'])
    op.create_table('bank_transfers',
        sa.Column('id',sa.String(64),primary_key=True), sa.Column('user_id',sa.String(64),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('recipient_user_id',sa.String(64),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('source_product_id',sa.String(64),nullable=False), sa.Column('recipient_product_id',sa.String(64),nullable=False),
        sa.Column('debit_transaction_id',sa.String(64),nullable=False,unique=True), sa.Column('credit_transaction_id',sa.String(64),nullable=False,unique=True),
        sa.Column('amount_minor',sa.BigInteger,nullable=False), sa.Column('request_key',sa.String(64),nullable=False),
        sa.Column('fingerprint',sa.String(64),nullable=False), sa.Column('receipt',sa.JSON,nullable=False), sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.ForeignKeyConstraint(['source_product_id','user_id'],['products.id','products.user_id']),
        sa.ForeignKeyConstraint(['recipient_product_id','recipient_user_id'],['products.id','products.user_id']),
        sa.ForeignKeyConstraint(['debit_transaction_id','user_id'],['transactions.id','transactions.user_id']),
        sa.ForeignKeyConstraint(['credit_transaction_id','recipient_user_id'],['transactions.id','transactions.user_id']),
        sa.UniqueConstraint('user_id','request_key'), sa.CheckConstraint('amount_minor > 0 AND user_id <> recipient_user_id'))
    for key in ('user_id','recipient_user_id'): op.create_index('ix_bank_transfers_'+key,'bank_transfers',[key])
    op.create_table('chat_documents',
        sa.Column('id',sa.String(64),primary_key=True), sa.Column('user_id',sa.String(64),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('conversation_id',sa.String(64),nullable=False), sa.Column('message_id',sa.String(64),sa.ForeignKey('messages.id'),nullable=False,unique=True),
        sa.Column('kind',sa.String(32),nullable=False), sa.Column('locale',sa.String(2),nullable=False), sa.Column('filename',sa.String(100),nullable=False),
        sa.Column('request_key',sa.String(64),nullable=False), sa.Column('fingerprint',sa.String(64),nullable=False),
        sa.Column('details',sa.JSON,nullable=False), sa.Column('content',sa.LargeBinary,nullable=False), sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.ForeignKeyConstraint(['conversation_id','user_id'],['conversations.id','conversations.user_id']), sa.UniqueConstraint('user_id','request_key'))
    for key in ('user_id','conversation_id'): op.create_index('ix_chat_documents_'+key,'chat_documents',[key])


def downgrade():
    raise RuntimeError('Restore a verified backup to preserve receipts, transfers and documents.')
