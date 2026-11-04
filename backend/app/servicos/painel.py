"""Painel da página inicial: indicadores de mercado (BCB, Tesouro) e maiores variações do último pregão.

Só reúne dados já gravados; nenhum número é estimado. Cada item leva a fonte e a data de referência.
"""

from datetime import timedelta

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.db.modelos import SerieEconomica, TituloTesouroTaxa

LIQUIDEZ_MINIMA = {"ACAO": 5_000_000, "UNIT": 5_000_000, "FII": 1_000_000}
VARIACAO_MAXIMA = 0.5  # acima disso, quase sempre é desdobramento/grupamento sem ajuste, não variação real


def _ultimo(sessao: Session, codigo: str):
    return sessao.scalars(select(SerieEconomica).where(SerieEconomica.codigo == codigo)
                          .order_by(SerieEconomica.data.desc()).limit(2)).all()


def _acumulado(sessao: Session, codigo: str, dias: int | None = None, pontos: int | None = None):
    """(1 + v1/100) × (1 + v2/100) × … − 1 sobre a janela; devolve (valor, data final)."""
    consulta = select(SerieEconomica).where(SerieEconomica.codigo == codigo).order_by(SerieEconomica.data.desc())
    if dias is not None:
        fim = sessao.scalar(select(func.max(SerieEconomica.data)).where(SerieEconomica.codigo == codigo))
        if fim is None:
            return None, None
        consulta = consulta.where(SerieEconomica.data > fim - timedelta(days=dias))
    if pontos is not None:
        consulta = consulta.limit(pontos)
    linhas = sessao.scalars(consulta).all()
    if not linhas or (pontos is not None and len(linhas) < pontos):
        return None, None
    fator = 1.0
    for s in linhas:
        fator *= 1 + float(s.valor) / 100
    return fator - 1, linhas[0].data


def macro(sessao: Session) -> list[dict]:
    itens: list[dict] = []
    selic = _ultimo(sessao, "SELIC_META")
    if selic:
        itens.append({"id": "selic", "rotulo": "Selic meta", "valor": float(selic[0].valor) / 100, "unidade": "% a.a.",
                      "data": selic[0].data.isoformat(), "fonte": "Banco Central (SGS 432)",
                      "variacao": (float(selic[0].valor) - float(selic[1].valor)) / 100 if len(selic) > 1 else None})
    cdi, data_cdi = _acumulado(sessao, "CDI", dias=365)
    if cdi is not None:
        itens.append({"id": "cdi", "rotulo": "CDI 12 meses", "valor": cdi, "unidade": "%", "data": data_cdi.isoformat(),
                      "fonte": "Banco Central (SGS 12)", "variacao": None})
    ipca, data_ipca = _acumulado(sessao, "IPCA", pontos=12)
    if ipca is not None:
        itens.append({"id": "ipca", "rotulo": "IPCA 12 meses", "valor": ipca, "unidade": "%",
                      "data": data_ipca.isoformat(), "fonte": "Banco Central (SGS 433)", "variacao": None})
    dolar = _ultimo(sessao, "DOLAR_VENDA")
    if dolar:
        ant = float(dolar[1].valor) if len(dolar) > 1 else None
        itens.append({"id": "dolar", "rotulo": "Dólar (PTAX venda)", "valor": float(dolar[0].valor), "unidade": "R$",
                      "data": dolar[0].data.isoformat(), "fonte": "Banco Central (SGS 1)",
                      "variacao": float(dolar[0].valor) / ant - 1 if ant else None})
    data_base = sessao.scalar(select(func.max(TituloTesouroTaxa.data_base)))
    if data_base is not None:
        for nome, rotulo in (("Tesouro IPCA+", "Tesouro IPCA+ (mais longo)"),
                             ("Tesouro Prefixado", "Tesouro Prefixado (mais longo)")):
            t = sessao.scalar(select(TituloTesouroTaxa)
                              .where(TituloTesouroTaxa.data_base == data_base, TituloTesouroTaxa.titulo == nome,
                                     TituloTesouroTaxa.taxa_compra.is_not(None))
                              .order_by(TituloTesouroTaxa.vencimento.desc()).limit(1))
            if t is not None:
                itens.append({"id": nome, "rotulo": rotulo, "valor": float(t.taxa_compra) / 100,
                              "unidade": "% a.a." + (" + IPCA" if "IPCA" in nome else ""),
                              "data": data_base.isoformat(), "fonte": f"Tesouro Transparente — venc. {t.vencimento:%Y}",
                              "variacao": None})
    return itens


_SQL_VARIACOES = text("""
with ultimo as (
  select max(c.data) as d from cotacao_diaria c join ativo a on a.id = c.ativo_id where a.mercado = 'B3'
), janela as (
  select a.ticker, a.classe, c.data, c.fechamento,
         lag(c.fechamento) over (partition by c.ativo_id order by c.data) as anterior, c.ativo_id
  from cotacao_diaria c join ativo a on a.id = c.ativo_id
  where a.mercado = 'B3' and a.ativo and a.classe in ('ACAO', 'UNIT', 'FII')
    and c.data >= (select d from ultimo) - 10
)
select j.ticker, j.classe, j.fechamento, j.anterior, j.data, i.valor as liquidez
from janela j join indicador_calculado i on i.ativo_id = j.ativo_id and i.metrica = 'basico.liquidez_diaria'
where j.data = (select d from ultimo) and j.anterior > 0 and i.valor is not null
""")


def variacoes(sessao: Session, quantos: int = 6) -> dict:
    linhas = sessao.execute(_SQL_VARIACOES).all()
    por_grupo: dict[str, list[dict]] = {"acoes": [], "fiis": []}
    data = None
    for ticker, classe, fech, ant, d, liq in linhas:
        if float(liq) < LIQUIDEZ_MINIMA.get(classe, 0):
            continue
        v = float(fech) / float(ant) - 1
        if abs(v) > VARIACAO_MAXIMA:
            continue
        data = d
        por_grupo["fiis" if classe == "FII" else "acoes"].append(
            {"ticker": ticker, "classe": classe, "fechamento": float(fech), "variacao": v})
    saida: dict = {"data": data.isoformat() if data else None, "fonte": "Yahoo Finance (fechamento)"}
    for grupo, itens in por_grupo.items():
        itens.sort(key=lambda x: x["variacao"])
        saida[grupo] = {"altas": list(reversed(itens[-quantos:])), "baixas": itens[:quantos],
                        "positivas": sum(1 for x in itens if x["variacao"] > 0),
                        "negativas": sum(1 for x in itens if x["variacao"] < 0), "total": len(itens)}
    return saida


def montar(sessao: Session) -> dict:
    return {"macro": macro(sessao), "variacoes": variacoes(sessao)}
