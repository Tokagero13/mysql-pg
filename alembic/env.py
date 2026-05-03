import os
import builtins
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool
from sqlalchemy.engine import URL
from sqlalchemy.dialects.mysql import TINYINT

from alembic import context
from dotenv import load_dotenv

# sqlacodegen-файлы используют TINYINT без явного импорта.
# Подкладываем символ в builtins, чтобы импорт моделей не падал.
builtins.TINYINT = TINYINT

from models_pg import Base

# 1. Загружаем переменные окружения
load_dotenv()

# Объект config предоставляет доступ к значениям из alembic.ini
config = context.config

# Настройка логирования (стандартная из alembic.ini)
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 2. Собираем URL для подключения к базе данных из переменных окружения
db_url = URL.create(
    drivername="postgresql+psycopg",  # убедитесь, что у вас установлен psycopg (или используйте psycopg2)
    username=os.getenv("POSTGRES_USER"),
    password=os.getenv("POSTGRES_PASSWORD"),
    host=os.getenv("POSTGRES_HOST", "localhost"),
    port=os.getenv("POSTGRES_PORT", "5432"),
    database=os.getenv("POSTGRES_DB")
)

# Переопределяем опцию sqlalchemy.url в конфигурации
config.set_main_option("sqlalchemy.url", db_url.render_as_string(hide_password=False))

# Используем metadata из SQLAlchemy-моделей для autogenerate.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Запуск миграций в 'offline' режиме.

    В этом режиме мы настраиваем контекст только с URL,
    без создания Engine.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Запуск миграций в 'online' режиме.

    В этом режиме мы создаем Engine и связываем с ним соединение
    внутри контекста Alembic.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()