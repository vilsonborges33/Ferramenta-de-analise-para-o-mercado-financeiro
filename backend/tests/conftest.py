import os

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://analise:analise@localhost:5432/analise_teste")
os.environ.setdefault("DIRETORIO_DADOS_BRUTOS", "/tmp/claude-0/dados_brutos_teste")

import pytest  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.db import modelos  # noqa: E402,F401
from app.db.sessao import Base, FabricaSessao, motor  # noqa: E402
from app.ingestao.base import garantir_fontes  # noqa: E402


@pytest.fixture
def sessao():
    """Banco de teste recriado a cada teste (PostgreSQL; JSONB e upserts exigem Postgres)."""
    with motor.begin() as conexao:
        conexao.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
    Base.metadata.create_all(motor)
    with FabricaSessao() as s:
        garantir_fontes(s)
        s.commit()
        yield s
