"""Link audit records to conversations without copying their content."""
from alembic import op
import sqlalchemy as sa

revision = "f217a8e309bc"
down_revision = "e104b56a902c"
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table("audit_events") as batch:
        batch.add_column(sa.Column("conversation_id", sa.String(64), nullable=True))
        batch.create_foreign_key("fk_audit_conversation", "conversations", ["conversation_id"], ["id"])
        batch.create_index("ix_audit_events_conversation_id", ["conversation_id"])

def downgrade():
    with op.batch_alter_table("audit_events") as batch:
        batch.drop_index("ix_audit_events_conversation_id")
        batch.drop_constraint("fk_audit_conversation", type_="foreignkey")
        batch.drop_column("conversation_id")
