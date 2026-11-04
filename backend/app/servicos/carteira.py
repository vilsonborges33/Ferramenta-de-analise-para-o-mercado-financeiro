"""Carteira (Fase 6): posições, rentabilidade contra índices, proventos recebidos e otimizador.

Insumos: lançamentos do usuário, cotações e proventos já gravados, CDI e IPCA (Banco Central) e os índices
Ibovespa e IFIX (Yahoo Finance). As contas ficam em `app.metodologias.carteira`, `portfolio` e `dalio`.
"""

from bisect import bisect_right
from collections import defaultdict
from datetime import date, timedelta

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.modelos import (
    Ativo,
    Carteira,
    CotacaoDiaria,
    Fii,
    Fonte,
    Lancamento,
    PrecoMedioAjuste,
    Provento,
    SerieEconomica,
)
from app.metodologias import carteira as mc
from app.metodologias import dalio, portfolio
from app.metodologias import indicadores_basicos as ib
from app.metodologias.registro import POR_ID
from app.servicos.historico import _codigos_fonte_proventos
from app.servicos.ranking import AVISO_NAO_RECOMENDACAO

AVISO_OTIMIZADOR = ("Pesos calculados com retornos e covariâncias históricas, que não se repetem necessariamente. "
                    "Ferramenta de estudo; não constitui recomendação de investimento.")


def _lancamentos(sessao: Session, carteira_id: int) -> list[tuple[Lancamento, str, str]]:
    return list(sessao.execute(select(Lancamento, Ativo.ticker, Ativo.classe)
                               .join(Ativo, Ativo.id == Lancamento.ativo_id)
                               .where(Lancamento.carteira_id == carteira_id)
                               .order_by(Lancamento.data, Lancamento.id)))


def movimentos(sessao: Session, carteira_id: int) -> list[mc.Movimento]:
    return [mc.Movimento(lan.data, ticker, lan.tipo, float(lan.quantidade), float(lan.preco or 0),
                         float(lan.taxas or 0)) for lan, ticker, _ in _lancamentos(sessao, carteira_id)]


def _ativos(sessao: Session, tickers: list[str]) -> dict[str, Ativo]:
    return {a.ticker: a for a in sessao.scalars(select(Ativo).where(Ativo.ticker.in_(tickers)))}


def _cotacoes(sessao: Session, ativo_ids: list[int], desde: date | None = None) -> dict[int, list[tuple[date, float]]]:
    consulta = select(CotacaoDiaria.ativo_id, CotacaoDiaria.data, CotacaoDiaria.fechamento).where(
        CotacaoDiaria.ativo_id.in_(ativo_ids)).order_by(CotacaoDiaria.data)
    if desde:
        consulta = consulta.where(CotacaoDiaria.data >= desde)
    saida: dict[int, list[tuple[date, float]]] = defaultdict(list)
    for a, d, f in sessao.execute(consulta):
        saida[a].append((d, float(f)))
    return saida


def _ultimas(sessao: Session, ativo_ids: list[int]) -> dict[int, list[tuple[date, float]]]:
    """Último fechamento de cada ativo (no formato de `_cotacoes`, com um ponto só)."""
    linhas = sessao.execute(select(CotacaoDiaria.ativo_id, CotacaoDiaria.data, CotacaoDiaria.fechamento)
                            .where(CotacaoDiaria.ativo_id.in_(ativo_ids)).distinct(CotacaoDiaria.ativo_id)
                            .order_by(CotacaoDiaria.ativo_id, CotacaoDiaria.data.desc()))
    return {a: [(d, float(f))] for a, d, f in linhas}


def _preco_em(serie: list[tuple[date, float]], dia: date) -> float | None:
    i = bisect_right([d for d, _ in serie], dia)
    return serie[i - 1][1] if i else None


def _proventos(sessao: Session, ativos: dict[str, Ativo]) -> dict[str, list[tuple[date, date, float, str]]]:
    """Por ticker: (data-com, data do crédito, valor líquido por cota, tipo), só da fonte configurada."""
    aliquota = POR_ID["basico.dy"].parametros[0].padrao
    saida: dict[str, list] = defaultdict(list)
    for ticker, ativo in ativos.items():
        codigos = _codigos_fonte_proventos(ativo.classe)
        ids = list(sessao.scalars(select(Fonte.id).where(Fonte.codigo.in_(codigos))))
        for p in sessao.scalars(select(Provento).where(Provento.ativo_id == ativo.id, Provento.fonte_id.in_(ids))
                                .order_by(Provento.data_com)):
            liquido = ib.provento_liquido(float(p.valor_por_cota), p.tipo, aliquota).valor
            credito = p.data_pagamento or p.data_ex or p.data_com
            saida[ticker].append((p.data_com, credito, liquido, p.tipo))
    return saida


def resumo(sessao: Session, carteira: Carteira, hoje: date | None = None) -> dict:
    hoje = hoje or date.today()
    posicoes = mc.consolidar(movimentos(sessao, carteira.id))
    ativos = _ativos(sessao, list(posicoes))
    ajustes = {a: float(v) for a, v in sessao.execute(
        select(PrecoMedioAjuste.ativo_id, PrecoMedioAjuste.preco_medio_manual)
        .where(PrecoMedioAjuste.carteira_id == carteira.id))}
    cotacoes = _ultimas(sessao, [a.id for a in ativos.values()])
    provs = _proventos(sessao, ativos)
    segmentos = {f.ativo_id: f.segmento for f in sessao.scalars(
        select(Fii).where(Fii.ativo_id.in_([a.id for a in ativos.values()])))}
    linhas, total_valor, total_custo = [], 0.0, 0.0
    for ticker, p in sorted(posicoes.items()):
        ativo = ativos[ticker]
        serie = cotacoes.get(ativo.id, [])
        preco = serie[-1][1] if serie else None
        pm = ajustes.get(ativo.id, p.preco_medio)
        valor = p.quantidade * preco if preco is not None else None
        custo = p.quantidade * pm if pm is not None else 0.0
        recebidos = mc.proventos_recebidos(p, [(c, v) for c, _, v, _ in provs.get(ticker, [])])
        por_cota_12m = sum(v for c, cred, v, _ in provs.get(ticker, []) if hoje - timedelta(days=365) < cred <= hoje)
        if p.quantidade > 0:
            total_valor += valor or 0.0
            total_custo += custo
        linhas.append({
            "ticker": ticker, "classe": ativo.classe, "nome": ativo.empresa.nome if ativo.empresa else None,
            "setor": ativo.empresa.setor if ativo.empresa else segmentos.get(ativo.id),
            "quantidade": p.quantidade, "preco_medio": pm, "preco_medio_ajustado": ativo.id in ajustes,
            "preco": preco, "data_preco": serie[-1][0].isoformat() if serie else None, "valor": valor,
            "resultado_aberto": (valor - custo) if valor is not None and p.quantidade > 0 else None,
            "rentabilidade_aberta": (valor / custo - 1) if valor and custo else None,
            "resultado_realizado": p.resultado_realizado, "proventos_recebidos": sum(v for _, v in recebidos),
            "yield_on_cost": mc.yield_on_cost(por_cota_12m, pm).valor if p.quantidade > 0 else None,
        })
    abertas = [lin for lin in linhas if lin["quantidade"] > 0]
    for lin in abertas:
        lin["peso"] = (lin["valor"] or 0) / total_valor if total_valor else None
    por_classe, por_setor = defaultdict(float), defaultdict(float)
    for lin in abertas:
        por_classe["FIIs" if lin["classe"] == "FII" else "Ações"] += lin["valor"] or 0
        por_setor[lin["setor"] or "Sem setor"] += lin["valor"] or 0
    return {
        "carteira": {"id": carteira.id, "nome": carteira.nome}, "posicoes": abertas,
        "encerradas": [lin for lin in linhas if lin["quantidade"] <= 0],
        "total_valor": total_valor, "total_custo": total_custo,
        "resultado_aberto": total_valor - total_custo,
        "resultado_realizado": sum(lin["resultado_realizado"] for lin in linhas),
        "proventos_recebidos": sum(lin["proventos_recebidos"] for lin in linhas),
        "alocacao": {"ativo": mc.alocacao({lin["ticker"]: lin["valor"] or 0 for lin in abertas}),
                     "classe": mc.alocacao(dict(por_classe)), "setor": mc.alocacao(dict(por_setor))},
        "criterios": "Preço médio com taxas (método da Receita); vendas não alteram o preço médio. Proventos "
                     "líquidos pela quantidade detida na data-com. Yield on cost = proventos por cota dos últimos "
                     "12 meses ÷ preço médio.",
    }


def _serie(sessao: Session, codigo: str, inicio: date, fim: date) -> list[tuple[date, float]]:
    return [(d, float(v)) for d, v in sessao.execute(
        select(SerieEconomica.data, SerieEconomica.valor).where(
            SerieEconomica.codigo == codigo, SerieEconomica.data >= inicio, SerieEconomica.data <= fim)
        .order_by(SerieEconomica.data))]


def _benchmarks(sessao: Session, dias: list[date]) -> dict[str, list[float | None]]:
    """Retorno acumulado de cada índice em cada dia da carteira (None quando a série não cobre o dia)."""
    inicio, fim = dias[0], dias[-1]
    saida: dict[str, list[float | None]] = {}
    cdi = dict(_serie(sessao, "CDI", inicio, fim))
    if cdi:
        acc, serie = 1.0, []
        for d in dias:
            if d != inicio and d in cdi:
                acc *= 1 + cdi[d] / 100
            serie.append(acc - 1)
        saida["CDI"] = serie
    ipca = _serie(sessao, "IPCA", date(inicio.year, inicio.month, 1) - timedelta(days=31), fim)
    if ipca:
        mensal = {(d.year, d.month): v for d, v in ipca}
        serie, acc, mes_atual = [], 1.0, (inicio.year, inicio.month)
        for d in dias:  # IPCA do mês entra quando o mês termina (série mensal)
            if (d.year, d.month) != mes_atual:
                acc *= 1 + mensal.get(mes_atual, 0.0) / 100
                mes_atual = (d.year, d.month)
            serie.append(acc - 1)
        saida["IPCA"] = serie
    for codigo in ("IBOV", "IFIX"):
        pontos = _serie(sessao, codigo, inicio - timedelta(days=10), fim)
        base = _preco_em(pontos, inicio)
        if pontos and base:
            saida[codigo] = [(v / base - 1) if (v := _preco_em(pontos, d)) else None for d in dias]
    return saida


def rentabilidade(sessao: Session, carteira: Carteira, hoje: date | None = None) -> dict:
    hoje = hoje or date.today()
    movs = movimentos(sessao, carteira.id)
    if not movs:
        return {"dias": [], "carteira": [], "indices": {}, "periodos": {}, "motivo": "carteira sem lançamentos"}
    posicoes = mc.consolidar(movs)
    ativos = _ativos(sessao, list(posicoes))
    inicio = min(m.data for m in movs)
    cotacoes = _cotacoes(sessao, [a.id for a in ativos.values()], inicio - timedelta(days=10))
    dias = sorted({d for serie in cotacoes.values() for d, _ in serie if inicio <= d <= hoje})
    if len(dias) < 2:
        return {"dias": [], "carteira": [], "indices": {}, "periodos": {}, "motivo": "menos de 2 pregões com cotação"}
    aportes_dia: dict[date, float] = defaultdict(float)
    for m in movs:
        dia = dias[min(bisect_right(dias, m.data - timedelta(days=1)), len(dias) - 1)]  # pregão do lançamento
        if m.tipo == "COMPRA":
            aportes_dia[dia] += m.quantidade * m.preco + m.taxas
        elif m.tipo == "VENDA":
            aportes_dia[dia] -= m.quantidade * m.preco - m.taxas
    proventos_dia: dict[date, float] = defaultdict(float)
    for ticker, lista in _proventos(sessao, ativos).items():
        for data_com, credito, valor, _ in lista:
            q = mc.quantidade_em(posicoes[ticker], data_com)
            if q > 0 and inicio <= credito <= hoje:
                dia = dias[min(bisect_right(dias, credito - timedelta(days=1)), len(dias) - 1)]
                proventos_dia[dia] += q * valor
    valores = []
    for d in dias:
        total = 0.0
        for ticker, p in posicoes.items():
            q = mc.quantidade_em(p, d)
            if q > 0:
                preco = _preco_em(cotacoes.get(ativos[ticker].id, []), d)
                total += q * (preco or 0.0)
        valores.append(total)
    r = mc.rentabilidade_cotas(valores, [aportes_dia[d] for d in dias], [proventos_dia[d] for d in dias])
    acumulado = r.detalhes.get("acumulado", [])
    indices = _benchmarks(sessao, dias)

    def periodo(dias_atras: int | None) -> dict[str, float | None]:
        i0 = 0 if dias_atras is None else bisect_right(dias, dias[-1] - timedelta(days=dias_atras))
        i0 = min(max(i0 - 1, 0), len(dias) - 1)

        def ret(serie):
            a, b = serie[i0], serie[-1]
            return None if a is None or b is None else (1 + b) / (1 + a) - 1
        return {"carteira": ret(acumulado), **{k: ret(v) for k, v in indices.items()}}

    return {
        "dias": [d.isoformat() for d in dias], "carteira": acumulado, "valor": valores, "indices": indices,
        "periodos": {"1 mês": periodo(31), "12 meses": periodo(365), "No ano": periodo((dias[-1] - date(
            dias[-1].year, 1, 1)).days + 1), "Desde o início": periodo(None)},
        "criterio": "Método das cotas: o retorno de cada dia desconta aportes e resgates e soma os proventos "
                    "creditados. Índices: CDI e IPCA (Banco Central), Ibovespa e IFIX (Yahoo Finance).",
    }


def proventos_recebidos(sessao: Session, carteira: Carteira) -> dict:
    posicoes = mc.consolidar(movimentos(sessao, carteira.id))
    ativos = _ativos(sessao, list(posicoes))
    itens, por_mes = [], defaultdict(float)
    for ticker, lista in _proventos(sessao, ativos).items():
        for data_com, credito, valor, tipo in lista:
            q = mc.quantidade_em(posicoes[ticker], data_com)
            if q > 0:
                itens.append({"ticker": ticker, "tipo": tipo, "data_com": data_com.isoformat(),
                              "credito": credito.isoformat(), "valor_por_cota": valor, "quantidade": q,
                              "total": q * valor})
                por_mes[credito.strftime("%Y-%m")] += q * valor
    itens.sort(key=lambda i: i["credito"], reverse=True)
    return {"itens": itens, "por_mes": dict(sorted(por_mes.items())), "total": sum(i["total"] for i in itens),
            "criterio": "Valores líquidos (JCP com 15% de IR) pela quantidade detida na data-com; crédito na data "
                        "de pagamento (ou na data-ex quando a fonte não informa o pagamento)."}


def otimizador(sessao: Session, carteira: Carteira, anos: int = 2, hoje: date | None = None) -> dict:
    hoje = hoje or date.today()
    abertas = {t: p for t, p in mc.consolidar(movimentos(sessao, carteira.id)).items() if p.quantidade > 0}
    base = {"aviso": AVISO_OTIMIZADOR, "ativos": sorted(abertas)}
    if len(abertas) < 2:
        return {**base, "motivo": "o otimizador precisa de ao menos 2 ativos na carteira"}
    ativos = _ativos(sessao, list(abertas))
    ultimas = _ultimas(sessao, [a.id for a in ativos.values()])
    fim = max((serie[0][0] for serie in ultimas.values()), default=hoje)  # janela termina no último pregão
    cotacoes = _cotacoes(sessao, [a.id for a in ativos.values()], fim - timedelta(days=365 * anos))
    series = {t: dict(cotacoes.get(ativos[t].id, [])) for t in abertas}
    comuns = sorted(set.intersection(*(set(s) for s in series.values())))
    if len(comuns) < 60:
        return {**base, "motivo": f"poucos pregões em comum entre os ativos ({len(comuns)}; mínimo 60)"}
    tickers = sorted(abertas)
    precos = np.array([[series[t][d] for t in tickers] for d in comuns])
    retornos = precos[1:] / precos[:-1] - 1
    medias, cov = portfolio.estatisticas(retornos)
    valores = np.array([abertas[t].quantidade * series[t][comuns[-1]] for t in tickers])
    pesos_atuais = valores / valores.sum()
    cdi = portfolio.taxa_acumulada([v for _, v in _serie(sessao, "CDI", fim - timedelta(days=365), fim)])
    rf = cdi.valor if cdi.disponivel else 0.10
    correl = dalio.matriz_correlacao(retornos)
    contrib = dalio.contribuicao_risco(pesos_atuais, cov)
    mv, ms, rp = portfolio.minima_variancia(cov), portfolio.maximo_sharpe(medias, cov, rf), dalio.paridade_risco(cov)
    fronteira = portfolio.fronteira_eficiente(medias, cov, 15)

    def carteira_de(nome: str, pesos) -> dict:
        w = np.asarray(pesos, float)
        ret, vol = portfolio.retorno_carteira(w, medias), portfolio.volatilidade_carteira(w, cov)
        return {"nome": nome, "pesos": dict(zip(tickers, w.round(6).tolist(), strict=True)), "retorno": ret,
                "volatilidade": vol, "sharpe": portfolio.sharpe(ret, vol, rf).valor}

    carteiras = [carteira_de("Atual", pesos_atuais)]
    for nome, r in (("Mínima variância", mv), ("Máximo Sharpe", ms), ("Paridade de risco", rp)):
        if r.disponivel:
            carteiras.append(carteira_de(nome, r.detalhes["pesos"]))
    return {
        **base, "tickers": tickers, "periodo": {"inicio": comuns[0].isoformat(), "fim": comuns[-1].isoformat(),
                                                "pregoes": len(comuns)},
        "taxa_livre_risco": rf, "retorno_medio": dict(zip(tickers, medias.tolist(), strict=True)),
        "volatilidade": dict(zip(tickers, np.sqrt(np.diag(cov)).tolist(), strict=True)),
        "correlacao": correl.detalhes.get("matriz"), "correlacao_media": correl.valor,
        "contribuicao_risco": dict(zip(tickers, contrib.detalhes.get("contribuicoes", []), strict=False)),
        "carteiras": carteiras,
        "fronteira": [{"retorno": p["retorno"], "volatilidade": p["volatilidade"]}
                      for p in fronteira.detalhes.get("pontos", [])],
        "numero_efetivo": portfolio.numero_efetivo_ativos(pesos_atuais).valor,
        "metodologias": ["portfolio.fronteira", "portfolio.sharpe", "dalio.correlacao", "dalio.paridade_risco"],
    }


def total_lancamentos(sessao: Session, carteira_id: int) -> int:
    return sessao.scalar(select(func.count()).select_from(Lancamento).where(Lancamento.carteira_id == carteira_id))


AVISO = AVISO_NAO_RECOMENDACAO
