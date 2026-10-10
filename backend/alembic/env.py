from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config import obter_configuracao
from app.db import modelos  # noqa: F401  (registra as tabelas)
from app.db.sessao import Base

config = context.config
config.set_main_option("sqlalchemy.url", obter_configuracao().database_url)
target_metadata = Base.metadata


def run_migrations_online() -> None:
    motor = engine_from_config(config.get_section(config.config_ini_section), prefix="sqlalchemy.",
                               poolclass=pool.NullPool)
    with motor.connect() as conexao:
        context.configure(connection=conexao, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
