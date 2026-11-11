"""Diagnóstico da instalação: `python -m app.jobs.cli diagnostico [TICKER]`.

Imprime, em texto simples para copiar e colar, o que foi carregado, o último resultado de cada fonte,
um teste ao vivo do Yahoo Finance e o motivo de cada indicador indisponível do ticker escolhido.
"""

from datetime import date

from sqlalchemy import desc, func, select

from app.config import obter_configuracao
from app.db.modelos import (
    Ativo,
    ComposicaoCapital,
    CotacaoDiaria,
    DemonstracaoLinha,
    DemonstracaoPadronizada,
    Fii,
    Fonte,
    IndicadorCalculado,
    LoteIngestao,
    Provento,
)
from app.db.sessao import FabricaSessao
from app.ingestao import yahoo
from app.ingestao.base import cliente_http, garantir_fontes

INDICADORES = ("basico.lpa", "basico.vpa", "basico.p_l", "basico.p_vp", "basico.dy", "basico.roe",
               "graham.valor_intrinseco", "basico.liquidez_diaria")


def _testar_padronizacao(sessao, empresa) -> str:
    """Roda a organização dos balanços da empresa em memória e devolve o resultado ou o erro."""
    import traceback

    from app.ingestao.padronizacao import padronizar, plano_pela_dre
    from app.ingestao.padronizacao_db import _COLUNAS
    consulta = select(*[getattr(DemonstracaoLinha, c) for c in _COLUNAS]).where(
        DemonstracaoLinha.empresa_id == empresa.id)
    linhas = [dict(zip(_COLUNAS, r, strict=True)) for r in sessao.execute(consulta)]
    try:
        periodos = padronizar(linhas, plano_pela_dre(linhas, empresa.tipo_plano_contas))
    except Exception:  # noqa: BLE001
        return "ERRO\n" + traceback.format_exc()[-1500:]
    exemplos = sorted({(p.periodo, p.tipo_periodo) for p in periodos})[-4:]
    return f"ok, {len(periodos)} períodos (ex.: {exemplos}); rode `completar` para gravá-los"


def executar(ticker: str = "PETR4") -> str:
    linhas: list[str] = []
    p = linhas.append
    cfg = obter_configuracao()
    p(f"=== DIAGNÓSTICO (fonte de mercado: {cfg.fonte_mercado}) ===")
    with FabricaSessao() as s:
        garantir_fontes(s)
        s.commit()
        contar = lambda modelo: s.scalar(select(func.count()).select_from(modelo))  # noqa: E731
        p(f"ativos: {contar(Ativo)} | cotações: {contar(CotacaoDiaria)} | proventos: {contar(Provento)} | "
          f"linhas de balanço: {contar(DemonstracaoLinha)} | balanços organizados: {contar(DemonstracaoPadronizada)} "
          f"| composição do capital: {contar(ComposicaoCapital)}")
        fiis = s.scalar(select(func.count()).select_from(Fii))
        com_isin = s.scalar(select(func.count()).select_from(Fii).where(Fii.isin.is_not(None)))
        com_ticker = s.scalar(select(func.count()).select_from(Fii).where(Fii.ativo_id.is_not(None)))
        exemplo = s.scalar(select(Fii).order_by(desc(Fii.data_referencia)).limit(1))
        p(f"FIIs: {fiis} | com ISIN: {com_isin} | com ticker: {com_ticker} | ex.: "
          f"{(exemplo.nome, exemplo.isin) if exemplo else '-'}")
        p("")
        p("--- último lote de cada fonte ---")
        for f in s.scalars(select(Fonte).order_by(Fonte.id)):
            lote = s.scalar(select(LoteIngestao).where(LoteIngestao.fonte_id == f.id).order_by(desc(LoteIngestao.id)))
            if lote is None:
                p(f"{f.codigo}: nunca executado")
                continue
            p(f"{f.codigo}: {lote.status} em {lote.concluido_em or lote.iniciado_em:%d/%m %H:%M} | "
              f"{lote.linhas_gravadas} linhas | {(lote.erro or '').strip()[:300]}")
        p("")
        from app.jobs.tarefas import ultima_cotacao, ultimo_dia_util
        p(f"cotações das ações em dia até: {ultima_cotacao(s)} (último dia útil: {ultimo_dia_util(date.today())})")
        p("últimas rodadas do Yahoo:")
        for lote in s.scalars(select(LoteIngestao).join(Fonte).where(Fonte.codigo == "YAHOO_FINANCE")
                              .order_by(desc(LoteIngestao.id)).limit(5)):
            p(f"  {lote.iniciado_em:%d/%m %H:%M} → {lote.status} | {lote.linhas_gravadas} linhas | "
              f"{(lote.erro or '').strip()[:200]}")
        p("")
        ativo = s.scalar(select(Ativo).where(Ativo.ticker == ticker.upper()))
        p(f"--- {ticker.upper()} ---")
        if ativo is None:
            p("ticker não cadastrado")
        else:
            empresa = ativo.empresa
            p(f"classe {ativo.classe} | isin {ativo.isin} | ativo={ativo.ativo} | empresa: "
              f"{empresa.nome if empresa else '-'} (cnpj {empresa.cnpj if empresa else '-'})")
            if empresa:
                p(f"linhas de balanço: {s.scalar(select(func.count()).select_from(DemonstracaoLinha).where(DemonstracaoLinha.empresa_id == empresa.id))}"  # noqa: E501
                  f" | períodos organizados: {s.scalar(select(func.count()).select_from(DemonstracaoPadronizada).where(DemonstracaoPadronizada.empresa_id == empresa.id))}"  # noqa: E501
                  f" | composição do capital: {s.scalar(select(func.count()).select_from(ComposicaoCapital).where(ComposicaoCapital.empresa_id == empresa.id))}")  # noqa: E501
            if empresa and not s.scalar(select(func.count()).select_from(DemonstracaoPadronizada)
                                        .where(DemonstracaoPadronizada.empresa_id == empresa.id)):
                p("organização dos balanços (teste agora): " + _testar_padronizacao(s, empresa))
            if empresa:
                p("resultados por período (R$ mi: receita | EBIT | lucro líquido | PL):")
                periodos = s.scalars(select(DemonstracaoPadronizada).where(
                    DemonstracaoPadronizada.empresa_id == empresa.id,
                    DemonstracaoPadronizada.tipo_periodo.in_(("trimestre", "ttm", "ano")))
                    .order_by(desc(DemonstracaoPadronizada.data_fim), DemonstracaoPadronizada.tipo_periodo).limit(12))
                for per in periodos:
                    c = per.campos
                    mi = lambda v: "-" if v is None else f"{v / 1e6:,.1f}"  # noqa: E731
                    base = "consolidado" if per.consolidado else "individual"
                    p(f"  {per.periodo:<9} {per.tipo_periodo:<9} {base:<11}"
                      f" v{per.versao_usada} | {mi(c.get('receita_liquida'))} | {mi(c.get('ebit'))} | "
                      f"{mi(c.get('lucro_liquido_controladores', c.get('lucro_liquido')))} | "
                      f"{mi(c.get('patrimonio_liquido'))}")
            ultima = s.scalar(select(CotacaoDiaria).where(CotacaoDiaria.ativo_id == ativo.id)
                              .order_by(desc(CotacaoDiaria.data)))
            p(f"última cotação: {f'{ultima.data} R$ {ultima.fechamento}' if ultima else 'nenhuma'}")
            for m in INDICADORES:
                ind = s.scalar(select(IndicadorCalculado).where(IndicadorCalculado.ativo_id == ativo.id,
                                                                IndicadorCalculado.metrica == m))
                if ind is None:
                    p(f"  {m}: não calculado")
                else:
                    texto = ind.valor if ind.valor is not None else f"indisponível — {ind.motivo_indisponivel or ''}"
                    p(f"  {m}: {texto}")
    p("")
    p(f"--- teste ao vivo do Yahoo ({yahoo.simbolo(ticker)}) ---")
    try:
        with cliente_http() as cliente:
            r = yahoo._consultar(cliente, ticker, "5d", tentativas=1)
        p(f"HTTP {r.status_code}")
        if r.status_code == 200:
            dados = yahoo.parse(r.json())
            p(f"{len(dados['cotacoes'])} pregões; último: {dados['cotacoes'][-1] if dados['cotacoes'] else '-'}")
        else:
            p(f"resposta: {r.text[:300]}")
    except Exception as erro:  # noqa: BLE001
        p(f"falhou: {erro!r}"[:400])
    return "\n".join(linhas)
