"""Valuation de uma ação (Fase 4): reúne os insumos do banco e calcula cada método com as premissas do usuário.

Métodos: preço teto projetivo (Bazin), Gordon e desconto de dividendos em dois estágios (Damodaran),
DCF pelo fluxo da firma (FCFF) e do acionista (FCFE) (McKinsey/Damodaran) e múltiplos do setor.
As contas ficam nas funções puras de `app.metodologias`; aqui só entram insumos, premissas e formatação.
Todo resultado traz o aviso de não recomendação, as premissas usadas e os insumos com data e fonte.
"""

from dataclasses import dataclass
from statistics import median

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.db.modelos import Ativo, CotacaoDiaria, DemonstracaoPadronizada, IndicadorCalculado, SerieEconomica
from app.metodologias import bazin, damodaran, dcf, graham
from app.metodologias import indicadores_basicos as ib
from app.metodologias.tipos import indisponivel, ok
from app.servicos.ranking import AVISO_NAO_RECOMENDACAO

METODOS = ("preco_teto_projetivo", "gordon", "ddm_dois_estagios", "dcf_fcff", "dcf_fcfe", "multiplos")
NOMES = {
    "preco_teto_projetivo": "Preço teto projetivo (Bazin)",
    "gordon": "Modelo de Gordon",
    "ddm_dois_estagios": "Dividendos em dois estágios",
    "dcf_fcff": "DCF — fluxo da firma (FCFF)",
    "dcf_fcfe": "DCF — fluxo do acionista (FCFE)",
    "multiplos": "Múltiplos do setor",
}
METRICA_REGISTRO = {
    "preco_teto_projetivo": "bazin.preco_teto_projetivo", "gordon": "damodaran.gordon",
    "ddm_dois_estagios": "damodaran.ddm_dois_estagios", "dcf_fcff": "dcf.valor", "dcf_fcfe": "dcf.valor",
    "multiplos": "damodaran.multiplos_setor",
}
PREMIO_RISCO_PADRAO = 0.05  # prêmio de risco de ações sobre a Selic (premissa editável)
SPREAD_DIVIDA_PADRAO = 0.02  # custo da dívida = Selic + spread (premissa editável)
CRESCIMENTO_PERPETUO_PADRAO = 0.04  # ≈ inflação de longo prazo (crescimento real ~0)
# Ativos em dólar (Fase 7): Treasury de 10 anos como taxa livre de risco, inflação-alvo do Fed + 0,5% real e
# alíquota federal de IR das empresas dos EUA.
POR_MOEDA = {
    "BRL": {"serie": "SELIC_META", "nome_taxa": "Selic", "crescimento": CRESCIMENTO_PERPETUO_PADRAO, "aliquota": 0.34},
    "USD": {"serie": "UST10Y", "nome_taxa": "Treasury 10 anos", "crescimento": 0.025, "aliquota": 0.21},
}


class ErroValuation(ValueError):
    pass


@dataclass
class Insumos:
    ticker: str
    nome: str | None
    setor: str | None
    preco: float | None
    data_preco: str | None
    acoes: float | None
    periodo: str | None  # período contábil (TTM ou ano) usado
    receita: float | None
    ebit: float | None
    depreciacao: float | None
    capex: float | None
    lucro: float | None
    patrimonio: float | None
    divida_bruta: float | None
    divida_liquida: float | None
    lpa: float | None
    vpa: float | None
    dividendo_12m: float | None  # por ação, líquido
    payout: float | None
    cagr_receita: float | None
    cagr_lucro: float | None
    selic: float | None  # taxa livre de risco da moeda do ativo (Selic ou Treasury 10 anos)
    data_selic: str | None
    multiplos_setor: dict[str, list[float]]
    moeda: str = "BRL"
    nome_taxa: str = "Selic"

    def como_dict(self) -> dict:
        d = dict(self.__dict__)
        d["multiplos_setor"] = {k: len(v) for k, v in self.multiplos_setor.items()}  # só a contagem de pares
        return d


def _indicadores(sessao: Session, ativo_id: int) -> dict[str, IndicadorCalculado]:
    return {i.metrica: i for i in sessao.scalars(select(IndicadorCalculado).where(
        IndicadorCalculado.ativo_id == ativo_id))}


def _valor(ind: IndicadorCalculado | None) -> float | None:
    return None if ind is None or ind.valor is None else float(ind.valor)


def _insumo(ind: IndicadorCalculado | None, nome: str) -> float | None:
    for i in (ind.insumos if ind else []):
        if i.get("insumo") == nome and i.get("valor") is not None:
            return float(i["valor"])
    return None


def carregar_insumos(sessao: Session, ticker: str) -> Insumos | None:
    ativo = sessao.scalar(select(Ativo).where(Ativo.ticker == ticker.upper()))
    if ativo is None or ativo.classe == "FII" or ativo.empresa is None:
        return None
    empresa = ativo.empresa
    inds = _indicadores(sessao, ativo.id)
    cot = sessao.scalar(select(CotacaoDiaria).where(CotacaoDiaria.ativo_id == ativo.id)
                        .order_by(desc(CotacaoDiaria.data)).limit(1))
    demo = None
    for tipo in ("ttm", "ano"):
        demo = sessao.scalar(select(DemonstracaoPadronizada).where(
            DemonstracaoPadronizada.empresa_id == empresa.id, DemonstracaoPadronizada.tipo_periodo == tipo)
            .order_by(desc(DemonstracaoPadronizada.data_fim)).limit(1))
        if demo:
            break
    c = demo.campos if demo else {}
    conf = POR_MOEDA.get(ativo.moeda, POR_MOEDA["BRL"])
    selic = sessao.scalar(select(SerieEconomica).where(SerieEconomica.codigo == conf["serie"])
                          .order_by(desc(SerieEconomica.data)).limit(1))
    preco = float(cot.fechamento) if cot else None
    dy = _valor(inds.get("basico.dy"))
    bruta = ib.divida_bruta(c.get("emprestimos_cp"), c.get("emprestimos_lp")).valor
    return Insumos(
        ticker=ativo.ticker, nome=empresa.nome, setor=empresa.setor, preco=preco,
        data_preco=cot.data.isoformat() if cot else None,
        acoes=_insumo(inds.get("basico.lpa"), "acoes_em_circulacao"),
        periodo=f"{demo.periodo} ({'12 meses' if demo.tipo_periodo == 'ttm' else 'ano'})" if demo else None,
        receita=c.get("receita_liquida"), ebit=c.get("ebit"), depreciacao=c.get("depreciacao_amortizacao"),
        capex=c.get("capex"), lucro=c.get("lucro_liquido_controladores", c.get("lucro_liquido")),
        patrimonio=c.get("patrimonio_liquido_controladores", c.get("patrimonio_liquido")),
        divida_bruta=bruta, divida_liquida=_valor(inds.get("basico.divida_liquida")),
        lpa=_valor(inds.get("basico.lpa")), vpa=_valor(inds.get("basico.vpa")),
        dividendo_12m=dy * preco if dy is not None and preco else None,
        payout=_valor(inds.get("basico.payout")),
        cagr_receita=_valor(inds.get("basico.cagr_receita_5a")), cagr_lucro=_valor(inds.get("basico.cagr_lucro_5a")),
        selic=float(selic.valor) / 100 if selic else None, data_selic=selic.data.isoformat() if selic else None,
        multiplos_setor=_multiplos_setor(sessao, empresa.setor, empresa.id, ativo.classe),
        moeda=ativo.moeda, nome_taxa=conf["nome_taxa"],
    )


def _multiplos_setor(sessao: Session, setor: str | None, empresa_id: int,
                     classe: str = "ACAO") -> dict[str, list[float]]:
    """P/L, P/VP e EV/EBITDA das outras empresas do mesmo setor da CVM (um ticker por empresa)."""
    saida: dict[str, list[float]] = {"basico.p_l": [], "basico.p_vp": [], "basico.ev_ebitda": []}
    if not setor:
        return saida
    linhas = sessao.execute(
        select(Ativo.empresa_id, IndicadorCalculado.metrica, IndicadorCalculado.valor)
        .join(IndicadorCalculado, IndicadorCalculado.ativo_id == Ativo.id)
        .where(Ativo.ativo.is_(True),
               Ativo.classe.in_(("STOCK", "REIT") if classe in ("STOCK", "REIT") else ("ACAO", "UNIT")),
               Ativo.empresa_id != empresa_id,
               Ativo.empresa.has(setor=setor), IndicadorCalculado.metrica.in_(list(saida)),
               IndicadorCalculado.valor.is_not(None)))
    vistos: set[tuple[int, str]] = set()
    for emp, metrica, valor in linhas:
        if (emp, metrica) not in vistos:
            vistos.add((emp, metrica))
            saida[metrica].append(float(valor))
    return saida


def _limitar(v: float | None, minimo: float, maximo: float, padrao: float) -> float:
    return padrao if v is None else max(minimo, min(maximo, v))


def premissas_padrao(ins: Insumos) -> dict[str, dict]:
    """Ponto de partida editável de cada método, sempre explicado em `origem`."""
    conf = POR_MOEDA.get(ins.moeda, POR_MOEDA["BRL"])
    taxa_nome, g_perp, ir = conf["nome_taxa"], conf["crescimento"], conf["aliquota"]
    selic = ins.selic if ins.selic is not None else (0.10 if ins.moeda == "BRL" else 0.04)
    ke = selic + PREMIO_RISCO_PADRAO
    cresc = _limitar(ins.cagr_receita, 0.0, 0.10, 0.03)
    receita = ins.receita or 0.0
    pct = lambda v: (v / receita) if (v is not None and receita) else 0.0  # noqa: E731
    capex_pct = abs(pct(ins.capex))  # a DFC informa o capex como saída (negativo)
    margem = _limitar(pct(ins.ebit) if ins.ebit is not None else None, -1.0, 1.0, 0.10)
    valor_mercado = ins.preco * ins.acoes if ins.preco and ins.acoes else None
    w = dcf.wacc(valor_mercado, ins.divida_bruta or 0.0, ke, selic + SPREAD_DIVIDA_PADRAO, ir)
    wacc = w.valor if w.disponivel else ke
    cresc, ke, wacc, margem = (round(x, 4) for x in (cresc, ke, wacc, margem))  # premissas legíveis (0,01 p.p.)
    return {
        "preco_teto_projetivo": {
            "lucro_projetado": ins.lucro * (1 + cresc) if ins.lucro is not None else None,
            "payout": _limitar(ins.payout, 0.0, 1.0, 0.5), "yield_minimo": bazin.YIELD_MINIMO,
            "origem": "Lucro dos últimos 12 meses × (1 + crescimento da receita em 5 anos, limitado a 0–10%); "
                      "payout atual; yield mínimo de 6% (Bazin).",
        },
        "gordon": {
            "dividendo_atual": ins.dividendo_12m, "custo_capital": ke, "crescimento": g_perp,
            "origem": f"Dividendos líquidos de 12 meses; custo do capital = {taxa_nome} ({selic:.2%}) + prêmio de "
                      f"{PREMIO_RISCO_PADRAO:.0%}; crescimento perpétuo de {g_perp:.1%}.",
        },
        "ddm_dois_estagios": {
            "dividendo_atual": ins.dividendo_12m, "custo_capital": ke, "crescimento_alto": cresc, "anos_alto": 5,
            "crescimento_estavel": g_perp,
            "origem": "Primeiro estágio de 5 anos crescendo como a receita dos últimos 5 anos (limitado a 0–10%); "
                      "depois, crescimento perpétuo.",
        },
        "dcf_fcff": {
            "receita_base": ins.receita, "crescimento_receita": [cresc] * 5, "margem_ebit": margem, "aliquota": ir,
            "da_pct_receita": round(pct(ins.depreciacao), 4), "capex_pct_receita": round(capex_pct, 4),
            "capital_giro_pct_variacao_receita": 0.10, "taxa_desconto": wacc,
            "crescimento_perpetuo": g_perp, "divida_liquida": ins.divida_liquida or 0.0,
            "origem": "Receita, margem EBIT, D&A e capex dos últimos 12 meses; 5 anos crescendo como a receita "
                      "histórica (0–10%); capital de giro = 10% do aumento da receita; desconto pelo WACC "
                      f"(Ke = {taxa_nome} + {PREMIO_RISCO_PADRAO:.0%}, Kd = {taxa_nome} + "
                      f"{SPREAD_DIVIDA_PADRAO:.0%}, IR {ir:.0%}, "
                      "pesos a valor de mercado).",
        },
        "dcf_fcfe": {
            "receita_base": ins.receita, "crescimento_receita": [cresc] * 5, "margem_ebit": margem, "aliquota": ir,
            "da_pct_receita": round(pct(ins.depreciacao), 4), "capex_pct_receita": round(capex_pct, 4),
            "capital_giro_pct_variacao_receita": 0.10, "juros_anuais": (ins.divida_bruta or 0.0) * (
                selic + SPREAD_DIVIDA_PADRAO), "nova_divida_anual": 0.0, "taxa_desconto": ke,
            "crescimento_perpetuo": g_perp,
            "origem": "Mesma projeção operacional do FCFF, menos juros após IR (dívida bruta × Kd) e mais nova "
                      "dívida (zero por padrão); desconto pelo custo do capital próprio.",
        },
        "multiplos": {
            "origem": "Mediana dos múltiplos das outras empresas do mesmo setor da CVM (P/L, P/VP e EV/EBITDA).",
        },
    }


def _fcfs(p: dict) -> list[dcf.AnoProjetado]:
    return dcf.projetar(dcf.PremissasProjecao(
        receita_base=float(p["receita_base"]), crescimento_receita=[float(g) for g in p["crescimento_receita"]],
        margem_ebit=float(p["margem_ebit"]), aliquota=float(p["aliquota"]), da_pct_receita=float(p["da_pct_receita"]),
        capex_pct_receita=float(p["capex_pct_receita"]),
        capital_giro_pct_variacao_receita=float(p["capital_giro_pct_variacao_receita"])))


def _sensibilidade(fluxos: list[float], taxa: float, g: float, divida: float, acoes: float | None) -> dict:
    taxas = [round(taxa + d, 4) for d in (-0.02, -0.01, 0.0, 0.01, 0.02)]
    crescimentos = [round(g + d, 4) for d in (-0.01, -0.005, 0.0, 0.005, 0.01)]
    return {"taxas": taxas, "crescimentos": crescimentos,
            "valores": dcf.tabela_sensibilidade(fluxos, taxas, crescimentos, divida, acoes)}


def calcular(ins: Insumos, metodo: str, premissas: dict | None = None) -> dict:
    if metodo not in METODOS:
        raise ErroValuation(f"método deve ser um de {', '.join(METODOS)}")
    p = {**premissas_padrao(ins)[metodo], **(premissas or {})}
    p.pop("origem", None)
    detalhes: dict = {}
    try:
        if metodo == "preco_teto_projetivo":
            r = bazin.preco_teto_projetivo(p["lucro_projetado"], p["payout"], ins.acoes, float(p["yield_minimo"]))
        elif metodo == "gordon":
            r = damodaran.gordon(p["dividendo_atual"], float(p["custo_capital"]), float(p["crescimento"]))
        elif metodo == "ddm_dois_estagios":
            r = damodaran.ddm_dois_estagios(p["dividendo_atual"], float(p["custo_capital"]),
                                            float(p["crescimento_alto"]), int(p["anos_alto"]),
                                            float(p["crescimento_estavel"]))
        elif metodo in ("dcf_fcff", "dcf_fcfe"):
            if not p.get("receita_base"):
                raise ErroValuation("receita indisponível: DCF não se aplica (sem DRE padronizada)")
            anos = _fcfs(p)
            if metodo == "dcf_fcff":
                fluxos = [a.fcff for a in anos]
                divida = float(p["divida_liquida"])
            else:
                fluxos = [dcf.fcfe(a.fcff, float(p["juros_anuais"]), float(p["aliquota"]),
                                   float(p["nova_divida_anual"])).valor for a in anos]
                divida = 0.0
            r = dcf.avaliar(fluxos, float(p["taxa_desconto"]), float(p["crescimento_perpetuo"]), divida, ins.acoes)
            detalhes["projecao"] = [{**a.__dict__, "fluxo": f} for a, f in zip(anos, fluxos, strict=True)]
            detalhes["sensibilidade"] = _sensibilidade(fluxos, float(p["taxa_desconto"]),
                                                       float(p["crescimento_perpetuo"]), divida, ins.acoes)
        else:
            r, detalhes["por_multiplo"] = _multiplos(ins)
    except (KeyError, TypeError) as erro:
        raise ErroValuation(f"premissa ausente ou inválida: {erro}") from erro
    detalhes.update({k: v for k, v in r.detalhes.items() if not isinstance(v, list | dict)})
    margem = graham.margem_seguranca(r.valor, ins.preco).valor if r.disponivel and ins.preco else None
    return {
        "metodo": metodo, "nome": NOMES[metodo], "metodologia": METRICA_REGISTRO[metodo],
        "valor_por_acao": r.valor, "motivo_indisponivel": r.motivo_indisponivel,
        "preco": ins.preco, "data_preco": ins.data_preco, "margem_seguranca": margem,
        "premissas": p, "detalhes": detalhes, "aviso": AVISO_NAO_RECOMENDACAO,
    }


def _multiplos(ins: Insumos):
    """Preço implícito por P/L, P/VP e EV/EBITDA; o resultado é a mediana dos disponíveis."""
    ebitda = ib.ebitda(ins.ebit, ins.depreciacao).valor
    ebitda_acao = ebitda / ins.acoes if ebitda is not None and ins.acoes else None
    dl_acao = (ins.divida_liquida or 0.0) / ins.acoes if ins.acoes else None
    por = {}
    for chave, nome, metrica in (("basico.p_l", "P/L", ins.lpa), ("basico.p_vp", "P/VP", ins.vpa),
                                 ("basico.ev_ebitda", "EV/EBITDA", ebitda_acao)):
        r = damodaran.preco_por_multiplo_setor(ins.multiplos_setor.get(chave, []), metrica)
        valor = r.valor
        if chave == "basico.ev_ebitda" and valor is not None and dl_acao is not None:
            valor -= dl_acao  # EV por ação − dívida líquida por ação = preço
        por[nome] = {"valor": valor, "mediana_setor": r.detalhes.get("mediana_setor"),
                     "pares": r.detalhes.get("pares"), "motivo_indisponivel": r.motivo_indisponivel}
    validos = sorted(v["valor"] for v in por.values() if v["valor"] is not None and v["valor"] > 0)
    if not validos:
        return indisponivel("nenhum múltiplo do setor disponível (menos de 3 pares ou métrica da empresa ≤ 0)"), por
    return ok(median(validos), metodos_usados=len(validos)), por


def comparar(ins: Insumos) -> list[dict]:
    """Todos os métodos com as premissas padrão, lado a lado."""
    saida = []
    for m in METODOS:
        try:
            r = calcular(ins, m)
        except ErroValuation as erro:
            r = {"metodo": m, "nome": NOMES[m], "metodologia": METRICA_REGISTRO[m], "valor_por_acao": None,
                 "motivo_indisponivel": str(erro), "margem_seguranca": None}
        saida.append({k: r.get(k) for k in ("metodo", "nome", "metodologia", "valor_por_acao",
                                            "motivo_indisponivel", "margem_seguranca")})
    return saida

