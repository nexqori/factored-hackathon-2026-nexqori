"""Initial independent laboratory schema."""
from alembic import op
from lab.db import Base
revision = "0001_lab"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    Base.metadata.create_all(op.get_bind())


def downgrade():
    raise RuntimeError("Destructive downgrade disabled; restore a reviewed local backup.")
