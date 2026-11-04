"""Séries da página do ativo: histórico anual (balanço e DRE), dividendos por ano e risco dos últimos 12 meses.

Os números saem das demonstrações padronizadas da CVM, das cotações e dos proventos já gravados; as contas
usam as funções puras de `app/metodologias`. Cada série informa a fonte e a data de referência.
"""

from bisect import bisect_right
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import obter_configuracao
from app.db.modelos import Ativo, CotacaoDiaria, DemonstracaoPadronizada, Fonte, Provento, SerieEconomica
from app.metodologias import indicadores_basicos as ib
from app.metodologias import portfolio
from app.metodologias.registro import POR_ID


def _ativo(sessao: Session, ticker: str) -> Ativo | None:
    return sessao.scalar(select(Ativo).where(Ativo.ticker == ticker.upper()))


def _cotacoes(sessao: Session, ativo_id: int) -> list[tuple[date, float]]:
    return [(d, float(f)) for d, f in sessao.execute(
        select(CotacaoDiaria.data, CotacaoDiaria.fechamento).where(CotacaoDiaria.ativo_id == ativo_id)
        .order_by(CotacaoDiaria.data))]


def _preco_em(cotacoes: list[tuple[date, float]], dia: date) -> tuple[float | None, str | None]:
    """Último fechamento até `dia` (inclusive)."""
    i = bisect_right([d for d, _ in cotacoes], dia)
    return (cotacoes[i - 1][1], cotacoes[i - 1][0].isoformat()) if i else (None, None)


def _v(resultado) -> float | None:
    return resultado.valor


def historico_anual(sessao: Session, ticker: str, anos: int = 10) -> dict | None:
    ativo = _ativo(sessao, ticker)
    if ativo is None or ativo.empresa_id is None:
        return None
    fontes = {f.id: f.codigo for f in sessao.scalars(select(Fonte))}
    periodos = list(sessao.scalars(select(DemonstracaoPadronizada).where(
        DemonstracaoPadronizada.empresa_id == ativo.empresa_id, DemonstracaoPadronizada.tipo_periodo == "ano")
        .order_by(DemonstracaoPadronizada.data_fim.desc()).limit(anos)))
    cotacoes = _cotacoes(sessao, ativo.id)
    linhas = []
    for p in reversed(periodos):
        c = p.campos
        g = c.get
        lucro = g("lucro_liquido_controladores", g("lucro_liquido"))
        pl = g("patrimonio_liquido_controladores", g("patrimonio_liquido"))
        ebitda = _v(ib.ebitda(g("ebit"), g("depreciacao_amortizacao")))
        bruta = _v(ib.divida_bruta(g("emprestimos_cp"), g("emprestimos_lp")))
        liquida = _v(ib.divida_liquida(bruta, g("caixa_equivalentes"), g("aplicacoes_financeiras")))
        preco, data_preco = _preco_em(cotacoes, p.data_fim)
        linhas.append({
            "ano": p.data_fim.year, "data_referencia": p.data_fim.isoformat(), "fonte": fontes.get(p.fonte_id),
            "consolidado": p.consolidado,
            "receita_liquida": g("receita_liquida"), "ebit": g("ebit"), "ebitda": ebitda, "lucro_liquido": lucro,
            "patrimonio_liquido": pl, "ativo_total": g("ativo_total"), "passivo_total": g("passivo_total"),
            "divida_bruta": bruta, "divida_liquida": liquida, "fco": g("fco"), "capex": g("capex"),
            "dividendos_pagos": g("dividendos_pagos"),
            "margem_bruta": _v(ib.margem(g("lucro_bruto"), g("receita_liquida"), "lucro bruto")),
            "margem_ebit": _v(ib.margem(g("ebit"), g("receita_liquida"), "EBIT")),
            "margem_liquida": _v(ib.margem(lucro, g("receita_liquida"), "lucro líquido")),
            "roe": _v(ib.roe(lucro, pl)),
            "dl_ebitda": _v(ib.divida_liquida_sobre(liquida, ebitda, "EBITDA")),
            "cotacao_fim_ano": preco, "data_cotacao": data_preco,
        })
    cagr_pl = None
    if len(linhas) >= 2:
        cagr_pl = _v(ib.cagr(linhas[0]["patrimonio_liquido"], linhas[-1]["patrimonio_liquido"],
                             linhas[-1]["ano"] - linhas[0]["ano"]))
    return {"ticker": ativo.ticker, "anos": linhas, "cagr_patrimonio": cagr_pl,
            "observacao": ("Valores em dólares, relatórios anuais (10-K) da SEC padronizados." if ativo.mercado == "US"
                           else "Valores em reais, demonstrações anuais (DFP) padronizadas.")
                          + " Cotação: último fechamento até o fim do exercício."}


def _codigos_fonte_proventos(classe: str) -> list[str]:
    if obter_configuracao().fonte_mercado == "yahoo":
        return ["YAHOO_FINANCE"]
    return ["FNET_RENDIMENTOS" if classe == "FII" else "B3_PROVENTOS", "BRAPI"]


CRITERIO_EUA = ("Dividendos brutos em dólares, somados pela data-ex (o Yahoo não informa o pagamento). Para "
                "residentes no Brasil, os EUA retêm 30% na fonte.")


def dividendos(sessao: Session, ticker: str, anos: int = 10) -> dict | None:
    ativo = _ativo(sessao, ticker)
    if ativo is None:
        return None
    codigos = _codigos_fonte_proventos(ativo.classe)
    fontes = {f.id: f.codigo for f in sessao.scalars(select(Fonte))}
    ids_fonte = [i for i, c in fontes.items() if c in codigos]
    hoje = date.today()
    inicio = date(hoje.year - anos + 1, 1, 1)
    data_janela = func.coalesce(Provento.data_pagamento, Provento.data_ex, Provento.data_com)
    proventos = list(sessao.scalars(select(Provento).where(
        Provento.ativo_id == ativo.id, Provento.fonte_id.in_(ids_fonte), data_janela >= inicio)
        .order_by(data_janela.desc())))
    aliquota = POR_ID["basico.dy"].parametros[0].padrao
    cotacoes = _cotacoes(sessao, ativo.id)
    pagamentos, por_ano = [], {}
    for p in proventos:
        bruto = float(p.valor_por_cota)
        liquido = ib.provento_liquido(bruto, p.tipo, aliquota).valor
        referencia = p.data_pagamento or p.data_ex or p.data_com
        pagamentos.append({"tipo": p.tipo, "valor_bruto": bruto, "valor_liquido": liquido,
                           "data_com": p.data_com.isoformat(), "data_ex": p.data_ex and p.data_ex.isoformat(),
                           "data_pagamento": p.data_pagamento and p.data_pagamento.isoformat(),
                           "fonte": fontes.get(p.fonte_id)})
        por_ano[referencia.year] = por_ano.get(referencia.year, 0.0) + liquido
    anuais = []
    for ano in range(inicio.year, hoje.year + 1):
        total = por_ano.get(ano, 0.0)
        preco, data_preco = _preco_em(cotacoes, min(date(ano, 12, 31), hoje))
        anuais.append({"ano": ano, "total_liquido": total, "cotacao": preco, "data_cotacao": data_preco,
                       "dividend_yield": ib.dividend_yield(total, preco).valor if preco else None,
                       "parcial": ano == hoje.year})
    # Anos antes do primeiro provento e sem cotação não informam nada: saem da série.
    while anuais and anuais[0]["total_liquido"] == 0 and anuais[0]["cotacao"] is None:
        anuais.pop(0)
    yields = [a["dividend_yield"] for a in anuais if a["dividend_yield"] is not None and not a["parcial"]]
    return {
        "ticker": ativo.ticker, "fontes": codigos, "pagamentos": pagamentos, "anos": anuais,
        "dy_medio": sum(yields) / len(yields) if yields else None,
        "dy_minimo": min(yields) if yields else None, "dy_maximo": max(yields) if yields else None,
        "criterio": (CRITERIO_EUA if ativo.mercado == "US" else
                     "Valores líquidos (JCP com 15% de IR), somados pela data de pagamento (ou data-ex quando a fonte "
                     "não informa o pagamento).") + " DY do ano = total do ano ÷ último fechamento do ano. O ano "
                    "corrente é parcial.",
    }


def risco(sessao: Session, ticker: str, hoje: date | None = None) -> dict | None:
    ativo = _ativo(sessao, ticker)
    if ativo is None:
        return None
    hoje = hoje or date.today()
    inicio = hoje - timedelta(days=365)
    precos = [f for d, f in _cotacoes(sessao, ativo.id) if d > inicio]
    vol = portfolio.volatilidade_anualizada(precos)
    retorno = precos[-1] / precos[0] - 1 if len(precos) >= 21 else None
    cdi = portfolio.taxa_acumulada([float(v) for v in sessao.scalars(
        select(SerieEconomica.valor).where(SerieEconomica.codigo == "CDI", SerieEconomica.data > inicio,
                                           SerieEconomica.data <= hoje))])
    if vol.disponivel and cdi.disponivel:
        sharpe = portfolio.sharpe(retorno, vol.valor, cdi.valor)
    else:
        sharpe = vol if not vol.disponivel else cdi
    return {
        "ticker": ativo.ticker, "retorno_12m": retorno,
        "volatilidade_12m": {"valor": vol.valor, "motivo_indisponivel": vol.motivo_indisponivel,
                             "metrica": "portfolio.volatilidade"},
        "cdi_12m": cdi.valor,
        "sharpe_12m": {"valor": sharpe.valor, "motivo_indisponivel": sharpe.motivo_indisponivel,
                       "metrica": "portfolio.sharpe"},
        "fontes": ["cotações diárias", "BCB_SGS (CDI)"],
    }
