"""Banco Central — SGS: Selic, CDI, IPCA e dólar.

Endpoint: https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados?formato=json&dataInicial=..&dataFinal=..
Desde 26/03/2025 o filtro de datas é obrigatório e a janela máxima é de 10 anos para séries diárias.
"""

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from app.db.modelos import SerieEconomica
from app.ingestao.base import Contexto, cliente_http, data_br, lote

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


def ingerir(sessao, codigo: str, inicio: date | None = None, fim: date | None = None) -> int:
    codigo_sgs = SERIES[codigo][0]
    if inicio is None:
        ultima = sessao.scalar(select(func.max(SerieEconomica.data)).where(SerieEconomica.codigo == codigo))
        inicio = (ultima + timedelta(days=1)) if ultima else INICIO_PADRAO
    fim = fim or date.today()
    if inicio > fim:
        return 0
    total = 0
    with lote(sessao, "BCB_SGS", URL.format(codigo=codigo_sgs)) as ctx, cliente_http() as cliente:
        for de, ate in janelas(inicio, fim):
            resposta = cliente.get(URL.format(codigo=codigo_sgs), params={
                "formato": "json", "dataInicial": de.strftime("%d/%m/%Y"), "dataFinal": ate.strftime("%d/%m/%Y")})
            if resposta.status_code == 404:  # janela sem observações
                continue
            resposta.raise_for_status()
            total += gravar(ctx, codigo, parse(resposta.json()))
        ctx.lote.linhas_gravadas = total
    return total


def ingerir_todas(sessao) -> dict[str, int]:
    return {codigo: ingerir(sessao, codigo) for codigo in SERIES}
