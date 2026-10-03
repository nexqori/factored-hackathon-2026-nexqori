"""Own conversations, identity login and persisted reading preferences."""
from uuid import uuid4
from alembic import op
import sqlalchemy as sa

revision = "b721c95d024a"
down_revision = "a649a6f7e838"
branch_labels = None
depends_on = None


def upgrade():
    db = op.get_bind()
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("identity_number", sa.String(32), nullable=True))
        batch.add_column(sa.Column("text_size", sa.String(8), nullable=False, server_default="medium"))
        batch.create_unique_constraint("uq_users_identity_number", ["identity_number"])
        batch.create_check_constraint("ck_users_text_size", "text_size IN ('small','medium','large')")
        if db.dialect.name == "sqlite":
            batch.create_check_constraint("ck_users_role", "role IN ('customer','admin')")
            batch.create_check_constraint("ck_users_locale", "locale IN ('es','en','pt')")
    # Only the shipped fixture addresses change. Passwords and custom accounts stay intact.
    for uid, local, number in [("andrea", "andrea", "00000001"), ("nora", "admin", "00000002"), ("mateo", "mateo", "00000003")]:
        db.execute(sa.text("UPDATE users SET email=:email, identity_number=:number WHERE id=:id AND email=:old AND NOT EXISTS (SELECT 1 FROM users WHERE email=:email)"), {"id":uid, "old":local+"@nexqori.local", "email":local+"@nexqori.com", "number":number})
    op.create_table("conversations",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(100), nullable=True),
        sa.Column("locale", sa.String(2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("id", "user_id", name="uq_conversations_owner"),
        sa.CheckConstraint("locale IN ('es','en','pt')", name="ck_conversations_locale"))
    op.create_index("ix_conversations_user_id", "conversations", ["user_id"])
    op.add_column("messages", sa.Column("conversation_id", sa.String(64), nullable=True))
    messages = sa.table("messages", sa.column("user_id"), sa.column("created_at", sa.DateTime(timezone=True)), sa.column("conversation_id"))
    conversations = sa.table("conversations", sa.column("id"), sa.column("user_id"), sa.column("title"), sa.column("locale"), sa.column("created_at", sa.DateTime(timezone=True)), sa.column("updated_at", sa.DateTime(timezone=True)))
    users = sa.table("users", sa.column("id"), sa.column("locale"))
    for user_id, first, last in db.execute(sa.select(messages.c.user_id, sa.func.min(messages.c.created_at), sa.func.max(messages.c.created_at)).group_by(messages.c.user_id)).all():
        cid = str(uuid4())
        locale = db.scalar(sa.select(users.c.locale).where(users.c.id == user_id))
        db.execute(conversations.insert().values(id=cid, user_id=user_id, title=None, locale=locale, created_at=first, updated_at=last))
        db.execute(messages.update().where(messages.c.user_id == user_id).values(conversation_id=cid))
    with op.batch_alter_table("messages") as batch:
        batch.alter_column("conversation_id", existing_type=sa.String(64), nullable=False)
        batch.create_foreign_key("fk_messages_conversation_owner", "conversations", ["conversation_id", "user_id"], ["id", "user_id"])
        batch.create_index("ix_messages_conversation_id", ["conversation_id"])
        if db.dialect.name == "sqlite":
            batch.create_check_constraint("ck_messages_role", "role IN ('user','assistant')")
            batch.create_check_constraint("ck_messages_locale", "locale IN ('es','en','pt')")


def downgrade():
    # Do not silently merge separate conversations or discard identity/preferences.
    raise RuntimeError("Restore a verified database backup to roll back this data migration.")
