"""Stock screening: todas as ações com os indicadores principais e o preço justo de cada livro lado a lado.

Filtros por faixa (mín./máx.), setor, BESST e favoritos; ordenação pelo método escolhido. Os métodos são
recalculados com os parâmetros do usuário a partir dos indicadores materializados, sem gravar nada.
"""

import unicodedata
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.metodologias import bazin, graham, lynch
from app.metodologias import greenblatt as gb
from app.servicos.ranking import AVISO_NAO_RECOMENDACAO, _universo

# Filtro da API → métrica materializada. Percentuais em fração (0,06 = 6%), como no restante da API.
FAIXAS = {
    "dy": "basico.dy",
    "p_l": "basico.p_l",
    "p_vp": "basico.p_vp",
    "roe": "basico.roe",
    "margem_liquida": "basico.margem_liquida",
    "dl_ebitda": "basico.dl_ebitda",
    "liquidez": "basico.liquidez_diaria",
}
ORDENACOES = ("graham", "bazin", "lynch", "greenblatt")
# BESST (Luiz Barsi): bancos, energia elétrica, saneamento, seguros e telecomunicações — setores perenes.
PALAVRAS_BESST = ("banco", "energia eletrica", "saneamento", "segur", "telecomunica")


def _sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn")


def setor_besst(setor: str | None) -> bool:
    return bool(setor) and any(p in _sem_acento(setor) for p in PALAVRAS_BESST)


@dataclass(frozen=True)
class FiltrosScreening:
    faixas: dict[str, tuple[float | None, float | None]] = field(default_factory=dict)
    setores: tuple[str, ...] = ()
    besst: bool = False
    tickers: frozenset[str] | None = None  # favoritos; None = sem restrição
    ordenar_por: str = "graham"
    yield_bazin: float = bazin.YIELD_MINIMO
    fator_graham: float = graham.FATOR_GRAHAM
    fator_lynch: float = 1.0
    mercado: str = "B3"  # B3 (R$) ou EUA (US$, ações e REITs)


def _dentro(valor: float | None, faixa: tuple[float | None, float | None]) -> bool:
    minimo, maximo = faixa
    if minimo is None and maximo is None:
        return True
    if valor is None:
        return False
    return (minimo is None or valor >= minimo) and (maximo is None or valor <= maximo)


def _margem(justo, preco: float) -> float | None:
    return graham.margem_seguranca(justo.valor, preco).valor if justo.disponivel else None


def _linha(u: dict, f: FiltrosScreening) -> dict:
    preco = u["preco"]
    g = graham.valor_intrinseco(u["basico.lpa"], u["basico.vpa"], f.fator_graham)
    dy = u["basico.dy"]
    b = bazin.preco_teto(dy * preco if dy is not None else None, f.yield_bazin)
    insumos = u["_insumos_cagr"] or []
    lucro_base = insumos[0].get("valor") if insumos else None
    lucro_atual = insumos[-1].get("valor") if insumos else None
    lj = lynch.preco_justo(u["basico.lpa"], u["basico.cagr_lucro_5a"], lucro_base, lucro_atual, fator=f.fator_lynch)
    return {
        "ticker": u["ticker"], "nome": u["nome"], "setor": u["setor"], "classe": u.get("classe"),
        "besst": setor_besst(u["setor"]),
        "preco": preco, "data_preco": u["data_preco"],
        **{nome: u[metrica] for nome, metrica in FAIXAS.items()},
        "valor_mercado": u["basico.valor_mercado"],
        "graham_valor": g.valor, "graham_margem": _margem(g, preco),
        "bazin_teto": b.valor, "bazin_margem": _margem(b, preco),
        "lynch_valor": lj.valor, "lynch_margem": _margem(lj, preco),
        "lynch_peg": lynch.peg(u["basico.p_l"], u["basico.cagr_lucro_5a"]).valor,
        "lynch_aviso": lj.detalhes.get("aviso") if lj.disponivel else None,
        "earnings_yield": u["greenblatt.earnings_yield"], "retorno_capital": u["greenblatt.retorno_capital"],
        "greenblatt_posicao": None,
        "_tipo_plano": u["tipo_plano_contas"],
    }


def screening_acoes(sessao: Session, f: FiltrosScreening = FiltrosScreening()) -> dict:
    if f.ordenar_por not in ORDENACOES:
        raise ValueError(f"ordenação desconhecida: {f.ordenar_por}")
    universo = _universo(sessao, f.mercado)
    setores = sorted({u["setor"] for u in universo if u["setor"]})
    sem_cotacao = sum(1 for u in universo if u["preco"] is None)
    linhas = []
    for u in universo:
        if u["preco"] is None:
            continue
        if f.tickers is not None and u["ticker"] not in f.tickers:
            continue
        if f.setores and u["setor"] not in f.setores:
            continue
        if f.besst and not setor_besst(u["setor"]):
            continue
        if not all(_dentro(u[FAIXAS[nome]], faixa) for nome, faixa in f.faixas.items()):
            continue
        linhas.append(_linha(u, f))

    # Fórmula mágica dentro do conjunto filtrado (sem exclusões extras: os filtros já são do usuário).
    resultado = gb.ranking([gb.Candidato(lin["ticker"], lin["earnings_yield"], lin["retorno_capital"],
                                         lin["_tipo_plano"], lin["setor"], lin["liquidez"]) for lin in linhas],
                           gb.ParametrosGreenblatt(excluir_financeiras=False, excluir_utilities=False))
    posicoes = {p.ticker: p.posicao for p in resultado.ranking}
    for lin in linhas:
        lin["greenblatt_posicao"] = posicoes.get(lin["ticker"])
        del lin["_tipo_plano"]

    if f.ordenar_por == "greenblatt":
        chave = lambda lin: (lin["greenblatt_posicao"] is None, lin["greenblatt_posicao"] or 0, lin["ticker"])  # noqa: E731
    else:
        coluna = {"graham": "graham_margem", "bazin": "bazin_margem", "lynch": "lynch_margem"}[f.ordenar_por]
        chave = lambda lin: (lin[coluna] is None, -(lin[coluna] or 0), lin["ticker"])  # noqa: E731
    linhas.sort(key=chave)
    for i, lin in enumerate(linhas, start=1):
        lin["posicao"] = i

    return {
        "aviso": AVISO_NAO_RECOMENDACAO,
        "mercado": f.mercado, "moeda": "USD" if f.mercado == "EUA" else "BRL",
        "ordenar_por": f.ordenar_por,
        "parametros": {"yield_bazin": f.yield_bazin, "fator_graham": f.fator_graham, "fator_lynch": f.fator_lynch},
        "atualizado_em": max((lin["data_preco"] for lin in linhas), default=None),
        "total_avaliados": len(universo),
        "sem_cotacao": sem_cotacao,
        "setores": setores,
        "itens": linhas,
    }
