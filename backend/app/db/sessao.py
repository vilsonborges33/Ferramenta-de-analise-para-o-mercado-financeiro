from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import obter_configuracao


class Base(DeclarativeBase):
    pass


motor = create_engine(obter_configuracao().database_url, pool_pre_ping=True)
FabricaSessao = sessionmaker(bind=motor, expire_on_commit=False)


def obter_sessao() -> Iterator[Session]:
    """Dependência do FastAPI: uma sessão por requisição."""
    with FabricaSessao() as sessao:
        yield sessao
