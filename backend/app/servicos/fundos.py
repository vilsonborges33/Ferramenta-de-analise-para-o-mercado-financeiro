"""Fundos imobiliários (Fase 5): página do fundo, Gordon ajustado, documentos do FNET e Fund Screening.

Fontes: informes mensal e trimestral da CVM (ODbL), cotações e rendimentos do Yahoo Finance, taxas do Tesouro
Direto (Tesouro Transparente) e a consulta pública de documentos do FNET (B3), usada só para listar e linkar.
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import date

import httpx
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.db.modelos import (
    Ativo,
    CotacaoDiaria,
    Fii,
    FiiImovel,
    FiiInformeMensal,
    IndicadorCalculado,
    SerieEconomica,
    TituloTesouroTaxa,
)
from app.ingestao.base import cliente_http
from app.metodologias import fii as mfii
from app.metodologias import graham
from app.servicos.ranking import AVISO_NAO_RECOMENDACAO
from app.servicos.screening import _dentro

log = logging.getLogger(__name__)

URL_FNET_LISTA = "https://fnet.bmfbovespa.com.br/fnet/publico/pesquisarGerenciadorDocumentosDados"
URL_FNET_VER = "https://fnet.bmfbovespa.com.br/fnet/publico/exibirDocumento?id={id}&cvm=true"
URL_FNET_BUSCA = "https://fnet.bmfbovespa.com.br/fnet/publico/abrirGerenciadorDocumentosCVM"
PREMIO_PADRAO = 0.02
CRESCIMENTO_PADRAO = 0.0
BASES = {"prefixado": "Tesouro Prefixado", "ipca": "Tesouro IPCA+", "selic": "Selic meta"}


def _fundo(sessao: Session, ticker: str) -> tuple[Ativo, Fii | None] | None:
    ativo = sessao.scalar(select(Ativo).where(Ativo.ticker == ticker.upper(), Ativo.classe == "FII"))
    if ativo is None:
        return None
    return ativo, sessao.scalar(select(Fii).where(Fii.ativo_id == ativo.id))


def _f(v) -> float | None:
    return None if v is None else float(v)


def _informes(sessao: Session, fii_id: int, meses: int = 24) -> list[FiiInformeMensal]:
    """Um informe por mês (a versão mais recente), do mais antigo ao mais novo."""
    linhas = list(sessao.scalars(select(FiiInformeMensal).where(FiiInformeMensal.fii_id == fii_id)
                                 .order_by(FiiInformeMensal.competencia, FiiInformeMensal.versao)))
    por_mes = {i.competencia: i for i in linhas}
    return [por_mes[c] for c in sorted(por_mes)][-meses:]


def _imoveis(sessao: Session, fii_id: int) -> list[FiiImovel]:
    ultima = sessao.scalar(select(func.max(FiiImovel.competencia)).where(FiiImovel.fii_id == fii_id))
    if ultima is None:
        return []
    return list(sessao.scalars(select(FiiImovel).where(FiiImovel.fii_id == fii_id, FiiImovel.competencia == ultima)
                               .order_by(desc(FiiImovel.percentual_receitas_fii), FiiImovel.nome)))


def _retornos_mensais(sessao: Session, ativo_id: int, meses: int = 24) -> list[dict]:
    """Retorno de cada mês pelo último fechamento do mês (sem rendimentos)."""
    fechamentos: dict[tuple[int, int], tuple[date, float]] = {}
    for d, f in sessao.execute(select(CotacaoDiaria.data, CotacaoDiaria.fechamento)
                               .where(CotacaoDiaria.ativo_id == ativo_id).order_by(CotacaoDiaria.data)):
        fechamentos[(d.year, d.month)] = (d, float(f))
    chaves = sorted(fechamentos)[-(meses + 1):]
    return [{"mes": f"{b[0]}-{b[1]:02d}", "retorno": fechamentos[b][1] / fechamentos[a][1] - 1}
            for a, b in zip(chaves, chaves[1:], strict=False)]


def detalhe_fundo(sessao: Session, ticker: str) -> dict | None:
    achado = _fundo(sessao, ticker)
    if achado is None:
        return None
    ativo, fii = achado
    if fii is None:
        return {"ticker": ativo.ticker, "ligado_ao_informe": False}
    informes = _informes(sessao, fii.id)
    ultimo = informes[-1] if informes else None
    extras = ultimo.extras if ultimo else None
    comp = mfii.composicao_ativo(extras, _f(ultimo.ativo_total) if ultimo else None)
    grupos = comp.detalhes.get("grupos", [])
    imoveis = _imoveis(sessao, fii.id)
    retornos = _retornos_mensais(sessao, ativo.id)
    estat = mfii.estatistica_retornos([r["retorno"] for r in retornos])
    return {
        "ticker": ativo.ticker, "ligado_ao_informe": True, "cnpj": fii.cnpj, "nome": fii.nome,
        "segmento": fii.segmento, "mandato": fii.mandato, "tipo_gestao": fii.tipo_gestao,
        "administrador": fii.administrador, "publico_alvo": fii.publico_alvo,
        "data_inicio": fii.data_inicio.isoformat() if fii.data_inicio else None,
        "tipo": mfii.tipo_do_fundo(grupos) if grupos else None,
        "competencia": ultimo.competencia.isoformat() if ultimo else None,
        "composicao": {"grupos": grupos, "total_classificado": comp.valor,
                       "cobertura": comp.detalhes.get("cobertura_do_ativo_total"),
                       "motivo_indisponivel": comp.motivo_indisponivel},
        "endividamento": {
            "ativo_total": _f(ultimo.ativo_total) if ultimo else None,
            "passivo_total": _f(ultimo.total_passivo) if ultimo else None,
            "alavancagem": mfii.alavancagem(_f(ultimo.total_passivo), _f(ultimo.ativo_total)).valor if ultimo else None,
            "obrigacoes": mfii.obrigacoes(extras),
        },
        "imoveis": [{"nome": i.nome, "classe": i.classe, "endereco": i.endereco, "area_m2": _f(i.area_m2),
                     "vacancia": _f(i.percentual_vacancia), "inadimplencia": _f(i.percentual_inadimplencia),
                     "receitas": _f(i.percentual_receitas_fii)} for i in imoveis],
        "competencia_imoveis": imoveis[0].competencia.isoformat() if imoveis else None,
        "historico": [{"competencia": i.competencia.isoformat(), "patrimonio_liquido": _f(i.patrimonio_liquido),
                       "vp_cota": _f(i.valor_patrimonial_cota), "cotistas": i.numero_cotistas,
                       "dy_mes": _f(i.dividend_yield_mes), "rentabilidade_patrimonial": _f(
                           i.rentabilidade_patrimonial_mes)} for i in informes],
        "retornos_mensais": retornos,
        "estatistica_retornos": {"valor": estat.valor, "motivo_indisponivel": estat.motivo_indisponivel,
                                 **estat.detalhes},
        "fontes": ["CVM — informe mensal", "CVM — informe trimestral", "cotações (Yahoo Finance)"],
    }


# ---------------------------------------------------------------- Gordon ajustado


def taxa_base(sessao: Session, base: str) -> tuple[float | None, str | None]:
    """Taxa anual (fração) e descrição: título do Tesouro de vencimento mais longo ou a Selic meta."""
    if base == "selic":
        s = sessao.scalar(select(SerieEconomica).where(SerieEconomica.codigo == "SELIC_META")
                          .order_by(desc(SerieEconomica.data)).limit(1))
        return (float(s.valor) / 100, f"Selic meta em {s.data:%d/%m/%Y}") if s else (None, None)
    titulo = BASES.get(base)
    if titulo is None:
        return None, None
    ultima = sessao.scalar(select(func.max(TituloTesouroTaxa.data_base)).where(TituloTesouroTaxa.titulo == titulo))
    if ultima is None:
        return None, None
    t = sessao.scalar(select(TituloTesouroTaxa).where(TituloTesouroTaxa.titulo == titulo,
                                                      TituloTesouroTaxa.data_base == ultima,
                                                      TituloTesouroTaxa.taxa_compra.is_not(None))
                      .order_by(desc(TituloTesouroTaxa.vencimento)).limit(1))
    if t is None:
        return None, None
    return float(t.taxa_compra) / 100, f"{titulo} {t.vencimento.year} em {ultima:%d/%m/%Y}"


def _dividendo_12m(sessao: Session, ativo_id: int, preco: float | None) -> float | None:
    dy = sessao.scalar(select(IndicadorCalculado.valor).where(IndicadorCalculado.ativo_id == ativo_id,
                                                               IndicadorCalculado.metrica == "basico.dy"))
    return float(dy) * preco if dy is not None and preco else None


def _preco(sessao: Session, ativo_id: int) -> tuple[float | None, str | None]:
    c = sessao.scalar(select(CotacaoDiaria).where(CotacaoDiaria.ativo_id == ativo_id)
                      .order_by(desc(CotacaoDiaria.data)).limit(1))
    return (float(c.fechamento), c.data.isoformat()) if c else (None, None)


def gordon_fundo(sessao: Session, ticker: str, base: str = "prefixado", taxa: float | None = None,
                 premio: float = PREMIO_PADRAO, crescimento: float = CRESCIMENTO_PADRAO,
                 liquida: bool = True) -> dict | None:
    achado = _fundo(sessao, ticker)
    if achado is None:
        return None
    ativo, _ = achado
    preco, data_preco = _preco(sessao, ativo.id)
    descricao = "informada pelo usuário"
    if taxa is None:
        taxa, descricao = taxa_base(sessao, base)
    dividendo = _dividendo_12m(sessao, ativo.id, preco)
    r = mfii.gordon_ajustado(dividendo, taxa, premio, crescimento, usar_taxa_liquida=liquida)
    margem = graham.margem_seguranca(r.valor, preco).valor if r.disponivel and preco else None
    return {"ticker": ativo.ticker, "preco": preco, "data_preco": data_preco, "dividendo_12m": dividendo,
            "taxa_base": taxa, "descricao_taxa": descricao, "base": base, "premio": premio, "crescimento": crescimento,
            "taxa_liquida": liquida, "taxa_exigida": r.detalhes.get("taxa_exigida"), "preco_teto": r.valor,
            "motivo_indisponivel": r.motivo_indisponivel, "margem_seguranca": margem,
            "metodologia": "fii.gordon_ajustado", "aviso": AVISO_NAO_RECOMENDACAO}


# ---------------------------------------------------------------- documentos (FNET)


def documentos_fnet(sessao: Session, ticker: str, limite: int = 30, cliente: httpx.Client | None = None) -> dict | None:
    """Documentos mais recentes do fundo no FNET (consulta pública, sob demanda; só metadados e link)."""
    achado = _fundo(sessao, ticker)
    if achado is None:
        return None
    _, fii = achado
    if fii is None:
        return {"documentos": [], "erro": "fundo sem informe da CVM ligado ao ticker", "busca": URL_FNET_BUSCA}
    params = {"d": 0, "s": 0, "l": limite, "o[0][dataEntrega]": "desc", "tipoFundo": 1,
              "cnpjFundo": re.sub(r"\D", "", fii.cnpj)}
    proprio = cliente is None
    cliente = cliente or cliente_http()
    try:
        resposta = cliente.get(URL_FNET_LISTA, params=params, timeout=20)
        resposta.raise_for_status()
        dados = resposta.json().get("data") or []
    except (httpx.HTTPError, ValueError) as erro:
        log.warning("FNET indisponível para %s: %r", ticker, erro)
        return {"documentos": [], "erro": "FNET indisponível no momento", "busca": URL_FNET_BUSCA}
    finally:
        if proprio:
            cliente.close()
    docs = [{"id": d.get("id"), "categoria": d.get("categoriaDocumento"), "tipo": d.get("tipoDocumento"),
             "especie": d.get("especieDocumento"), "referencia": d.get("dataReferencia"),
             "entrega": d.get("dataEntrega"), "status": d.get("status"),
             "url": URL_FNET_VER.format(id=d.get("id"))} for d in dados if d.get("id")]
    return {"documentos": docs, "erro": None, "busca": URL_FNET_BUSCA, "fonte": "B3 — FNET"}


# ---------------------------------------------------------------- Fund Screening

FAIXAS_FII = {
    "dy": "basico.dy", "p_vp": "fii.p_vp", "patrimonio": "fii.patrimonio_liquido", "liquidez": "basico.liquidez_diaria",
    "vacancia": "fii.vacancia", "alavancagem": "fii.alavancagem", "cotistas": "fii.numero_cotistas",
}
ORDENACOES_FII = ("gordon", "dy", "p_vp")


@dataclass(frozen=True)
class FiltrosFii:
    faixas: dict[str, tuple[float | None, float | None]] = field(default_factory=dict)
    segmentos: tuple[str, ...] = ()
    tipos: tuple[str, ...] = ()
    tickers: frozenset[str] | None = None
    ordenar_por: str = "gordon"
    base: str = "prefixado"
    premio: float = PREMIO_PADRAO
    crescimento: float = CRESCIMENTO_PADRAO


def _ultimos_extras(sessao: Session) -> dict[int, tuple[dict | None, float | None]]:
    """(extras, ativo_total) do informe mais recente de cada fundo."""
    linhas = sessao.execute(select(FiiInformeMensal.fii_id, FiiInformeMensal.extras, FiiInformeMensal.ativo_total)
                            .distinct(FiiInformeMensal.fii_id)
                            .order_by(FiiInformeMensal.fii_id, desc(FiiInformeMensal.competencia),
                                      desc(FiiInformeMensal.versao)))
    return {f: (e, _f(t)) for f, e, t in linhas}


def screening_fiis(sessao: Session, f: FiltrosFii = FiltrosFii()) -> dict:
    if f.ordenar_por not in ORDENACOES_FII:
        raise ValueError(f"ordenação desconhecida: {f.ordenar_por}")
    ativos = list(sessao.execute(select(Ativo, Fii).outerjoin(Fii, Fii.ativo_id == Ativo.id)
                                 .where(Ativo.classe == "FII", Ativo.ativo.is_(True))))
    ids = [a.id for a, _ in ativos]
    valores: dict[int, dict[str, float]] = {}
    for ativo_id, metrica, valor in sessao.execute(
            select(IndicadorCalculado.ativo_id, IndicadorCalculado.metrica, IndicadorCalculado.valor)
            .where(IndicadorCalculado.ativo_id.in_(ids), IndicadorCalculado.metrica.in_(list(FAIXAS_FII.values())))):
        if valor is not None:
            valores.setdefault(ativo_id, {})[metrica] = float(valor)
    precos = {a: (float(p), d.isoformat()) for a, p, d in sessao.execute(
        select(CotacaoDiaria.ativo_id, CotacaoDiaria.fechamento, CotacaoDiaria.data)
        .where(CotacaoDiaria.ativo_id.in_(ids)).distinct(CotacaoDiaria.ativo_id)
        .order_by(CotacaoDiaria.ativo_id, desc(CotacaoDiaria.data)))}
    extras = _ultimos_extras(sessao)
    taxa, descricao_taxa = taxa_base(sessao, f.base)
    segmentos = sorted({fii.segmento for _, fii in ativos if fii and fii.segmento})
    itens, sem_cotacao = [], 0
    for ativo, fii in ativos:
        if ativo.id not in precos:
            sem_cotacao += 1
            continue
        preco, data_preco = precos[ativo.id]
        v = valores.get(ativo.id, {})
        linha = {nome: v.get(metrica) for nome, metrica in FAIXAS_FII.items()}
        e, total = extras.get(fii.id, (None, None)) if fii else (None, None)
        comp = mfii.composicao_ativo(e, total)
        tipo = mfii.tipo_do_fundo(comp.detalhes["grupos"]) if comp.disponivel else None
        if f.tickers is not None and ativo.ticker not in f.tickers:
            continue
        if f.segmentos and (fii is None or fii.segmento not in f.segmentos):
            continue
        if f.tipos and tipo not in f.tipos:
            continue
        if not all(_dentro(linha[nome], faixa) for nome, faixa in f.faixas.items()):
            continue
        dividendo = linha["dy"] * preco if linha["dy"] is not None else None
        g = mfii.gordon_ajustado(dividendo, taxa, f.premio, f.crescimento)
        itens.append({"ticker": ativo.ticker, "nome": fii.nome if fii else None,
                      "segmento": fii.segmento if fii else None, "tipo": tipo, "preco": preco,
                      "data_preco": data_preco, **linha, "gordon_teto": g.valor,
                      "gordon_margem": graham.margem_seguranca(g.valor, preco).valor if g.disponivel else None})
    if f.ordenar_por == "gordon":
        chave = lambda i: (i["gordon_margem"] is None, -(i["gordon_margem"] or 0), i["ticker"])  # noqa: E731
    elif f.ordenar_por == "dy":
        chave = lambda i: (i["dy"] is None, -(i["dy"] or 0), i["ticker"])  # noqa: E731
    else:
        chave = lambda i: (i["p_vp"] is None, i["p_vp"] or 0, i["ticker"])  # noqa: E731
    itens.sort(key=chave)
    for n, i in enumerate(itens, start=1):
        i["posicao"] = n
    return {"aviso": AVISO_NAO_RECOMENDACAO, "ordenar_por": f.ordenar_por, "taxa_base": taxa,
            "descricao_taxa": descricao_taxa, "atualizado_em": max((i["data_preco"] for i in itens), default=None),
            "total_avaliados": len(ativos), "sem_cotacao": sem_cotacao, "segmentos": segmentos,
            "tipos": ["Tijolo", "Papel", "Fundo de fundos", "Híbrido"], "itens": itens}
