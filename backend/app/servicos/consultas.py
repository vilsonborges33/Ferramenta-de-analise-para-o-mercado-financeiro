"""Leitura dos dados para a API, sempre com a procedência de cada número."""

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.db.modelos import (
    Ativo,
    CotacaoDiaria,
    Fii,
    Fonte,
    IndicadorCalculado,
    SerieEconomica,
    TituloTesouroTaxa,
)
from app.metodologias.registro import POR_ID

COLUNAS_LISTA_ACOES = ("basico.p_l", "basico.p_vp", "basico.dy", "basico.roe", "basico.margem_liquida",
                       "basico.ev_ebitda", "basico.dl_ebitda", "basico.liquidez_diaria")
COLUNAS_LISTA_FIIS = ("fii.p_vp", "basico.dy", "fii.dy_informado_12m", "fii.patrimonio_liquido",
                      "fii.numero_cotistas", "basico.liquidez_diaria")


def numero(ind: IndicadorCalculado | None, metrica_id: str) -> dict:
    metrica = POR_ID[metrica_id]
    base = {"metrica": metrica_id, "nome": metrica.nome, "unidade": metrica.unidade}
    if ind is None:
        return {**base, "valor": None, "motivo_indisponivel": "ainda não calculado", "procedencia": [],
                "aviso": None, "data_referencia": None}
    insumos = [i for i in ind.insumos if "insumo" in i]
    avisos = [i["aviso"] for i in ind.insumos if "aviso" in i]
    return {**base, "valor": None if ind.valor is None else float(ind.valor),
            "motivo_indisponivel": ind.motivo_indisponivel, "procedencia": insumos,
            "aviso": avisos[0] if avisos else None,
            "data_referencia": ind.data_referencia.isoformat() if ind.data_referencia else None,
            "calculado_em": ind.calculado_em.isoformat()}


def _indicadores(sessao: Session, ativo_ids: list[int]) -> dict[int, dict[str, IndicadorCalculado]]:
    resultado: dict[int, dict[str, IndicadorCalculado]] = {}
    for ind in sessao.scalars(select(IndicadorCalculado).where(IndicadorCalculado.ativo_id.in_(ativo_ids))):
        resultado.setdefault(ind.ativo_id, {})[ind.metrica] = ind
    return resultado


def _cotacao(sessao: Session, ativo_id: int, fontes: dict[int, str]) -> dict | None:
    c = sessao.scalar(select(CotacaoDiaria).where(CotacaoDiaria.ativo_id == ativo_id)
                      .order_by(desc(CotacaoDiaria.data)).limit(1))
    if c is None:
        return None
    return {"valor": float(c.fechamento), "data": c.data.isoformat(), "fonte": fontes.get(c.fonte_id),
            "coletado_em": c.coletado_em.isoformat()}


def listar(sessao: Session, classe: str, busca: str | None = None) -> list[dict]:
    consulta = select(Ativo).where(Ativo.classe == classe, Ativo.ativo.is_(True)).order_by(Ativo.ticker)
    if busca:
        consulta = consulta.where(Ativo.ticker.ilike(f"%{busca.strip()}%"))
    ativos = list(sessao.scalars(consulta))
    inds = _indicadores(sessao, [a.id for a in ativos])
    fontes = {f.id: f.codigo for f in sessao.scalars(select(Fonte))}
    colunas = COLUNAS_LISTA_FIIS if classe == "FII" else COLUNAS_LISTA_ACOES
    nomes_fii = {f.ativo_id: f.nome for f in sessao.scalars(select(Fii).where(Fii.ativo_id.is_not(None)))}
    saida = []
    for a in ativos:
        if a.id not in inds:  # sem nenhum dado calculado ainda
            continue
        nome = nomes_fii.get(a.id) if classe == "FII" else (a.empresa.nome if a.empresa else None)
        saida.append({
            "ticker": a.ticker, "nome": nome, "setor": a.empresa.setor if a.empresa else None,
            "cotacao": _cotacao(sessao, a.id, fontes),
            "indicadores": {m: numero(inds[a.id].get(m), m) for m in colunas},
        })
    return saida


def detalhe(sessao: Session, ticker: str) -> dict | None:
    ativo = sessao.scalar(select(Ativo).where(Ativo.ticker == ticker.upper()))
    if ativo is None:
        return None
    inds = _indicadores(sessao, [ativo.id]).get(ativo.id, {})
    fontes = {f.id: f.codigo for f in sessao.scalars(select(Fonte))}
    grupos: dict[str, list[dict]] = {}
    for metrica in POR_ID.values():
        tipo = "FII" if ativo.classe == "FII" else "ACAO"
        if tipo not in metrica.aplica_a:
            continue
        grupos.setdefault(metrica.grupo, []).append(numero(inds.get(metrica.id), metrica.id))
    info: dict = {"ticker": ativo.ticker, "classe": ativo.classe, "especie": ativo.especie, "isin": ativo.isin}
    if ativo.empresa:
        e = ativo.empresa
        info.update(nome=e.nome, cnpj=e.cnpj, setor=e.setor, segmento_listagem=e.segmento_listagem,
                    tipo_plano_contas=e.tipo_plano_contas,
                    outros_tickers=[a.ticker for a in e.ativos if a.id != ativo.id])
    fii = sessao.scalar(select(Fii).where(Fii.ativo_id == ativo.id))
    if fii:
        info.update(nome=fii.nome, cnpj=fii.cnpj, segmento=fii.segmento, mandato=fii.mandato,
                    tipo_gestao=fii.tipo_gestao, administrador=fii.administrador, publico_alvo=fii.publico_alvo)
    return {**info, "cotacao": _cotacao(sessao, ativo.id, fontes), "grupos": grupos}


def historico_cotacoes(sessao: Session, ticker: str, limite: int = 750) -> list[dict]:
    ativo = sessao.scalar(select(Ativo).where(Ativo.ticker == ticker.upper()))
    if ativo is None:
        return []
    linhas = sessao.scalars(select(CotacaoDiaria).where(CotacaoDiaria.ativo_id == ativo.id)
                            .order_by(desc(CotacaoDiaria.data)).limit(limite))
    return [{"data": c.data.isoformat(), "fechamento": float(c.fechamento)} for c in reversed(list(linhas))]


def serie(sessao: Session, codigo: str, desde=None) -> list[dict]:
    consulta = select(SerieEconomica).where(SerieEconomica.codigo == codigo).order_by(SerieEconomica.data)
    if desde:
        consulta = consulta.where(SerieEconomica.data >= desde)
    return [{"data": s.data.isoformat(), "valor": float(s.valor)} for s in sessao.scalars(consulta)]


def taxas_tesouro(sessao: Session) -> list[dict]:
    from sqlalchemy import func
    ultima = sessao.scalar(select(func.max(TituloTesouroTaxa.data_base)))
    if ultima is None:
        return []
    linhas = sessao.scalars(select(TituloTesouroTaxa).where(TituloTesouroTaxa.data_base == ultima)
                            .order_by(TituloTesouroTaxa.titulo, TituloTesouroTaxa.vencimento))
    return [{"titulo": t.titulo, "vencimento": t.vencimento.isoformat(), "data_base": t.data_base.isoformat(),
             "taxa_compra": None if t.taxa_compra is None else float(t.taxa_compra),
             "taxa_venda": None if t.taxa_venda is None else float(t.taxa_venda)} for t in linhas]
