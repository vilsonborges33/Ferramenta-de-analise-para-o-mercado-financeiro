"""Análises dos livros calculadas sob demanda para um ativo (ações da B3 e dos EUA).

Graham (fórmula revisada e checklist do investidor defensivo), Bazin (critérios e preço teto pela média de N
anos), Lynch (índice e categoria), Siegel (reversão à média do P/L), Bogle (decomposição do retorno esperado),
Lo & Foerster (beta e fatores) e Damodaran (custo do capital próprio com prêmio de risco país).

As fórmulas ficam em `app/metodologias`; aqui só se reúnem os insumos já gravados (demonstrações padronizadas,
indicadores calculados, cotações, proventos e séries), cada um com a fonte e a data de referência.
"""

from bisect import bisect_right
from datetime import date, timedelta
from statistics import mean

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.db.modelos import Ativo, CotacaoDiaria, DemonstracaoPadronizada, IndicadorCalculado, SerieEconomica
from app.metodologias import bazin, bogle, damodaran, graham, lynch, portfolio, siegel
from app.metodologias.tipos import Resultado, indisponivel
from app.servicos import historico
from app.servicos.ranking import AVISO_NAO_RECOMENDACAO

ANOS_MEDIA_BAZIN = 5
ANOS_REGULARIDADE_BAZIN = 5
ANOS_BOGLE = 10
DIAS_BETA = 730
ANOS_DIVIDENDOS_GRAHAM = 20
CLASSES_MERCADO = {"B3": ("ACAO", "UNIT"), "US": ("STOCK", "REIT")}


def _r(res: Resultado, **extra) -> dict:
    return {"valor": res.valor, "motivo_indisponivel": res.motivo_indisponivel, "detalhes": res.detalhes, **extra}


def _indicadores(sessao: Session, ativo_id: int) -> dict[str, float | None]:
    return {m: (None if v is None else float(v)) for m, v in sessao.execute(
        select(IndicadorCalculado.metrica, IndicadorCalculado.valor).where(IndicadorCalculado.ativo_id == ativo_id))}


def _serie(sessao: Session, codigo: str) -> tuple[float | None, str | None]:
    s = sessao.scalar(select(SerieEconomica).where(SerieEconomica.codigo == codigo)
                      .order_by(desc(SerieEconomica.data)).limit(1))
    return (float(s.valor) / 100, s.data.isoformat()) if s else (None, None)


def _tesouro_prefixado_longo(sessao: Session) -> tuple[float | None, str | None]:
    from app.servicos.fundos import taxa_base
    return taxa_base(sessao, "prefixado")


def _anuais(sessao: Session, empresa_id: int) -> list[DemonstracaoPadronizada]:
    return list(reversed(list(sessao.scalars(select(DemonstracaoPadronizada).where(
        DemonstracaoPadronizada.empresa_id == empresa_id, DemonstracaoPadronizada.tipo_periodo == "ano")
        .order_by(desc(DemonstracaoPadronizada.data_fim)).limit(15)))))


def _lucro(p: DemonstracaoPadronizada) -> float | None:
    c = p.campos
    v = c.get("lucro_liquido_controladores", c.get("lucro_liquido"))
    return None if v is None else float(v)


def _retornos_alinhados(a: list[tuple[date, float]], m: list[tuple[date, float]]) -> tuple[list[float], list[float]]:
    """Retornos diários nos dias em que os dois têm preço (o índice e o ativo podem ter feriados diferentes)."""
    mercado = dict(m)
    comuns = [(d, p, mercado[d]) for d, p in a if d in mercado]
    ra, rm = [], []
    for (_, p0, m0), (_, p1, m1) in zip(comuns, comuns[1:], strict=False):
        if p0 > 0 and m0 > 0:
            ra.append(p1 / p0 - 1)
            rm.append(m1 / m0 - 1)
    return ra, rm


def _beta(sessao: Session, ativo: Ativo, hoje: date) -> tuple[Resultado, str]:
    desde = hoje - timedelta(days=DIAS_BETA)
    serie = historico.serie_retorno_total(sessao, ativo, desde, hoje)
    if ativo.mercado == "US":
        spy = sessao.scalar(select(Ativo).where(Ativo.ticker == "SPY"))
        mercado = historico.serie_retorno_total(sessao, spy, desde, hoje) if spy else []
        nome = "SPY (S&P 500)"
    else:
        mercado = [(d, float(v)) for d, v in sessao.execute(
            select(SerieEconomica.data, SerieEconomica.valor).where(
                SerieEconomica.codigo == "IBOV", SerieEconomica.data >= desde).order_by(SerieEconomica.data))]
        nome = "Ibovespa"
    ra, rm = _retornos_alinhados(serie, mercado)
    if len(ra) < 60:
        return indisponivel(f"histórico curto contra o {nome} (menos de 60 pregões em comum)"), nome
    return portfolio.beta(ra, rm), nome


def _precos_em(sessao: Session, classes: tuple[str, ...], dia: date) -> dict[int, float]:
    """Último fechamento até `dia` de cada ativo das classes (um DISTINCT ON por ativo)."""
    consulta = (select(CotacaoDiaria.ativo_id, CotacaoDiaria.fechamento)
                .join(Ativo, Ativo.id == CotacaoDiaria.ativo_id)
                .where(Ativo.classe.in_(classes), Ativo.ativo.is_(True), CotacaoDiaria.data <= dia,
                       CotacaoDiaria.data > dia - timedelta(days=15))
                .distinct(CotacaoDiaria.ativo_id).order_by(CotacaoDiaria.ativo_id, CotacaoDiaria.data.desc()))
    return {a: float(f) for a, f in sessao.execute(consulta)}


def _fatores(sessao: Session, ativo: Ativo, hoje: date) -> dict:
    """Percentis de valor (earnings yield), tamanho (valor de mercado) e momento (12−1 meses) no mercado do ativo."""
    classes = CLASSES_MERCADO["US" if ativo.mercado == "US" else "B3"]
    valores: dict[str, dict[int, float | None]] = {"greenblatt.earnings_yield": {}, "basico.valor_mercado": {}}
    for a, m, v in sessao.execute(
            select(IndicadorCalculado.ativo_id, IndicadorCalculado.metrica, IndicadorCalculado.valor)
            .join(Ativo, Ativo.id == IndicadorCalculado.ativo_id)
            .where(Ativo.classe.in_(classes), Ativo.ativo.is_(True), IndicadorCalculado.metrica.in_(list(valores)))):
        valores[m][a] = None if v is None else float(v)
    um_mes, doze_meses = _precos_em(sessao, classes, hoje - timedelta(days=30)), \
        _precos_em(sessao, classes, hoje - timedelta(days=365))
    momento = {a: um_mes[a] / doze_meses[a] - 1 for a in um_mes if doze_meses.get(a)}
    saida = {}
    for chave, serie, texto in (("valor", valores["greenblatt.earnings_yield"], "earnings yield"),
                                ("tamanho", valores["basico.valor_mercado"], "valor de mercado"),
                                ("momento", momento, "retorno de 12−1 meses")):
        pct = portfolio.percentis({str(k): v for k, v in serie.items()})
        p = pct.get(str(ativo.id))
        saida[chave] = {"percentil": p, "valor": serie.get(ativo.id), "criterio": texto, "universo": len(pct),
                        "motivo_indisponivel": None if p is not None else f"dado indisponível: {texto}"}
    return saida


def _anos_com_dividendos(anos: list[dict]) -> int | None:
    """Anos completos seguidos com proventos, do mais recente para trás. None se o histórico disponível acabar antes
    de um ano sem proventos e for menor que o exigido por Graham (não dá para afirmar que "não atende")."""
    completos = [a for a in anos if not a["parcial"]]
    seguidos = 0
    for a in reversed(completos):
        if a["total_liquido"] <= 0:
            return seguidos
        seguidos += 1
    return seguidos if seguidos >= ANOS_DIVIDENDOS_GRAHAM else None


def analises(sessao: Session, ticker: str, hoje: date | None = None) -> dict | None:
    ativo = sessao.scalar(select(Ativo).where(Ativo.ticker == ticker.upper()))
    if ativo is None or ativo.empresa_id is None or ativo.classe not in ("ACAO", "UNIT", "STOCK", "REIT"):
        return None
    hoje = hoje or date.today()
    ind = _indicadores(sessao, ativo.id)
    eua = ativo.mercado == "US"
    lpa, vpa = ind.get("basico.lpa"), ind.get("basico.vpa")
    cot = sessao.scalar(select(CotacaoDiaria).where(CotacaoDiaria.ativo_id == ativo.id)
                        .order_by(desc(CotacaoDiaria.data)).limit(1))
    preco = float(cot.fechamento) if cot else None
    dy, p_l, p_vp = ind.get("basico.dy"), ind.get("basico.p_l"), ind.get("basico.p_vp")
    g = ind.get("basico.cagr_lucro_5a")
    anuais = _anuais(sessao, ativo.empresa_id)
    ttm = sessao.scalar(select(DemonstracaoPadronizada).where(
        DemonstracaoPadronizada.empresa_id == ativo.empresa_id, DemonstracaoPadronizada.tipo_periodo == "ttm")
        .order_by(desc(DemonstracaoPadronizada.data_fim)).limit(1))
    ttm = ttm or (anuais[-1] if anuais else None)  # sem ITR, o LPA também usa o último anual
    lucro_ttm = _lucro(ttm) if ttm else None
    # Ações do ticker (já com units, tesouraria etc. resolvidos no cálculo do LPA): lucro de 12 meses ÷ LPA.
    acoes = lucro_ttm / lpa if lucro_ttm and lpa else None
    lucros = [_lucro(p) for p in anuais]
    lpas = [None if (lc is None or not acoes) else lc / acoes for lc in lucros]
    divs = historico.dividendos(sessao, ativo.ticker, anos=ANOS_DIVIDENDOS_GRAHAM) or {"anos": []}
    totais = [a["total_liquido"] for a in divs["anos"] if not a["parcial"]]

    # Graham — fórmula revisada: Y = Selic meta (Brasil) ou Treasury de 10 anos (EUA)
    taxa_y, data_y = _serie(sessao, "UST10Y" if eua else "SELIC_META")
    revisado = graham.valor_revisado(lpa, g, taxa_y)
    ultimo = anuais[-1].campos if anuais else {}
    checklist = graham.checklist_defensivo(graham.DadosDefensivo(
        receita_anual=ultimo.get("receita_liquida"), ativo_circulante=ultimo.get("ativo_circulante"),
        passivo_circulante=ultimo.get("passivo_circulante"), divida_longo_prazo=ultimo.get("emprestimos_lp", 0.0),
        lucros_anuais=lucros, anos_com_dividendos=_anos_com_dividendos(divs["anos"]), lpa_anuais=lpas,
        preco=preco, vpa=vpa))

    # Bazin — critérios e preço teto pela média de N anos
    media = bazin.dividendo_medio_anual(totais, ANOS_MEDIA_BAZIN) if totais else indisponivel(
        "dado indisponível: proventos por ano")
    teto_medio = bazin.preco_teto(media.valor) if media.disponivel else media
    c_ttm = ttm.campos if ttm else {}
    dl = None
    if any(k in c_ttm for k in ("emprestimos_cp", "emprestimos_lp")):
        dl = (c_ttm.get("emprestimos_cp") or 0) + (c_ttm.get("emprestimos_lp") or 0) \
            - (c_ttm.get("caixa_equivalentes") or 0) - (c_ttm.get("aplicacoes_financeiras") or 0)
    pl_ctrl = c_ttm.get("patrimonio_liquido_controladores", c_ttm.get("patrimonio_liquido"))
    financeira = (ativo.empresa.tipo_plano_contas if ativo.empresa else "geral") != "geral"
    endividamento = indisponivel("não se aplica a bancos e seguradoras") if financeira \
        else bazin.endividamento_baixo(dl, pl_ctrl)
    regularidade = bazin.regularidade_proventos(totais, ANOS_REGULARIDADE_BAZIN) \
        if len(totais) >= ANOS_REGULARIDADE_BAZIN else indisponivel(
            f"menos de {ANOS_REGULARIDADE_BAZIN} anos completos de proventos")

    # Crescimento atípico (efeito de base, lucro não recorrente) contamina Graham revisado, Lynch e Bogle.
    aviso_g = lynch.crescimento_atipico(g, lucros[-6] if len(lucros) >= 6 else None, lucros[-1] if lucros else None)
    # Lynch — índice e categoria
    indice = lynch.indice_lynch(g, dy, p_l)
    categoria = lynch.classificar(g, lucros, p_vp, ativo.empresa.setor if ativo.empresa else None)

    # Siegel — P/L de cada fim de ano (preço do último pregão do ano ÷ lucro do ano por ação)
    cotacoes = historico._cotacoes(sessao, ativo.id)
    datas = [d for d, _ in cotacoes]
    pls = []
    for p, lpa_ano in zip(anuais, lpas, strict=True):
        i = bisect_right(datas, p.data_fim)
        if i and lpa_ano and lpa_ano > 0 and (p.data_fim - datas[i - 1]).days <= 15:
            pls.append(cotacoes[i - 1][1] / lpa_ano)
    reversao = siegel.desvio_da_media(p_l, pls) if p_l and p_l > 0 else indisponivel("P/L atual não positivo")
    media_pl = mean(pls) if len(pls) >= 3 else None

    # Bogle — retorno esperado = DY + crescimento do lucro + volta do P/L à média em N anos
    decomposicao = bogle.decomposicao_retorno(dy, g, p_l, media_pl, ANOS_BOGLE) if media_pl else indisponivel(
        "menos de 3 anos de P/L histórico")

    # Lo & Foerster — beta e fatores; Damodaran — custo do capital próprio
    beta, indice_mercado = _beta(sessao, ativo, hoje)
    if eua:
        rf, data_rf = _serie(sessao, "UST10Y")
        erp, data_erp = _serie(sessao, "DAMODARAN_ERP_EUA")
        crp, spread = 0.0, 0.0
        descricao_rf = f"Treasury 10 anos em {date.fromisoformat(data_rf):%d/%m/%Y}" if data_rf else None
    else:
        rf_bruta, descricao_rf = _tesouro_prefixado_longo(sessao)
        erp, data_erp = _serie(sessao, "DAMODARAN_ERP_MADURO")
        crp, _ = _serie(sessao, "DAMODARAN_CRP_BRASIL")
        spread, _ = _serie(sessao, "DAMODARAN_SPREAD_BRASIL")
        # A taxa do Tesouro já embute o risco de default do Brasil; sai para não contar duas vezes com o prêmio país.
        rf = rf_bruta - spread if rf_bruta is not None and spread is not None else None
    beta_usado = beta.valor if beta.disponivel else 1.0
    ke = damodaran.custo_capital_proprio(rf, beta_usado, erp, crp or 0.0) if erp is not None else indisponivel(
        "dado indisponível: prêmios de risco do Damodaran ainda não carregados")

    return {
        "ticker": ativo.ticker, "moeda": ativo.moeda, "preco": preco,
        "graham": {
            "valor_revisado": _r(revisado, metrica="graham.valor_revisado", crescimento=g, taxa_y=taxa_y,
                                 descricao_taxa_y=(f"{'Treasury 10 anos' if eua else 'Selic meta'} em "
                                                   f"{date.fromisoformat(data_y):%d/%m/%Y}"
                                                   if data_y else None),
                                 margem=graham.margem_seguranca(revisado.valor, preco).valor
                                 if revisado.disponivel and preco else None,
                                 aviso=aviso_g),
            "checklist": _r(checklist, metrica="graham.checklist_defensivo", anos_disponiveis=len(anuais)),
        },
        "bazin": {
            "preco_teto_media": _r(teto_medio, metrica="bazin.preco_teto", anos=ANOS_MEDIA_BAZIN,
                                   dividendo_medio=media.valor,
                                   margem=graham.margem_seguranca(teto_medio.valor, preco).valor
                                   if teto_medio.disponivel and preco else None),
            "endividamento_baixo": _r(endividamento, metrica="bazin.criterios"),
            "regularidade": _r(regularidade, metrica="bazin.criterios", anos=ANOS_REGULARIDADE_BAZIN),
        },
        "lynch": {"indice": _r(indice, metrica="lynch.indice", crescimento=g, dy=dy, p_l=p_l, aviso=aviso_g),
                  "categoria": _r(categoria, metrica="lynch.categoria")},
        "siegel": {"reversao_media": _r(reversao, metrica="siegel.reversao_media", p_l=p_l, media_historica=media_pl,
                                        anos=len(pls))},
        "bogle": {"decomposicao": _r(decomposicao, metrica="bogle.decomposicao", anos=ANOS_BOGLE,
                                     p_l_final=media_pl, aviso=aviso_g)},
        "portfolio": {"beta": _r(beta, metrica="portfolio.beta", indice=indice_mercado),
                      "fatores": _fatores(sessao, ativo, hoje)},
        "damodaran": {"custo_capital_proprio": _r(
            ke, metrica="damodaran.custo_capital_proprio", taxa_livre_risco=rf, descricao_taxa=descricao_rf,
            spread_default=None if eua else spread, beta=beta_usado, beta_estimado=beta.disponivel,
            premio_mercado=erp, premio_pais=None if eua else crp, data_premios=data_erp,
            fonte_premios="Damodaran Online (ctryprem.xlsx)")},
        "fontes": ["CVM/SEC (balanços padronizados)", "Yahoo Finance (cotações e proventos)",
                   "BCB SGS (Selic)", "Tesouro Direto / U.S. Treasury", "Damodaran Online"],
        "aviso": AVISO_NAO_RECOMENDACAO,
    }
