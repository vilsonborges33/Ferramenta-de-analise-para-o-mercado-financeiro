"""Tesouro dos EUA: taxa diária do título de 10 anos (taxa livre de risco dos valuations em dólar).

Fonte: "Daily Treasury Par Yield Curve Rates", CSV público do U.S. Department of the Treasury, por ano:
https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/{ano}/all
  ?type=daily_treasury_yield_curve&field_tdr_date_value={ano}&page&_format=csv
Gravada como série `UST10Y` (% a.a.).
"""

import csv
import io
from datetime import date, datetime

from sqlalchemy.dialects.postgresql import insert

from app.db.modelos import SerieEconomica
from app.ingestao.base import EsquemaInesperado, cliente_http, lote

URL = ("https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/{ano}/all"
       "?type=daily_treasury_yield_curve&field_tdr_date_value={ano}&page&_format=csv")
CODIGO = "UST10Y"


def parse(texto: str) -> list[tuple[date, float]]:
    leitor = csv.DictReader(io.StringIO(texto.lstrip("﻿")))
    if not leitor.fieldnames or "Date" not in leitor.fieldnames or "10 Yr" not in leitor.fieldnames:
        raise EsquemaInesperado("Treasury: CSV sem as colunas Date e 10 Yr")
    saida = []
    for linha in leitor:
        valor = (linha.get("10 Yr") or "").strip()
        if not valor:
            continue
        saida.append((datetime.strptime(linha["Date"].strip(), "%m/%d/%Y").date(), float(valor)))
    return sorted(saida)


def ingerir(sessao, ano: int | None = None, cliente=None) -> int:
    ano = ano or date.today().year
    url = URL.format(ano=ano)
    proprio = cliente is None
    cliente = cliente or cliente_http()
    try:
        with lote(sessao, "US_TREASURY", url) as ctx:
            resposta = cliente.get(url)
            resposta.raise_for_status()
            pontos = parse(resposta.text)
            for d, v in pontos:
                valores = {"codigo": CODIGO, "data": d, "valor": v, **ctx.procedencia(d)}
                stmt = insert(SerieEconomica).values(**valores)
                sessao.execute(stmt.on_conflict_do_update(
                    index_elements=["codigo", "data"],
                    set_={k: stmt.excluded[k] for k in valores if k not in ("codigo", "data")}))
            ctx.lote.linhas_gravadas = len(pontos)
            return len(pontos)
    finally:
        if proprio:
            cliente.close()
