"""CVM: cadastro de companhias abertas e valores mobiliários (FCA) → `empresa` e `ativo`.

Arquivos (Dados Abertos CVM, ODbL):
- https://dados.cvm.gov.br/dados/CIA_ABERTA/CAD/DADOS/cad_cia_aberta.csv
- https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/FCA/DADOS/fca_cia_aberta_AAAA.zip
  (contém fca_cia_aberta_valor_mobiliario_AAAA.csv com os códigos de negociação)
"""

import io
import re
import zipfile
from datetime import date
from pathlib import Path

import pandas as pd
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.db.modelos import Ativo, Empresa
from app.ingestao.base import Contexto, baixar, data_br, exigir_colunas, lote

URL_CADASTRO = "https://dados.cvm.gov.br/dados/CIA_ABERTA/CAD/DADOS/cad_cia_aberta.csv"
URL_FCA = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/FCA/DADOS/fca_cia_aberta_{ano}.zip"

COLUNAS_CADASTRO = {"CNPJ_CIA", "DENOM_SOCIAL", "CD_CVM", "SIT", "SETOR_ATIV", "DT_REG"}
COLUNAS_VALOR_MOBILIARIO = {"CNPJ_Companhia", "Data_Referencia", "Valor_Mobiliario", "Codigo_Negociacao",
                            "Mercado", "Segmento"}

# Setores do cadastro CVM que usam plano de contas de instituição financeira/seguradora.
SETORES_BANCO = ("Bancos", "Intermediação Financeira")
SETORES_SEGURADORA = ("Seguradoras e Corretoras",)


def ler_csv_cvm(conteudo: bytes | io.BytesIO | Path) -> pd.DataFrame:
    return pd.read_csv(conteudo, sep=";", encoding="latin-1", dtype=str, keep_default_na=False)


def tipo_plano(setor: str | None) -> str:
    setor = setor or ""
    if any(s in setor for s in SETORES_BANCO):
        return "banco"
    if any(s in setor for s in SETORES_SEGURADORA):
        return "seguradora"
    return "geral"


def parse_cadastro(df: pd.DataFrame) -> list[dict]:
    exigir_colunas(df.columns, COLUNAS_CADASTRO, "cad_cia_aberta.csv")
    # O cadastro pode repetir o CNPJ (registros cancelados); fica o mais recente.
    df = df.sort_values("DT_REG").drop_duplicates("CNPJ_CIA", keep="last")
    df = df.drop_duplicates("CD_CVM", keep="last")
    registros = []
    for _, linha in df.iterrows():
        registros.append({
            "cnpj": linha["CNPJ_CIA"],
            "nome": linha["DENOM_SOCIAL"].strip(),
            "codigo_cvm": linha["CD_CVM"].lstrip("0") or "0",
            "situacao": linha["SIT"] or None,
            "setor": linha["SETOR_ATIV"] or None,
            "tipo_plano_contas": tipo_plano(linha["SETOR_ATIV"]),
            "data_referencia": data_br(linha["DT_REG"]) or date.today(),
        })
    return registros


def especie_por_ticker(ticker: str, valor_mobiliario: str) -> tuple[str, str]:
    """Classe e espécie a partir do sufixo do ticker B3 (3 = ON, 4/5/6/7/8 = PN, 11 = unit)."""
    if ticker.endswith("11") and "Unit" in valor_mobiliario:
        return "UNIT", "UNIT"
    if ticker.endswith("3"):
        return "ACAO", "ON"
    if ticker[-1] in "45678":
        return "ACAO", "PN"
    return "ACAO", "ON" if "Ordin" in valor_mobiliario else "PN"


# Ticker de ação/unit/BDR na B3: 4 letras + 1 ou 2 dígitos (ex.: PETR4, TAEE11, AAPL34).
PADRAO_TICKER_B3 = re.compile(r"^[A-Z]{4}\d{1,2}$")


def ticker_valido(ticker: str) -> bool:
    return bool(PADRAO_TICKER_B3.match(ticker))


def parse_valores_mobiliarios(df: pd.DataFrame) -> list[dict]:
    exigir_colunas(df.columns, COLUNAS_VALOR_MOBILIARIO, "fca_cia_aberta_valor_mobiliario")
    df = df[(df["Codigo_Negociacao"].str.strip() != "")
            & (df["Valor_Mobiliario"].str.contains("Ações|Units|Certificado de Depósito", regex=True))
            & (df["Mercado"].str.contains("Bolsa", na=False))]
    if "Data_Fim_Negociacao" in df.columns:
        df = df[df["Data_Fim_Negociacao"].str.strip() == ""]
    registros = []
    for _, linha in df.iterrows():
        ticker = linha["Codigo_Negociacao"].strip().upper()
        if not ticker_valido(ticker):  # códigos de outros mercados (ex.: "8192") não são tickers da B3
            continue
        classe, especie = especie_por_ticker(ticker, linha["Valor_Mobiliario"])
        registros.append({
            "ticker": ticker,
            "cnpj": linha["CNPJ_Companhia"],
            "classe": classe,
            "especie": especie,
            "segmento_listagem": linha["Segmento"].strip() or None,
        })
    return registros


def gravar_cadastro(ctx: Contexto, registros: list[dict]) -> int:
    for r in registros:
        valores = {**r, **ctx.procedencia(r["data_referencia"])}
        stmt = insert(Empresa).values(**valores)
        stmt = stmt.on_conflict_do_update(
            index_elements=["cnpj"],
            set_={k: stmt.excluded[k] for k in valores if k != "cnpj"},
        )
        ctx.sessao.execute(stmt)
    ctx.lote.linhas_gravadas = len(registros)
    return len(registros)


def gravar_valores_mobiliarios(ctx: Contexto, registros: list[dict]) -> int:
    por_cnpj = {e.cnpj: e for e in ctx.sessao.scalars(select(Empresa))}
    gravados = 0
    for r in registros:
        empresa = por_cnpj.get(r["cnpj"])
        if empresa is None:
            continue
        if r["segmento_listagem"]:
            empresa.segmento_listagem = r["segmento_listagem"]
        stmt = insert(Ativo).values(ticker=r["ticker"], empresa_id=empresa.id, classe=r["classe"],
                                    especie=r["especie"], mercado="B3", moeda="BRL", ativo=True)
        stmt = stmt.on_conflict_do_update(
            index_elements=["ticker"],
            set_={"empresa_id": empresa.id, "classe": r["classe"], "especie": r["especie"]},
        )
        ctx.sessao.execute(stmt)
        gravados += 1
    # Desativa códigos inválidos gravados por versões anteriores.
    for ativo in ctx.sessao.scalars(select(Ativo).where(Ativo.classe.in_(("ACAO", "UNIT")), Ativo.ativo.is_(True))):
        if not ticker_valido(ativo.ticker):
            ativo.ativo = False
    ctx.lote.linhas_gravadas = gravados
    return gravados


def ingerir_cadastro(sessao) -> int:
    with lote(sessao, "CVM_CADASTRO", URL_CADASTRO) as ctx:
        caminho, ctx.lote.hash_arquivo = baixar(URL_CADASTRO, "CVM_CADASTRO")
        return gravar_cadastro(ctx, parse_cadastro(ler_csv_cvm(caminho)))


def ingerir_valores_mobiliarios(sessao, ano: int) -> int:
    url = URL_FCA.format(ano=ano)
    with lote(sessao, "CVM_FCA", url) as ctx:
        caminho, ctx.lote.hash_arquivo = baixar(url, "CVM_FCA")
        z = zipfile.ZipFile(caminho)
        nome = f"fca_cia_aberta_valor_mobiliario_{ano}.csv"
        df = ler_csv_cvm(io.BytesIO(z.read(nome)))
        return gravar_valores_mobiliarios(ctx, parse_valores_mobiliarios(df))
