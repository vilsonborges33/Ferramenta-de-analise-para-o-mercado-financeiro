"""Retorno de longo prazo à la Siegel: quanto R$ 100 viraram, em termos nominais e reais (descontado o IPCA),
em ações/FIIs com dividendos reinvestidos, no CDI e no dólar; e o CAPE de cada empresa.

- Retorno total: I_t = I_{t−1} × (P_t + D_t) ÷ P_{t−1}, D_t = proventos com data-ex no dia (siegel.retorno_total).
  Os fechamentos do Yahoo já vêm ajustados por desdobramentos e grupamentos.
- Real: índice nominal ÷ índice do IPCA (Fisher, siegel.retorno_real). O IPCA sai com ~40 dias de atraso,
  então a série real termina no último mês com IPCA publicado.
- CAPE da empresa: valor de mercado ÷ média do lucro anual real dos últimos N anos (equivale a preço ÷ LPA real
  médio sem depender de mudanças na quantidade de ações).
"""

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.modelos import Ativo, DemonstracaoPadronizada, IndicadorCalculado, SerieEconomica
from app.metodologias import siegel
from app.servicos.historico import serie_retorno_total

LIMITE_ATIVOS = 4


def _mes(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def _fim_de_mes(pontos: list[tuple[date, float]]) -> dict[str, float]:
    """Último valor de cada mês."""
    saida: dict[str, float] = {}
    for d, v in pontos:
        saida[_mes(d)] = v
    return saida


def _indice_diario(taxas: list[tuple[date, float]]) -> list[tuple[date, float]]:
    nivel, saida = 1.0, []
    for d, t in taxas:
        nivel *= 1 + t / 100
        saida.append((d, nivel))
    return saida


def _serie(sessao: Session, codigo: str, desde: date) -> list[tuple[date, float]]:
    return [(d, float(v)) for d, v in sessao.execute(
        select(SerieEconomica.data, SerieEconomica.valor)
        .where(SerieEconomica.codigo == codigo, SerieEconomica.data >= desde).order_by(SerieEconomica.data))]


def _ipca_mensal(sessao: Session, desde: date) -> dict[str, float]:
    """Índice do IPCA no fim de cada mês (o ponto do SGS é datado no 1º dia do mês de referência)."""
    nivel, saida = 1.0, {}
    for d, v in _serie(sessao, "IPCA", date(desde.year, desde.month, 1)):
        nivel *= 1 + v / 100
        saida[_mes(d)] = nivel
    return saida


def _cape(sessao: Session, ativo: Ativo, ipca: dict[str, float], anos: int) -> dict:
    if ativo.empresa_id is None or ativo.classe == "FII":
        return {"valor": None, "motivo_indisponivel": "CAPE só se aplica a ações (lucro da empresa)"}
    vm = sessao.scalar(select(IndicadorCalculado.valor).where(IndicadorCalculado.ativo_id == ativo.id,
                                                              IndicadorCalculado.metrica == "basico.valor_mercado"))
    periodos = list(sessao.scalars(select(DemonstracaoPadronizada).where(
        DemonstracaoPadronizada.empresa_id == ativo.empresa_id, DemonstracaoPadronizada.tipo_periodo == "ano")
        .order_by(DemonstracaoPadronizada.data_fim.desc()).limit(anos)))
    if not ipca:
        return {"valor": None, "motivo_indisponivel": "IPCA indisponível"}
    atual = ipca[max(ipca)]
    lucros, usados = [], []
    for p in reversed(periodos):
        lucro = p.campos.get("lucro_liquido_controladores", p.campos.get("lucro_liquido"))
        idx = ipca.get(_mes(p.data_fim))
        if lucro is None or idx is None:
            lucros.append(None)
            continue
        real = siegel.lpa_real([lucro, 0.0], [idx, atual])[0]  # lucro em reais de hoje
        lucros.append(real)
        usados.append({"ano": p.data_fim.year, "lucro_nominal": lucro, "lucro_real": real})
    r = siegel.cape(None if vm is None else float(vm), lucros, anos)
    return {"valor": r.valor, "motivo_indisponivel": r.motivo_indisponivel, "anos": anos, "lucros": usados,
            "valor_mercado": None if vm is None else float(vm), "lucro_real_medio": r.detalhes.get("lpa_medio")}


def longo_prazo(sessao: Session, tickers: list[str], desde: date, anos_cape: int = 10) -> dict:
    ipca = _ipca_mensal(sessao, desde)
    candidatos: list[tuple[str, str, dict[str, float], str]] = []
    capes = {}
    classes: dict[str, str] = {}
    for t in tickers[:LIMITE_ATIVOS]:
        ativo = sessao.scalar(select(Ativo).where(Ativo.ticker == t.upper()))
        if ativo is None or ativo.mercado != "B3":
            continue
        classes[ativo.ticker] = ativo.classe
        diario = serie_retorno_total(sessao, ativo, desde)
        if diario:
            candidatos.append((ativo.ticker, "ativo", _fim_de_mes(diario), "Yahoo Finance (cotações e proventos)"))
        capes[ativo.ticker] = _cape(sessao, ativo, ipca, anos_cape)
    cdi = _fim_de_mes(_indice_diario(_serie(sessao, "CDI", desde)))
    if cdi:
        candidatos.append(("CDI", "indice", cdi, "Banco Central (SGS 12)"))
    dolar = _fim_de_mes(_serie(sessao, "DOLAR_VENDA", desde))
    if dolar:
        candidatos.append(("Dólar", "indice", dolar, "Banco Central (SGS 1)"))
    if ipca:
        candidatos.append(("IPCA", "inflacao", ipca, "Banco Central (SGS 433)"))
    if not candidatos:
        return {"meses": [], "series": [], "capes": capes, "motivo": "sem dados no período"}

    # Janela comum: do primeiro mês em que todas as séries existem até o último mês com dado.
    inicio = max(min(s) for _, _, s, _ in candidatos)
    meses = sorted({m for _, _, s, _ in candidatos for m in s if m >= inicio})
    base_ipca = ipca.get(inicio)
    series = []
    for nome, tipo, valores, fonte in candidatos:
        base = valores.get(inicio)
        if not base:
            continue
        nominal, real, ultimo = [], [], None
        for m in meses:
            v = valores.get(m, ultimo)
            ultimo = v
            n = None if v is None else 100 * v / base
            nominal.append(n)
            idx = ipca.get(m)
            real.append(None if n is None or idx is None or not base_ipca else n / (idx / base_ipca))
        ult_real = next((x for x in reversed(real) if x is not None), None)
        meses_real = sum(1 for x in real if x is not None) - 1
        acum_nominal = nominal[-1] / 100 - 1 if nominal[-1] else None
        acum_real = ult_real / 100 - 1 if ult_real else None
        anual_real = ((1 + acum_real) ** (12 / meses_real) - 1) if acum_real is not None and meses_real >= 12 else None
        series.append({"nome": nome, "tipo": tipo, "classe": classes.get(nome), "fonte": fonte,
                       "nominal": nominal, "real": real,
                       "acumulado_nominal": acum_nominal, "acumulado_real": acum_real, "real_anualizado": anual_real})
    ultimo_ipca = max(ipca) if ipca else None
    return {"meses": meses, "inicio": inicio, "ultimo_ipca": ultimo_ipca, "series": series, "capes": capes,
            "observacao": "R$ 100 investidos no início; proventos reinvestidos na data-ex; "
                          + (f"valores reais em reais de {ultimo_ipca} (IPCA)." if ultimo_ipca
                             else "IPCA ainda não carregado: só a série nominal está disponível.")}
