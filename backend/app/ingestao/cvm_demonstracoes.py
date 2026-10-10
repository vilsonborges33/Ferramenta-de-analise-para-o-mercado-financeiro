"""CVM: DFP (anual) e ITR (trimestral) → `demonstracao_linha` e `composicao_capital`.

Arquivos (Dados Abertos CVM, ODbL), um ZIP por ano:
- https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/DFP/DADOS/dfp_cia_aberta_AAAA.zip
- https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/ITR/DADOS/itr_cia_aberta_AAAA.zip

Cada ZIP traz um CSV por demonstração e por visão (con = consolidado, ind = individual), em
formato longo: uma linha por conta. Só a coluna ORDEM_EXERC = "ÚLTIMO" é gravada (o exercício
corrente do documento); comparativos reapresentados chegam pelas versões seguintes.
"""

import io
import zipfile
from decimal import Decimal

import pandas as pd
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.db.modelos import Ativo, ComposicaoCapital, DemonstracaoLinha, Empresa
from app.ingestao.base import Contexto, baixar, data_br, decimal_br, exigir_colunas, lote
from app.ingestao.cvm_companhias import ler_csv_cvm

URLS = {
    "DFP": "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/DFP/DADOS/dfp_cia_aberta_{ano}.zip",
    "ITR": "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/ITR/DADOS/itr_cia_aberta_{ano}.zip",
}
TIPOS = ("BPA", "BPP", "DRE", "DFC_MD", "DFC_MI")
COLUNAS = {"CNPJ_CIA", "DT_REFER", "VERSAO", "ESCALA_MOEDA", "ORDEM_EXERC", "DT_FIM_EXERC", "CD_CONTA",
           "DS_CONTA", "VL_CONTA"}
COLUNAS_CAPITAL = {"CNPJ_CIA", "DT_REFER", "VERSAO", "QT_ACAO_ORDIN_CAP_INTEGR", "QT_ACAO_PREF_CAP_INTEGR",
                   "QT_ACAO_ORDIN_TESOURO", "QT_ACAO_PREF_TESOURO"}
ESCALAS = {"UNIDADE": Decimal(1), "MIL": Decimal(1000)}
TAMANHO_BLOCO = 5000


def parse_demonstracao(df: pd.DataFrame, documento: str, tipo: str, consolidado: bool,
                       cnpjs: set[str] | None = None) -> list[dict]:
    """Converte um CSV de demonstração em registros com valores em unidades de R$."""
    nome = f"{documento}_{tipo}_{'con' if consolidado else 'ind'}"
    exigir_colunas(df.columns, COLUNAS, nome)
    df = df[df["ORDEM_EXERC"].str.upper().str.startswith("ÚLTIMO")]
    if cnpjs is not None:
        df = df[df["CNPJ_CIA"].isin(cnpjs)]
    tem_inicio = "DT_INI_EXERC" in df.columns
    tem_fixa = "ST_CONTA_FIXA" in df.columns
    registros = []
    for linha in df.itertuples(index=False):
        escala = ESCALAS.get(linha.ESCALA_MOEDA.upper())
        if escala is None:
            raise ValueError(f"{nome}: escala desconhecida {linha.ESCALA_MOEDA!r}")
        valor = decimal_br(linha.VL_CONTA)
        if valor is None:
            continue
        registros.append({
            "cnpj": linha.CNPJ_CIA,
            "documento": documento,
            "tipo": tipo,
            "consolidado": consolidado,
            "ordem_exercicio": "ULTIMO",
            "data_inicio": data_br(linha.DT_INI_EXERC) if tem_inicio else None,
            "data_fim": data_br(linha.DT_FIM_EXERC),
            "data_referencia": data_br(linha.DT_REFER),
            "versao": int(linha.VERSAO),
            "conta_codigo": linha.CD_CONTA,
            "conta_descricao": linha.DS_CONTA[:500],
            "conta_fixa": (linha.ST_CONTA_FIXA == "S") if tem_fixa else None,
            "valor": valor * escala,
        })
    return registros


def parse_composicao_capital(df: pd.DataFrame, cnpjs: set[str] | None = None) -> list[dict]:
    exigir_colunas(df.columns, COLUNAS_CAPITAL, "composicao_capital")
    if cnpjs is not None:
        df = df[df["CNPJ_CIA"].isin(cnpjs)]
    # Mantém a versão mais recente de cada documento.
    df = df.assign(_v=df["VERSAO"].astype(int)).sort_values("_v").drop_duplicates(
        ["CNPJ_CIA", "DT_REFER"], keep="last")
    return [{
        "cnpj": linha["CNPJ_CIA"],
        "data_referencia": data_br(linha["DT_REFER"]),
        "acoes_ordinarias": decimal_br(linha["QT_ACAO_ORDIN_CAP_INTEGR"]),
        "acoes_preferenciais": decimal_br(linha["QT_ACAO_PREF_CAP_INTEGR"]),
        "acoes_tesouraria_on": decimal_br(linha["QT_ACAO_ORDIN_TESOURO"]),
        "acoes_tesouraria_pn": decimal_br(linha["QT_ACAO_PREF_TESOURO"]),
    } for _, linha in df.iterrows()]


def _empresas_listadas(ctx: Contexto) -> dict[str, int]:
    """CNPJ → empresa_id, só para empresas com ao menos um ticker (reduz o volume gravado)."""
    consulta = select(Empresa.cnpj, Empresa.id).join(Ativo, Ativo.empresa_id == Empresa.id).distinct()
    return {cnpj: id_ for cnpj, id_ in ctx.sessao.execute(consulta)}


def gravar_linhas(ctx: Contexto, registros: list[dict], empresas: dict[str, int]) -> int:
    linhas = []
    for r in registros:
        empresa_id = empresas.get(r["cnpj"])
        if empresa_id is None:
            continue
        r = {k: v for k, v in r.items() if k != "cnpj"}
        r.update(empresa_id=empresa_id, fonte_id=ctx.fonte.id, lote_ingestao_id=ctx.lote.id,
                 coletado_em=ctx.coletado_em)
        linhas.append(r)
    for i in range(0, len(linhas), TAMANHO_BLOCO):
        ctx.sessao.execute(insert(DemonstracaoLinha).on_conflict_do_nothing(), linhas[i:i + TAMANHO_BLOCO])
    return len(linhas)


def gravar_composicao(ctx: Contexto, registros: list[dict], empresas: dict[str, int]) -> int:
    gravados = 0
    for r in registros:
        empresa_id = empresas.get(r["cnpj"])
        if empresa_id is None:
            continue
        valores = {k: v for k, v in r.items() if k != "cnpj"}
        valores.update(empresa_id=empresa_id, **ctx.procedencia(r["data_referencia"]))
        stmt = insert(ComposicaoCapital).values(**valores)
        stmt = stmt.on_conflict_do_update(
            index_elements=["empresa_id", "data_referencia"],
            set_={k: stmt.excluded[k] for k in valores if k not in ("empresa_id", "data_referencia")},
        )
        ctx.sessao.execute(stmt)
        gravados += 1
    return gravados


def processar_zip(ctx: Contexto, conteudo_zip: zipfile.ZipFile, documento: str, ano: int) -> int:
    empresas = _empresas_listadas(ctx)
    cnpjs = set(empresas)
    prefixo = documento.lower()
    total = 0
    nomes = set(conteudo_zip.namelist())
    for tipo in TIPOS:
        for consolidado in (True, False):
            nome = f"{prefixo}_cia_aberta_{tipo}_{'con' if consolidado else 'ind'}_{ano}.csv"
            if nome not in nomes:
                continue
            df = ler_csv_cvm(io.BytesIO(conteudo_zip.read(nome)))
            total += gravar_linhas(ctx, parse_demonstracao(df, documento, tipo, consolidado, cnpjs), empresas)
    nome_capital = f"{prefixo}_cia_aberta_composicao_capital_{ano}.csv"
    if nome_capital in nomes:
        df = ler_csv_cvm(io.BytesIO(conteudo_zip.read(nome_capital)))
        total += gravar_composicao(ctx, parse_composicao_capital(df, cnpjs), empresas)
    ctx.lote.linhas_gravadas = total
    return total


def ingerir(sessao, documento: str, ano: int) -> int:
    codigo = f"CVM_{documento}"
    url = URLS[documento].format(ano=ano)
    with lote(sessao, codigo, url) as ctx:
        caminho, ctx.lote.hash_arquivo = baixar(url, codigo)
        with zipfile.ZipFile(caminho) as z:
            return processar_zip(ctx, z, documento, ano)
