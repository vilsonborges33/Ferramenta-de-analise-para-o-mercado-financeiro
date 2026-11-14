import os

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://analise:analise@localhost:5432/analise_teste")
os.environ.setdefault("DIRETORIO_DADOS_BRUTOS", "/tmp/claude-0/dados_brutos_teste")

# Trava de segurança: os testes apagam e recriam o schema a cada caso. Rodar contra o banco de uso
# (ex.: `pytest` dentro do container, onde DATABASE_URL já aponta para "analise") apagaria tudo.
# Use TEST_DATABASE_URL ou um banco cujo nome termine em "_teste".
if os.environ.get("TEST_DATABASE_URL"):
    os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
if not os.environ["DATABASE_URL"].rsplit("/", 1)[-1].split("?")[0].endswith("_teste"):
    raise SystemExit(
        "Testes recusados: DATABASE_URL não aponta para um banco de teste (nome terminado em _teste). "
        "Defina TEST_DATABASE_URL=postgresql+psycopg://.../analise_teste.")

import pytest  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.db import modelos  # noqa: E402,F401
from app.db.sessao import Base, FabricaSessao, motor  # noqa: E402
from app.ingestao.base import garantir_fontes  # noqa: E402


@pytest.fixture
def sessao():
    """Banco de teste recriado a cada teste (PostgreSQL; JSONB e upserts exigem Postgres)."""
    from app.servicos.ranking import limpar_cache
    limpar_cache()  # o ranking guarda o universo por 60 s; cada teste tem um banco novo
    with motor.begin() as conexao:
        conexao.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
    Base.metadata.create_all(motor)
    with FabricaSessao() as s:
        garantir_fontes(s)
        s.commit()
        yield s
