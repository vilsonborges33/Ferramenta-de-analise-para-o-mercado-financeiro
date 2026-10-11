"""Banco Central — SGS: Selic, CDI, IPCA e dólar.

Endpoint: https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados?formato=json&dataInicial=..&dataFinal=..
Desde 26/03/2025 o filtro de datas é obrigatório e a janela máxima é de 10 anos para séries diárias.
"""

import logging
import time
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from app.db.modelos import SerieEconomica
from app.ingestao.base import Contexto, cliente_http, data_br, lote

log = logging.getLogger(__name__)

URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados"

# código interno → (código SGS, descrição, unidade)
SERIES: dict[str, tuple[int, str, str]] = {
    "SELIC_META": (432, "Meta Selic definida pelo Copom", "% a.a."),
    "SELIC_DIARIA": (11, "Taxa Selic diária", "% a.d."),
    "CDI": (12, "Taxa DI diária (CDI)", "% a.d."),
    "IPCA": (433, "IPCA — variação mensal", "% a.m."),
    "DOLAR_VENDA": (1, "Dólar comercial (venda)", "R$/US$"),
}
JANELA_MAXIMA = timedelta(days=365 * 10 - 5)
INICIO_PADRAO = date(2005, 1, 1)


def janelas(inicio: date, fim: date) -> list[tuple[date, date]]:
    """Divide [inicio, fim] em janelas de no máximo ~10 anos."""
    resultado = []
    atual = inicio
    while atual <= fim:
        proximo = min(atual + JANELA_MAXIMA, fim)
        resultado.append((atual, proximo))
        atual = proximo + timedelta(days=1)
    return resultado


def parse(dados: list[dict]) -> list[tuple[date, Decimal]]:
    return [(data_br(d["data"]), Decimal(str(d["valor"]))) for d in dados if d.get("valor") not in (None, "")]


def gravar(ctx: Contexto, codigo: str, pontos: list[tuple[date, Decimal]]) -> int:
    if not pontos:
        return 0
    linhas = [{"codigo": codigo, "data": d, "valor": v, **ctx.procedencia(d)} for d, v in pontos]
    stmt = insert(SerieEconomica)
    stmt = stmt.on_conflict_do_update(
        index_elements=["codigo", "data"],
        set_={c: stmt.excluded[c] for c in ("valor", "lote_ingestao_id", "coletado_em")})
    ctx.sessao.execute(stmt, linhas)
    return len(linhas)


def consultar(cliente, codigo_sgs: int, de: date, ate: date, tentativas: int = 3, espera: float = 2.0) -> list | None:
    """Uma janela da série. Devolve a lista de pontos, [] se não houver dados, ou None se a API
    responder algo que não é JSON mesmo após novas tentativas (instabilidade do SGS)."""
    params = {"formato": "json", "dataInicial": de.strftime("%d/%m/%Y"), "dataFinal": ate.strftime("%d/%m/%Y")}
    for tentativa in range(1, tentativas + 1):
        resposta = cliente.get(URL.format(codigo=codigo_sgs), params=params)
        if resposta.status_code == 404:  # janela sem observações
            return []
        if resposta.status_code < 500:
            resposta.raise_for_status()
            try:
                return resposta.json()
            except ValueError:
                pass
        log.warning("SGS %s (%s a %s): resposta inválida (HTTP %s, início: %r), tentativa %s/%s",
                    codigo_sgs, params["dataInicial"], params["dataFinal"], resposta.status_code,
                    resposta.text[:120], tentativa, tentativas)
        if tentativa < tentativas:
            time.sleep(espera * tentativa)
    return None


def ingerir(sessao, codigo: str, inicio: date | None = None, fim: date | None = None, cliente=None) -> int:
    codigo_sgs = SERIES[codigo][0]
    if inicio is None:
        ultima = sessao.scalar(select(func.max(SerieEconomica.data)).where(SerieEconomica.codigo == codigo))
        inicio = (ultima + timedelta(days=1)) if ultima else INICIO_PADRAO
    fim = fim or date.today()
    if inicio > fim:
        return 0
    total, janelas_falhas = 0, 0
    proprio = cliente is None
    cliente = cliente or cliente_http()
    try:
        with lote(sessao, "BCB_SGS", URL.format(codigo=codigo_sgs)) as ctx:
            for de, ate in janelas(inicio, fim):
                dados = consultar(cliente, codigo_sgs, de, ate)
                if dados is None:
                    janelas_falhas += 1
                    continue
                total += gravar(ctx, codigo, parse(dados))
            ctx.lote.linhas_gravadas = total
            if janelas_falhas:
                ctx.lote.erro = f"{janelas_falhas} janela(s) sem resposta válida do SGS; tentar de novo mais tarde"
    finally:
        if proprio:
            cliente.close()
    return total


def ingerir_todas(sessao) -> dict[str, int | str]:
    """Cada série é independente: a falha de uma não impede as outras."""
    resultado: dict[str, int | str] = {}
    for codigo in SERIES:
        try:
            resultado[codigo] = ingerir(sessao, codigo)
        except Exception as erro:
            log.exception("SGS %s falhou", codigo)
            resultado[codigo] = f"erro: {erro!r}"[:200]
    return resultado
