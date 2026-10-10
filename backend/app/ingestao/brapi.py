"""brapi.dev: cotação mais recente e, com plano pago, proventos.

GET https://brapi.dev/api/quote/{ticker}?token=...            (plano gratuito: 1 ticker por chamada)
GET https://brapi.dev/api/quote/{ticker}?dividends=true&...   (proventos: só planos pagos)

Termos: exibição no próprio app permitida; revenda/redistribuição proibida (FONTES_DE_DADOS.md).
O formato das respostas segue a documentação pública da brapi e precisa ser conferido na primeira
execução real (a rede deste ambiente de desenvolvimento bloqueia o domínio).
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.config import obter_configuracao
from app.db.modelos import Ativo, CotacaoDiaria, Provento
from app.ingestao.base import Contexto, cliente_http, lote

URL = "https://brapi.dev/api/quote/{ticker}"

TIPOS_PROVENTO = {
    "DIVIDENDO": "DIVIDENDO",
    "JCP": "JCP",
    "JUROS SOBRE CAPITAL PRÓPRIO": "JCP",
    "RENDIMENTO": "RENDIMENTO_FII",
    "AMORTIZAÇÃO": "AMORTIZACAO",
}


def _data_iso(texto: str | None) -> date | None:
    if not texto:
        return None
    return datetime.fromisoformat(texto.replace("Z", "+00:00")).date()


def parse_cotacao(resultado: dict) -> dict | None:
    preco = resultado.get("regularMarketPrice")
    instante = resultado.get("regularMarketTime")
    if preco is None or instante is None:
        return None
    volume_acoes = resultado.get("regularMarketVolume")
    return {
        "ticker": resultado["symbol"].upper(),
        "data": _data_iso(instante),
        "abertura": _dec(resultado.get("regularMarketOpen")),
        "maxima": _dec(resultado.get("regularMarketDayHigh")),
        "minima": _dec(resultado.get("regularMarketDayLow")),
        "fechamento": _dec(preco),
        # A brapi informa volume em quantidade de ações; o volume financeiro fica indisponível aqui
        # e é preenchido pelo COTAHIST quando o arquivo do dia é processado.
        "volume_financeiro": None,
        "negocios": None,
        "_volume_acoes": volume_acoes,
    }


def parse_proventos(resultado: dict) -> list[dict]:
    dados = (resultado.get("dividendsData") or {}).get("cashDividends") or []
    registros = []
    for d in dados:
        tipo = TIPOS_PROVENTO.get((d.get("label") or "").upper().strip())
        data_com = _data_iso(d.get("lastDatePrior"))
        if tipo is None or data_com is None or d.get("rate") is None:
            continue
        registros.append({
            "ticker": resultado["symbol"].upper(),
            "tipo": tipo,
            "valor_por_cota": _dec(d["rate"]),
            "data_aprovacao": _data_iso(d.get("approvedOn")),
            "data_com": data_com,
            "data_pagamento": _data_iso(d.get("paymentDate")),
        })
    return registros


def _dec(valor) -> Decimal | None:
    return None if valor is None else Decimal(str(valor))


def gravar_cotacoes(ctx: Contexto, registros: list[dict]) -> int:
    ativos = {a.ticker: a.id for a in ctx.sessao.scalars(select(Ativo))}
    gravados = 0
    for r in registros:
        ativo_id = ativos.get(r["ticker"])
        if ativo_id is None:
            continue
        valores = {k: v for k, v in r.items() if not k.startswith("_") and k != "ticker"}
        valores.update(ativo_id=ativo_id, **ctx.procedencia(r["data"]))
        # Não sobrescreve pregão já gravado pelo COTAHIST (fonte oficial).
        ctx.sessao.execute(insert(CotacaoDiaria).values(**valores).on_conflict_do_nothing())
        gravados += 1
    return gravados


def gravar_proventos(ctx: Contexto, registros: list[dict]) -> int:
    ativos = {a.ticker: a.id for a in ctx.sessao.scalars(select(Ativo))}
    gravados = 0
    for r in registros:
        ativo_id = ativos.get(r["ticker"])
        if ativo_id is None:
            continue
        valores = {k: v for k, v in r.items() if k != "ticker"}
        valores.update(ativo_id=ativo_id, **ctx.procedencia(r["data_com"]))
        ctx.sessao.execute(insert(Provento).values(**valores).on_conflict_do_nothing())
        gravados += 1
    return gravados


def ingerir(sessao, tickers: list[str]) -> dict[str, int]:
    cfg = obter_configuracao()
    params = {"token": cfg.brapi_token} if cfg.brapi_token else {}
    if cfg.brapi_proventos_habilitado:
        params["dividends"] = "true"
    totais = {"cotacoes": 0, "proventos": 0}
    with lote(sessao, "BRAPI", URL.format(ticker="*")) as ctx, cliente_http() as cliente:
        for ticker in tickers:
            resposta = cliente.get(URL.format(ticker=ticker), params=params)
            if resposta.status_code == 404:
                continue
            resposta.raise_for_status()
            for resultado in resposta.json().get("results", []):
                cotacao = parse_cotacao(resultado)
                if cotacao:
                    totais["cotacoes"] += gravar_cotacoes(ctx, [cotacao])
                if cfg.brapi_proventos_habilitado:
                    totais["proventos"] += gravar_proventos(ctx, parse_proventos(resultado))
        ctx.lote.linhas_gravadas = sum(totais.values())
    return totais
