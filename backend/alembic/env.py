"""Alembic 迁移环境配置。

使用异步引擎，从 app.config 读取数据库 URL。
"""

import asyncio
from importlib import import_module
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from app.config import settings
from app.db.base import Base

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

MODEL_MODULES = (
    "app.modules.character_library.models",
    "app.modules.image_asset.audit_models",
    "app.modules.image_asset.models",
    "app.modules.novel_intake.models",
    "app.modules.project.models",
    "app.modules.prop_library.models",
    "app.modules.quality_retry.models",
    "app.modules.scene_library.models",
    "app.modules.story_bible.models",
    "app.modules.workflow.models",
)


def import_model_modules() -> None:
    """Register SQLAlchemy models with Base.metadata before autogenerate."""
    for module in MODEL_MODULES:
        import_module(module)


import_model_modules()
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """离线模式运行迁移。"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """在线模式运行迁移。"""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
