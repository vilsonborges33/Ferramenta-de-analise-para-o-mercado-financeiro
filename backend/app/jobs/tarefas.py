"""Tarefas de ingestão e recálculo, usadas pelo agendador e pela linha de comando."""

import logging
from datetime import date, timedelta

from app.config import obter_configuracao
from app.db.sessao import FabricaSessao
from app.ingestao import bcb_sgs, brapi, cotahist, cvm_companhias, cvm_demonstracoes, cvm_fii, tesouro
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


def macro() -> None:
    _executar("BCB SGS", bcb_sgs.ingerir_todas)
    _executar("Tesouro", tesouro.ingerir, date.today() - timedelta(days=3650))


def indicadores(tickers: list[str] | None = None) -> None:
    _executar("recálculo de indicadores", recalcular, tickers)


def carga_inicial(ano_inicial: int, ano_final: int) -> None:
    anos = list(range(ano_inicial, ano_final + 1))
    preparar()
    companhias(ano_final)
    demonstracoes(anos)
    fiis(anos)
    cotacoes_historicas(anos)
    macro()
    cotacoes_do_dia()
    indicadores()
