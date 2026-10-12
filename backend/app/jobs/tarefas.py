"""Tarefas de ingestão e recálculo, usadas pelo agendador e pela linha de comando."""

import logging
from contextlib import contextmanager
from datetime import date, timedelta

from sqlalchemy import func, select

from app.config import obter_configuracao
from app.db.modelos import Ativo, CotacaoDiaria, DemonstracaoLinha, Provento
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
    yahoo,
)
from app.ingestao.base import garantir_fontes
from app.ingestao.padronizacao_db import empresas_sem_padronizacao, padronizar_todas
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


def usa_yahoo() -> bool:
    return obter_configuracao().fonte_mercado == "yahoo"


def cotacoes_historicas(anos: list[int], somente_acompanhados: bool = False) -> None:
    """Histórico de cotações (e, no Yahoo, também dos dividendos) cobrindo os anos pedidos."""
    tickers = set(obter_configuracao().lista_tickers) if somente_acompanhados else None
    if usa_yahoo():
        anos_atras = date.today().year - min(anos) + 1
        _executar("Yahoo Finance (histórico)", yahoo.ingerir, sorted(tickers) if tickers else None, f"{anos_atras}y")
        return
    for ano in anos:
        _executar(f"COTAHIST {ano}", cotahist.ingerir_ano, ano, tickers)


def cotacoes_do_dia(dia: date | None = None) -> None:
    if usa_yahoo():
        _executar("Yahoo Finance (últimos dias)", yahoo.ingerir, None, "5d")
        return
    dia = dia or date.today()
    _executar(f"COTAHIST {dia}", cotahist.ingerir_dia, dia)
    _executar("brapi", brapi.ingerir, obter_configuracao().lista_tickers)


def proventos(dias_fnet: int = 10) -> None:
    """Proventos. No Yahoo vêm junto com as cotações (último ano); senão, B3 (ações) e FNET (FIIs)."""
    if usa_yahoo():
        _executar("Yahoo Finance (dividendos)", yahoo.ingerir, None, "2y")
        return
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


def faltam_cotacoes(sessao) -> bool:
    """Menos da metade das ações ativas tem cotação (ex.: só as poucas que a brapi gratuita libera)."""
    acoes = sessao.scalar(select(func.count()).select_from(Ativo).where(Ativo.classe == "ACAO", Ativo.ativo.is_(True)))
    com_cotacao = sessao.scalar(select(func.count(func.distinct(CotacaoDiaria.ativo_id)))
                                .join(Ativo, Ativo.id == CotacaoDiaria.ativo_id).where(Ativo.classe == "ACAO"))
    return acoes > 0 and com_cotacao < acoes / 2


def faltam_proventos(sessao) -> bool:
    return sessao.scalar(select(func.count()).select_from(Provento)) == 0


def _passo(nome: str, funcao, *args) -> None:
    """Executa um passo do complemento sem deixar uma falha interromper os seguintes."""
    try:
        funcao(*args)
    except Exception:
        log.exception("%s falhou", nome)


def _criar_tickers_fii() -> None:
    with FabricaSessao() as sessao:  # FIIs ganham ticker pelo ISIN (antes vinha do COTAHIST)
        cvm_fii.criar_ativos_pelo_isin(sessao)
        cotahist.ligar_fiis_por_isin(sessao)
        sessao.commit()


def completar_carga(forcar: bool = False) -> None:
    """Instalação com carga parcial: organiza balanços pendentes, busca cotações/dividendos que faltam
    e recalcula. Com `forcar`, refaz cotações e dividendos mesmo que pareçam completos."""
    with trava_exclusiva() as obtida:
        if not obtida:
            log.warning("já existe uma carga em andamento; complemento ignorado")
            return
        with FabricaSessao() as sessao:
            sem_padronizacao = empresas_sem_padronizacao(sessao)
            sem_cotacoes = forcar or faltam_cotacoes(sessao)
            sem_proventos = forcar or faltam_proventos(sessao)
        if not (sem_padronizacao or sem_cotacoes or sem_proventos):
            return
        ano = date.today().year
        _passo("tickers de FII", _criar_tickers_fii)
        if sem_padronizacao:
            log.info("%s empresa(s) com balanço sem períodos organizados: reorganizando", sem_padronizacao)
            _passo("padronização", _executar, "padronização", padronizar_todas)
        if sem_cotacoes:
            log.info("faltam cotações: baixando de %s a %s", ano - ANOS_CARGA_INICIAL, ano)
            _passo("cotações", cotacoes_historicas, list(range(ano - ANOS_CARGA_INICIAL, ano + 1)))
        if sem_proventos and not (usa_yahoo() and sem_cotacoes):  # no Yahoo, o histórico já trouxe os dividendos
            _passo("proventos", proventos, 400)
        _passo("indicadores", indicadores)


def carga_inicial_se_vazio() -> None:
    with FabricaSessao() as sessao:
        if not precisa_carga_inicial(sessao):
            parcial = True
        else:
            parcial = False
    if parcial:
        completar_carga()
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
    if not usa_yahoo():  # no Yahoo, o histórico de cotações já traz os dividendos
        proventos(dias_fnet=400)  # 13 meses: cobre a janela de 12 meses do DY por data de pagamento
    macro()
    cotacoes_do_dia()
    indicadores()
