"""
Alembic migration environment.

Reads the DB URL from the app's Settings (so it always targets the same database
as the app and worker), converting the async driver to the sync psycopg2 driver
Alembic uses. target_metadata points at the app's SQLAlchemy Base so
autogenerate can diff future model changes.
"""
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# Import the app's metadata and settings.
from app.db.database import Base
from app.config import get_settings

# Ensure all models are imported so Base.metadata is fully populated.
import app.db.models  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _sync_url() -> str:
    """App URL (asyncpg) → sync psycopg2 URL that Alembic can use."""
    url = get_settings().database_url
    return url.replace("+asyncpg", "+psycopg2").replace(
        "postgresql+asyncpg", "postgresql+psycopg2"
    )


def run_migrations_offline() -> None:
    context.configure(
        url=_sync_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section) or {}
    section["sqlalchemy.url"] = _sync_url()
    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
