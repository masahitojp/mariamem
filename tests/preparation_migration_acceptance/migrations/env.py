"""Repository-authored online environment; explicit configuration, no route hook.

Uses the standard Alembic/SQLAlchemy engine_from_config entry, with NullPool.
This is not an unmodified upstream template or an arbitrary application adapter.
"""
from alembic import context
from sqlalchemy import engine_from_config, pool

config = context.config
engine = engine_from_config(config.get_section(config.config_ini_section),
                            prefix="sqlalchemy.", poolclass=pool.NullPool)
try:
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=None)
        with context.begin_transaction():
            context.run_migrations()
finally:
    engine.dispose()
