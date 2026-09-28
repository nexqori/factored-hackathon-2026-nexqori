from logging.config import fileConfig
from alembic import context
from sqlalchemy import create_engine, pool
from backend.models import Base
import os
config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)
url = os.environ['DATABASE_URL']
if context.is_offline_mode():
    context.configure(url=url, target_metadata=Base.metadata, literal_binds=True, dialect_opts={'paramstyle':'named'})
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_engine(url, poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
