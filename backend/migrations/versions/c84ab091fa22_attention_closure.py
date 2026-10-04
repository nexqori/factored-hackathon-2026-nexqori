"""Merge Araceli feedback and current bank migrations; persist attention closure."""
from alembic import op
import sqlalchemy as sa

revision = 'c84ab091fa22'
down_revision = ('f5a306c829d1', 'b37d1f4c9a20')
branch_labels = None
depends_on = None


def upgrade():
    # Unknown timings remain NULL; zero would fabricate a measured duration.
    constraints = [sa.CheckConstraint("metric IN ('nps','csat','ces')"),
        sa.CheckConstraint("(metric = 'nps' AND score BETWEEN 0 AND 10) OR (metric = 'csat' AND score BETWEEN 1 AND 5) OR (metric = 'ces' AND score BETWEEN 1 AND 7)"),
        sa.CheckConstraint("locale IN ('es','en','pt')"),
        sa.CheckConstraint('form_duration_ms BETWEEN 0 AND 86400000'),
        sa.CheckConstraint('conversation_duration_ms BETWEEN 0 AND 604800000')]
    with op.batch_alter_table('chat_feedback', table_args=constraints) as batch:
        batch.alter_column('form_duration_ms', existing_type=sa.Integer(), nullable=True)
        batch.alter_column('conversation_duration_ms', existing_type=sa.Integer(), nullable=True)
    op.create_table('attention_reviews',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(64), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('request_id', sa.String(64), unique=True),
        sa.Column('conversation_id', sa.String(64), unique=True),
        sa.Column('resolved_by', sa.String(64), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('summary', sa.Text(), nullable=False),
        sa.Column('status', sa.String(16), nullable=False),
        sa.Column('confirmed_at', sa.BigInteger(), nullable=False),
        sa.Column('due_at', sa.BigInteger(), nullable=False),
        sa.Column('closed_at', sa.BigInteger()),
        sa.Column('checkpoint', sa.JSON(), nullable=False),
        sa.Column('snapshots', sa.JSON(), nullable=False),
        sa.Column('answers', sa.JSON(), nullable=False),
        sa.Column('answer_revision', sa.Integer(), nullable=False),
        sa.Column('submitted_at', sa.BigInteger()),
        sa.ForeignKeyConstraint(['request_id','user_id'], ['requests.id','requests.user_id']),
        sa.ForeignKeyConstraint(['conversation_id','user_id'], ['conversations.id','conversations.user_id']),
        sa.CheckConstraint('(request_id IS NULL) <> (conversation_id IS NULL)'),
        sa.CheckConstraint("status IN ('scheduled','closed','reopened')"),
        sa.CheckConstraint('due_at = confirmed_at + 900'))
    for field in ('user_id', 'status', 'due_at'):
        op.create_index('ix_attention_reviews_'+field, 'attention_reviews', [field])


def downgrade():
    op.drop_table('attention_reviews')
    # Preserve NULL timings rather than inventing data during downgrade.
