"""Yahoo Finance: cotações diárias e dividendos de ações e FIIs da B3 (sufixo ".SA").

GET https://query1.finance.yahoo.com/v8/finance/chart/{TICKER}.SA?range=6y&interval=1d&events=div
Resposta: chart.result[0] com `timestamp`, `indicators.quote[0]` (open/high/low/close/volume) e
`events.dividends` ({ts: {amount, date}}).

Limitações (DECISOES.md D-027):
- API não oficial, sem contrato; os termos do Yahoo restringem uso automatizado. Uso pessoal.
- O preço `close` já vem ajustado por desdobramentos/grupamentos.
- Dividendos vêm pela data-ex, sem data de pagamento e sem separar JCP de dividendo (valor bruto).
- O volume é em quantidade; o volume financeiro é estimado como fechamento × quantidade.
"""

import logging
import time
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.db.modelos import Ativo, CotacaoDiaria, Provento
from app.ingestao.base import Contexto, EsquemaInesperado, cliente_http, lote

log = logging.getLogger(__name__)

URL = "https://query1.finance.yahoo.com/v8/finance/chart/{simbolo}"
# O Yahoo recusa (HTTP 429) clientes sem cara de navegador.
CABECALHOS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/128.0 Safari/537.36", "Accept": "application/json"}


def simbolo(ticker: str) -> str:
    return f"{ticker.upper()}.SA"


def _data_local(ts: int, deslocamento: int) -> date:
    return datetime.fromtimestamp(ts + deslocamento, tz=UTC).date()


def dia_util_anterior(d: date) -> date:
    """Data-com = pregão anterior à data-ex (feriados não considerados)."""
    d -= timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def _dec(valor) -> Decimal | None:
    return None if valor is None else Decimal(str(valor))


def parse(corpo: dict, classe: str = "ACAO") -> dict:
    """Converte a resposta do /chart em {cotacoes: [...], dividendos: [...]}; erro do Yahoo → EsquemaInesperado."""
    grafico = (corpo or {}).get("chart") or {}
    if grafico.get("error"):
        erro = grafico["error"]
        raise EsquemaInesperado(f"Yahoo: {erro.get('code')} — {erro.get('description')}")
    resultados = grafico.get("result") or []
    if not resultados:
        raise EsquemaInesperado("Yahoo: resposta sem resultado")
    r = resultados[0]
    deslocamento = int((r.get("meta") or {}).get("gmtoffset") or 0)
    tempos = r.get("timestamp") or []
    quote = ((r.get("indicators") or {}).get("quote") or [{}])[0]
    cotacoes = []
    for i, ts in enumerate(tempos):
        fechamento = (quote.get("close") or [None] * len(tempos))[i]
        if fechamento is None:
            continue
        volume = (quote.get("volume") or [None] * len(tempos))[i]
        cotacoes.append({
            "data": _data_local(ts, deslocamento),
            "abertura": _dec((quote.get("open") or [None] * len(tempos))[i]),
            "maxima": _dec((quote.get("high") or [None] * len(tempos))[i]),
            "minima": _dec((quote.get("low") or [None] * len(tempos))[i]),
            "fechamento": _dec(fechamento),
            "negocios": None,
            "volume_financeiro": None if volume is None else _dec(fechamento) * Decimal(volume),
        })
    dividendos = []
    for evento in ((r.get("events") or {}).get("dividends") or {}).values():
        valor = _dec(evento.get("amount"))
        if valor is None or valor <= 0 or evento.get("date") is None:
            continue
        data_ex = _data_local(int(evento["date"]), deslocamento)
        dividendos.append({
            "tipo": "RENDIMENTO_FII" if classe == "FII" else "DIVIDENDO",
            "valor_por_cota": valor, "data_ex": data_ex, "data_com": dia_util_anterior(data_ex),
            "data_pagamento": None, "data_aprovacao": None,
        })
    return {"cotacoes": cotacoes, "dividendos": dividendos}


def gravar(ctx: Contexto, ativo_id: int, dados: dict) -> int:
    linhas = [{**c, "ativo_id": ativo_id, **ctx.procedencia(c["data"])} for c in dados["cotacoes"]]
    for i in range(0, len(linhas), 2000):
        bloco = linhas[i:i + 2000]
        stmt = insert(CotacaoDiaria)
        stmt = stmt.on_conflict_do_update(
            index_elements=["ativo_id", "data"],
            set_={c: stmt.excluded[c] for c in bloco[0] if c not in ("ativo_id", "data")})
        ctx.sessao.execute(stmt, bloco)
    for d in dados["dividendos"]:
        valores = {**d, "ativo_id": ativo_id, **ctx.procedencia(d["data_ex"])}
        ctx.sessao.execute(insert(Provento).values(**valores).on_conflict_do_nothing())
    return len(linhas) + len(dados["dividendos"])


def _consultar(cliente, ticker: str, intervalo: str, tentativas: int = 3, espera: float = 2.0):
    params = {"range": intervalo, "interval": "1d", "events": "div", "includeAdjustedClose": "true"}
    for tentativa in range(1, tentativas + 1):
        resposta = cliente.get(URL.format(simbolo=simbolo(ticker)), params=params, headers=CABECALHOS)
        if resposta.status_code == 429 and tentativa < tentativas:  # limite de requisições: espera e tenta de novo
            time.sleep(espera * tentativa)
            continue
        return resposta
    return resposta


def ingerir(sessao, tickers: list[str] | None = None, intervalo: str = "5d", cliente=None,
            pausa: float = 0.4) -> int:
    """Cotações e dividendos de cada ação/unit/FII ativo. Falhas isoladas não param os demais.

    `intervalo`: "5d" na atualização diária, "6y" na carga inicial.
    """
    consulta = select(Ativo).where(Ativo.ativo.is_(True), Ativo.classe.in_(("ACAO", "UNIT", "FII")))
    if tickers:
        consulta = consulta.where(Ativo.ticker.in_([t.upper() for t in tickers]))
    ativos = [(a.id, a.ticker, a.classe) for a in sessao.scalars(consulta)]
    proprio = cliente is None
    cliente = cliente or cliente_http()
    total, falhas, sem_dados = 0, [], []
    try:
        with lote(sessao, "YAHOO_FINANCE", URL.format(simbolo="*")) as ctx:
            for i, (ativo_id, ticker, classe) in enumerate(ativos):
                if i and pausa:
                    time.sleep(pausa)
                try:
                    resposta = _consultar(cliente, ticker, intervalo)
                    if resposta.status_code == 404:
                        sem_dados.append(ticker)
                        continue
                    resposta.raise_for_status()
                    with sessao.begin_nested():
                        total += gravar(ctx, ativo_id, parse(resposta.json(), classe))
                except EsquemaInesperado:
                    sem_dados.append(ticker)  # ticker sem negociação/histórico no Yahoo
                except Exception as erro:
                    falhas.append(f"{ticker}: {erro!r}"[:120])
            ctx.lote.linhas_gravadas = total
            partes = []
            if sem_dados:
                partes.append(f"{len(sem_dados)} ticker(s) sem dados no Yahoo (ex.: {', '.join(sem_dados[:8])})")
            if falhas:
                partes.append(f"{len(falhas)} com falha (ex.: {'; '.join(falhas[:3])})")
            ctx.lote.erro = "; ".join(partes) or None
            if ativos and len(falhas) == len(ativos):
                raise RuntimeError("todas as consultas ao Yahoo falharam: " + falhas[0])
    finally:
        if proprio:
            cliente.close()
    log.info("Yahoo: %s linhas; %s sem dados; %s falhas", total, len(sem_dados), len(falhas))
    return total
