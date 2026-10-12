"""B3 COTAHIST: séries históricas de cotações (arquivo de largura fixa, 245 posições).

Anual:  https://bvmf.bmfbovespa.com.br/InstDados/SerHist/COTAHIST_AAAAAA.ZIP (ex.: COTAHIST_A2025.ZIP)
Diário: https://bvmf.bmfbovespa.com.br/InstDados/SerHist/COTAHIST_DDDMMAAAA.ZIP

Layout oficial da B3 ("SeriesHistoricas_Layout.pdf"). Preços sem ajuste por proventos.
Uso conforme a Política de Market Data da B3 — ver docs/FONTES_DE_DADOS.md (uso pessoal).
"""

import io
import logging
import zipfile
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.db.modelos import Ativo, CotacaoDiaria, Fii
from app.ingestao.base import Contexto, EsquemaInesperado, baixar, lote

log = logging.getLogger(__name__)

URL_ANUAL = "https://bvmf.bmfbovespa.com.br/InstDados/SerHist/COTAHIST_A{ano}.ZIP"
URL_DIARIO = "https://bvmf.bmfbovespa.com.br/InstDados/SerHist/COTAHIST_D{data:%d%m%Y}.ZIP"

MERCADO_A_VISTA = "010"
# CODBDI: 02 lote padrão; 12 fundos imobiliários; 14 certificados/ETFs (cotas de fundos de índice).
CODBDI_ACEITOS = {"02", "12", "14"}


def _preco(campo: str) -> Decimal:
    return Decimal(int(campo)) / 100  # 11 inteiros + 2 decimais


def parse_linha(linha: str) -> dict | None:
    if not linha.startswith("01"):
        return None
    if len(linha.rstrip("\r\n")) < 245:
        raise EsquemaInesperado(f"COTAHIST: linha com {len(linha)} posições (esperado 245)")
    if linha[24:27] != MERCADO_A_VISTA or linha[10:12] not in CODBDI_ACEITOS:
        return None
    return {
        "data": date(int(linha[2:6]), int(linha[6:8]), int(linha[8:10])),
        "codbdi": linha[10:12],
        "ticker": linha[12:24].strip(),
        "especificacao": linha[39:49].strip(),
        "abertura": _preco(linha[56:69]),
        "maxima": _preco(linha[69:82]),
        "minima": _preco(linha[82:95]),
        "fechamento": _preco(linha[108:121]),
        "negocios": int(linha[147:152]),
        "volume_financeiro": _preco(linha[170:188]),
        "fator_cotacao": int(linha[210:217]),
        "isin": linha[230:242].strip(),
    }


def parse(texto: str, tickers: set[str] | None = None) -> list[dict]:
    registros = []
    for linha in texto.splitlines():
        r = parse_linha(linha)
        if r is None or (tickers is not None and r["ticker"] not in tickers):
            continue
        if r["fator_cotacao"] != 1:  # cotação por lote de N ações: normaliza para 1 ação
            fator = Decimal(r["fator_cotacao"])
            for campo in ("abertura", "maxima", "minima", "fechamento"):
                r[campo] = r[campo] / fator
        registros.append(r)
    return registros


def gravar(ctx: Contexto, registros: list[dict]) -> int:
    ativos = {a.ticker: a for a in ctx.sessao.scalars(select(Ativo))}
    linhas = []
    for r in registros:
        ativo = ativos.get(r["ticker"])
        if ativo is None:
            continue
        if ativo.isin is None and r["isin"]:
            ativo.isin = r["isin"]
        linhas.append({
            "ativo_id": ativo.id, "data": r["data"], "abertura": r["abertura"], "maxima": r["maxima"],
            "minima": r["minima"], "fechamento": r["fechamento"], "volume_financeiro": r["volume_financeiro"],
            "negocios": r["negocios"], **ctx.procedencia(r["data"]),
        })
    for i in range(0, len(linhas), 5000):
        bloco = linhas[i:i + 5000]
        stmt = insert(CotacaoDiaria)
        # COTAHIST é a fonte oficial: sobrescreve o que veio de outro provedor para o mesmo pregão.
        stmt = stmt.on_conflict_do_update(
            index_elements=["ativo_id", "data"],
            set_={c: stmt.excluded[c] for c in bloco[0] if c not in ("ativo_id", "data")},
        )
        ctx.sessao.execute(stmt, bloco)
    ctx.lote.linhas_gravadas = len(linhas)
    return len(linhas)


def criar_ativos_fii(ctx: Contexto, registros: list[dict]) -> int:
    """Cria `ativo` para cotas de FII (CODBDI 12) e liga ao `fii` pelo ISIN do informe mensal."""
    existentes = set(ctx.sessao.scalars(select(Ativo.ticker)))
    novos = 0
    for r in registros:
        if r["codbdi"] != "12" or r["ticker"] in existentes:
            continue
        existentes.add(r["ticker"])
        ctx.sessao.add(Ativo(ticker=r["ticker"], classe="FII", isin=r["isin"] or None, mercado="B3", moeda="BRL"))
        novos += 1
    ctx.sessao.flush()
    ligar_fiis_por_isin(ctx.sessao)
    return novos


def ligar_fiis_por_isin(sessao) -> None:
    """Liga cada cota negociada a um único fundo. Vários cadastros podem informar o mesmo ISIN
    (ex.: fundo e classe após a Resolução CVM 175); fica o cadastro mais recente."""
    ativos_por_isin = {a.isin: a.id for a in sessao.scalars(select(Ativo).where(Ativo.classe == "FII"))
                       if a.isin}
    ligados = set(sessao.scalars(select(Fii.ativo_id).where(Fii.ativo_id.is_not(None))))
    candidatos = sessao.scalars(select(Fii).where(Fii.ativo_id.is_(None), Fii.isin.is_not(None))
                                .order_by(Fii.data_referencia.desc(), Fii.id.desc()))
    for fii in candidatos:
        ativo_id = ativos_por_isin.get(fii.isin)
        if ativo_id is not None and ativo_id not in ligados:
            fii.ativo_id = ativo_id
            ligados.add(ativo_id)
    sessao.flush()


def ingerir_arquivo(sessao, url: str, tickers: set[str] | None = None) -> int:
    with lote(sessao, "B3_COTAHIST", url) as ctx:
        caminho, ctx.lote.hash_arquivo = baixar(url, "B3_COTAHIST")
        z = zipfile.ZipFile(caminho)
        nome = z.namelist()[0]
        texto = io.TextIOWrapper(z.open(nome), encoding="latin-1").read()
        registros = parse(texto, tickers)
        try:
            with ctx.sessao.begin_nested():  # falha ao ligar FIIs não pode impedir a gravação das cotações
                criar_ativos_fii(ctx, registros)
        except Exception:
            log.exception("COTAHIST: falha ao criar/ligar ativos de FII; seguindo com as cotações")
        return gravar(ctx, registros)


def ingerir_ano(sessao, ano: int, tickers: set[str] | None = None) -> int:
    return ingerir_arquivo(sessao, URL_ANUAL.format(ano=ano), tickers)


def ingerir_dia(sessao, data: date, tickers: set[str] | None = None) -> int:
    if data.weekday() >= 5:  # sábado/domingo: não há pregão
        return 0
    return ingerir_arquivo(sessao, URL_DIARIO.format(data=data), tickers) or 0
