"""Optional GPT-Live sessions; no changes to financial records."""
from alembic import op
import sqlalchemy as sa

revision = 'f492b731e845'
down_revision = 'f381a620d734'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('voice_sessions',
        sa.Column('id',sa.String(64),primary_key=True),
        sa.Column('user_id',sa.String(64),nullable=False),
        sa.Column('conversation_id',sa.String(64),nullable=False),
        sa.Column('auth_hash',sa.String(64),nullable=False),
        sa.Column('request_key',sa.String(64),nullable=False),
        sa.Column('provider_id',sa.String(128),nullable=True),
        sa.Column('status',sa.String(16),nullable=False),
        sa.Column('locale',sa.String(2),nullable=False),
        sa.Column('created_at',sa.BigInteger,nullable=False),
        sa.Column('expires_at',sa.BigInteger,nullable=False),
        sa.Column('heartbeat_at',sa.BigInteger,nullable=False),
        sa.Column('state',sa.JSON,nullable=False),
        sa.ForeignKeyConstraint(['conversation_id','user_id'],['conversations.id','conversations.user_id']),
        sa.UniqueConstraint('user_id','request_key'),
        sa.CheckConstraint("status IN ('connecting','active','closing','closed','failed')"))
    op.create_index('ix_voice_sessions_user_id','voice_sessions',['user_id'])
    op.create_index('ix_voice_sessions_conversation_id','voice_sessions',['conversation_id'])


def downgrade():
    raise RuntimeError('Restore a verified backup to preserve voice session audit records.')
