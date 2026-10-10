"""Configuração lida do ambiente / arquivo .env."""

import logging
import secrets
from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Configuracao(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://analise:analise@localhost:5432/analise"
    jwt_segredo: str = "trocar-este-segredo-no-arquivo-env-antes-de-usar"
    jwt_expiracao_horas: int = 24 * 7
    cookie_seguro: bool = False
    cors_origens: str = "http://localhost:3000"

    # Identificação enviada no User-Agent (boa prática; exigida pela SEC na Fase 7).
    contato_user_agent: str = "analise-mercado (contato: definir no .env)"

    brapi_token: str = ""
    # O plano gratuito da brapi não inclui proventos; ligar só com plano pago.
    brapi_proventos_habilitado: bool = False

    # Tickers consultados na brapi (limite do plano gratuito: 1 ticker por chamada, 15 mil/mês).
    tickers_acompanhados: str = (
        "PETR4,VALE3,ITUB4,WEGE3,ABEV3,EGIE3,MGLU3,RADL3,TAEE11,SUZB3,"
        "HGLG11,KNRI11,MXRF11,XPML11,VISC11,HGRU11,KNCR11,BTLG11,HSML11,RBRF11"
    )

    diretorio_dados_brutos: Path = Path("dados_brutos")
    agendador_habilitado: bool = True


    @field_validator("jwt_segredo")
    @classmethod
    def segredo_preenchido(cls, v: str) -> str:
        if not v.strip():
            # Sem segredo no .env: gera um aleatório (as sessões caem a cada reinício do backend).
            logging.getLogger(__name__).warning("JWT_SEGREDO vazio: usando segredo aleatório temporário")
            return secrets.token_hex(32)
        return v

    @property
    def lista_tickers(self) -> list[str]:
        return [t.strip().upper() for t in self.tickers_acompanhados.split(",") if t.strip()]


@lru_cache
def obter_configuracao() -> Configuracao:
    return Configuracao()
