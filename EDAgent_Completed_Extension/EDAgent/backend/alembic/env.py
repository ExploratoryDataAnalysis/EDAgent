"""Alembic environment: uses the application's models and blocking database URL."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from app.core.config import settings
from app.core.database import Base
import app.models  # noqa: F401  (registers every table on Base.metadata)

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
URL = settings.sync_database_url
# SQLite reflects UUID columns as NUMERIC, which makes type comparison report false drift there.
COMPARE_TYPES = not URL.startswith("sqlite")


def run_migrations_offline() -> None:
    context.configure(url=URL, target_metadata=target_metadata, literal_binds=True, render_as_batch=URL.startswith("sqlite"), compare_type=COMPARE_TYPES)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(URL, poolclass=pool.NullPool)
    with engine.connect() as connection:
        # Batch mode lets SQLite apply ALTERs by recreating tables.
        context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=URL.startswith("sqlite"), compare_type=COMPARE_TYPES)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
