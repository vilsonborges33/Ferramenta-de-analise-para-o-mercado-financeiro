"""Ranking "Mais baratas": ordena as ações pelo desconto em relação ao valor justo de cada livro.

Usa os indicadores materializados (LPA, VPA, DY, CAGR do lucro, EY, ROC, liquidez) e recalcula os
métodos com os parâmetros escolhidos pelo usuário, sem gravar nada.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.modelos import Ativo, CotacaoDiaria, IndicadorCalculado
from app.metodologias import bazin, graham, lynch
from app.metodologias import greenblatt as gb

AVISO_NAO_RECOMENDACAO = ("Resultados calculados a partir de dados públicos e dos parâmetros escolhidos. "
                          "Não constituem recomendação de investimento.")
METODOS = ("greenblatt", "graham", "bazin", "lynch")
METRICAS_USADAS = ("basico.lpa", "basico.vpa", "basico.dy", "basico.p_l", "basico.cagr_lucro_5a",
                   "basico.liquidez_diaria", "greenblatt.earnings_yield", "greenblatt.retorno_capital")


@dataclass(frozen=True)
class Parametros:
    liquidez_minima: float = 1_000_000.0
    yield_bazin: float = bazin.YIELD_MINIMO
    fator_graham: float = graham.FATOR_GRAHAM
    fator_lynch: float = 1.0
    excluir_financeiras: bool = True
    excluir_utilities: bool = True
    limite: int = 100


def _ultimas_cotacoes(sessao: Session) -> dict[int, tuple[float, str]]:
    consulta = (select(CotacaoDiaria.ativo_id, CotacaoDiaria.fechamento, CotacaoDiaria.data)
                .distinct(CotacaoDiaria.ativo_id)
                .order_by(CotacaoDiaria.ativo_id, CotacaoDiaria.data.desc()))
    return {a: (float(f), d.isoformat()) for a, f, d in sessao.execute(consulta)}


def _universo(sessao: Session) -> list[dict]:
    ativos = list(sessao.scalars(select(Ativo).where(Ativo.classe == "ACAO", Ativo.ativo.is_(True))))
    valores: dict[int, dict[str, tuple[float | None, list]]] = {}
    motivos_dy: dict[int, str | None] = {}
    consulta = select(IndicadorCalculado.ativo_id, IndicadorCalculado.metrica, IndicadorCalculado.valor,
                      IndicadorCalculado.insumos, IndicadorCalculado.motivo_indisponivel).where(
        IndicadorCalculado.metrica.in_(METRICAS_USADAS))
    for ativo_id, metrica, valor, insumos, motivo in sessao.execute(consulta):
        valores.setdefault(ativo_id, {})[metrica] = (None if valor is None else float(valor), insumos)
        if metrica == "basico.dy":
            motivos_dy[ativo_id] = motivo
    cotacoes = _ultimas_cotacoes(sessao)
    universo = []
    for a in ativos:
        v = valores.get(a.id, {})
        preco, data = cotacoes.get(a.id, (None, None))
        universo.append({
            "ticker": a.ticker, "nome": a.empresa.nome if a.empresa else None,
            "setor": a.empresa.setor if a.empresa else None,
            "tipo_plano_contas": a.empresa.tipo_plano_contas if a.empresa else "geral",
            "preco": preco, "data_preco": data,
            **{m: v.get(m, (None, []))[0] for m in METRICAS_USADAS},
            "_insumos_cagr": v.get("basico.cagr_lucro_5a", (None, []))[1],
            "_motivo_dy": motivos_dy.get(a.id),
        })
    return universo


def _item(u: dict, valor_justo: float | None, desconto: float | None, **extras) -> dict:
    return {"ticker": u["ticker"], "nome": u["nome"], "setor": u["setor"], "preco": u["preco"],
            "data_preco": u["data_preco"], "liquidez_diaria": u["basico.liquidez_diaria"],
            "valor_justo": valor_justo, "desconto": desconto, **extras}


def ranking_acoes(sessao: Session, metodo: str, p: Parametros = Parametros()) -> dict:
    if metodo not in METODOS:
        raise ValueError(f"método desconhecido: {metodo}")
    universo = _universo(sessao)
    motivos: dict[str, int] = {}

    def excluir(motivo: str) -> None:
        motivos[motivo] = motivos.get(motivo, 0) + 1

    elegiveis = []
    for u in universo:
        if u["preco"] is None:
            excluir("sem cotação")
        elif p.liquidez_minima and (u["basico.liquidez_diaria"] or 0) < p.liquidez_minima:
            excluir("liquidez abaixo do mínimo")
        else:
            elegiveis.append(u)

    itens: list[dict] = []
    if metodo == "greenblatt":
        candidatos = [gb.Candidato(u["ticker"], u["greenblatt.earnings_yield"], u["greenblatt.retorno_capital"],
                                   u["tipo_plano_contas"], u["setor"], u["basico.liquidez_diaria"])
                      for u in elegiveis]
        resultado = gb.ranking(candidatos, gb.ParametrosGreenblatt(
            excluir_financeiras=p.excluir_financeiras, excluir_utilities=p.excluir_utilities))
        por_ticker = {u["ticker"]: u for u in elegiveis}
        for pos in resultado.ranking:
            u = por_ticker[pos.ticker]
            itens.append(_item(u, None, None, posicao=pos.posicao, soma_posicoes=pos.soma,
                               earnings_yield=u["greenblatt.earnings_yield"],
                               retorno_capital=u["greenblatt.retorno_capital"],
                               posicao_ey=pos.posicao_ey, posicao_roc=pos.posicao_roc))
        for motivo in resultado.excluidos.values():
            excluir(motivo)
    else:
        for u in elegiveis:
            extras: dict = {}
            if metodo == "graham":
                justo = graham.valor_intrinseco(u["basico.lpa"], u["basico.vpa"], p.fator_graham)
            elif metodo == "bazin":
                dy = u["basico.dy"]
                if dy is None:
                    excluir((u["_motivo_dy"] or "dividend yield indisponível").split(":")[0])
                    continue
                dividendo = dy * u["preco"]
                justo = bazin.preco_teto(dividendo, p.yield_bazin)
                extras["dividend_yield"] = dy
            else:
                insumos = u["_insumos_cagr"] or []
                base_lucro = insumos[0].get("valor") if insumos else None
                atual_lucro = insumos[-1].get("valor") if insumos else None
                justo = lynch.preco_justo(u["basico.lpa"], u["basico.cagr_lucro_5a"], base_lucro, atual_lucro,
                                          fator=p.fator_lynch)
                extras.update(crescimento_lucro=u["basico.cagr_lucro_5a"],
                              peg=lynch.peg(u["basico.p_l"], u["basico.cagr_lucro_5a"]).valor,
                              aviso=justo.detalhes.get("aviso"))
            if not justo.disponivel:
                excluir(justo.motivo_indisponivel.split(":")[0])
                continue
            margem = graham.margem_seguranca(justo.valor, u["preco"])
            itens.append(_item(u, justo.valor, margem.valor, **extras))
        itens.sort(key=lambda i: (-(i["desconto"] if i["desconto"] is not None else -1e9), i["ticker"]))
        for i, item in enumerate(itens, start=1):
            item["posicao"] = i

    return {
        "metodo": metodo,
        "parametros": p.__dict__,
        "aviso": AVISO_NAO_RECOMENDACAO,
        "total_avaliados": len(universo),
        "total_no_ranking": len(itens),
        "excluidos": dict(sorted(motivos.items(), key=lambda kv: -kv[1])),
        "itens": itens[: p.limite],
    }
