"""Tarefas de ingestão e recálculo, usadas pelo agendador e pela linha de comando."""

import logging
from contextlib import contextmanager
from datetime import date, timedelta

from sqlalchemy import func, select

from app.config import obter_configuracao
from app.db.modelos import DemonstracaoLinha
from app.db.sessao import FabricaSessao, motor
from app.ingestao import (
    b3_proventos,
    bcb_sgs,
    brapi,
    cotahist,
    cvm_companhias,
    cvm_demonstracoes,
    cvm_fii,
    fnet_rendimentos,
    tesouro,
)
from app.ingestao.base import garantir_fontes
from app.ingestao.padronizacao_db import padronizar_todas
from app.servicos.indicadores import recalcular

log = logging.getLogger(__name__)


def _executar(nome: str, funcao, *args):
    with FabricaSessao() as sessao:
        try:
            resultado = funcao(sessao, *args)
            log.info("%s: %s", nome, resultado)
            return resultado
        except Exception:
            log.exception("%s falhou", nome)
            return None


def preparar() -> None:
    with FabricaSessao() as sessao:
        garantir_fontes(sessao)
        sessao.commit()


def companhias(ano: int | None = None) -> None:
    ano = ano or date.today().year
    _executar("cadastro CVM", cvm_companhias.ingerir_cadastro)
    _executar(f"FCA {ano}", cvm_companhias.ingerir_valores_mobiliarios, ano)


def demonstracoes(anos: list[int]) -> None:
    for ano in anos:
        _executar(f"DFP {ano}", cvm_demonstracoes.ingerir, "DFP", ano)
        _executar(f"ITR {ano}", cvm_demonstracoes.ingerir, "ITR", ano)
    _executar("padronização", padronizar_todas)


def fiis(anos: list[int]) -> None:
    for ano in anos:
        _executar(f"FII mensal {ano}", cvm_fii.ingerir, ano)


def cotacoes_historicas(anos: list[int], somente_acompanhados: bool = False) -> None:
    tickers = set(obter_configuracao().lista_tickers) if somente_acompanhados else None
    for ano in anos:
        _executar(f"COTAHIST {ano}", cotahist.ingerir_ano, ano, tickers)


def cotacoes_do_dia(dia: date | None = None) -> None:
    dia = dia or date.today()
    _executar(f"COTAHIST {dia}", cotahist.ingerir_dia, dia)
    _executar("brapi", brapi.ingerir, obter_configuracao().lista_tickers)


def proventos(dias_fnet: int = 10) -> None:
    """Proventos de ações (B3) e rendimentos de FII (FNET). Depende do ISIN gravado pelo COTAHIST."""
    _executar("B3 proventos", b3_proventos.ingerir)
    _executar("FNET rendimentos", fnet_rendimentos.ingerir, dias_fnet)


def macro() -> None:
    _executar("BCB SGS", bcb_sgs.ingerir_todas)
    _executar("Tesouro", tesouro.ingerir, date.today() - timedelta(days=3650))


def indicadores(tickers: list[str] | None = None) -> None:
    _executar("recálculo de indicadores", recalcular, tickers)


def precisa_carga_inicial(sessao) -> bool:
    """Verdadeiro enquanto nenhuma demonstração da CVM foi gravada (instalação nova ou carga interrompida)."""
    return sessao.scalar(select(func.count()).select_from(DemonstracaoLinha)) == 0


ANOS_CARGA_INICIAL = 6  # 6 anos de DFP permitem o CAGR de 5 anos


def carga_inicial_se_vazio() -> None:
    with FabricaSessao() as sessao:
        if not precisa_carga_inicial(sessao):
            return
    ano = date.today().year
    log.info("banco sem dados: iniciando a carga inicial (%s–%s); pode levar bastante tempo",
             ano - ANOS_CARGA_INICIAL, ano)
    carga_inicial(ano - ANOS_CARGA_INICIAL, ano)


CHAVE_TRAVA_CARGA = 7_214_001  # trava consultiva do PostgreSQL (um número qualquer, fixo)


@contextmanager
def trava_exclusiva(chave: int = CHAVE_TRAVA_CARGA):
    """Garante uma carga por vez entre processos (worker e linha de comando). Devolve False se já há outra."""
    with motor.connect() as conexao:
        obtida = conexao.execute(select(func.pg_try_advisory_lock(chave))).scalar()
        try:
            yield bool(obtida)
        finally:
            if obtida:
                conexao.execute(select(func.pg_advisory_unlock(chave)))


def carga_inicial(ano_inicial: int, ano_final: int) -> None:
    with trava_exclusiva() as obtida:
        if not obtida:
            log.warning("já existe uma carga em andamento (worker ou outro terminal); esta foi ignorada")
            return
        _carga_inicial(ano_inicial, ano_final)


def _carga_inicial(ano_inicial: int, ano_final: int) -> None:
    anos = list(range(ano_inicial, ano_final + 1))
    preparar()
    companhias(ano_final)
    demonstracoes(anos)
    fiis(anos)
    cotacoes_historicas(anos)
    proventos(dias_fnet=400)  # 13 meses: cobre a janela de 12 meses do DY por data de pagamento
    macro()
    cotacoes_do_dia()
    indicadores()
