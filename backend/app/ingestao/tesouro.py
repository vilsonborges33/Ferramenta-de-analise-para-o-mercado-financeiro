"""Tesouro Transparente — "Taxas dos Títulos Ofertados pelo Tesouro Direto" (CSV oficial).

O endpoint JSON do site do Tesouro Direto não é API oficial e não é usado (DECISOES.md D-010).
URL do recurso CSV: a confirmar na página do dataset na primeira execução real.
"""

import pandas as pd
from sqlalchemy.dialects.postgresql import insert

from app.db.modelos import TituloTesouroTaxa
from app.ingestao.base import Contexto, baixar, data_br, decimal_br, exigir_colunas, lote

URL = ("https://www.tesourotransparente.gov.br/ckan/dataset/df56aa42-484a-4a59-8184-7676580c81e3/resource/"
       "796d2059-14e9-44e3-80c9-2d9e30b405c1/download/PrecoTaxaTesouroDireto.csv")
COLUNAS = {"Tipo Titulo", "Data Vencimento", "Data Base", "Taxa Compra Manha", "Taxa Venda Manha",
           "PU Compra Manha", "PU Venda Manha"}


def parse(df: pd.DataFrame, desde=None) -> list[dict]:
    exigir_colunas(df.columns, COLUNAS, "PrecoTaxaTesouroDireto.csv")
    registros = []
    for linha in df.itertuples(index=False):
        valores = dict(zip(df.columns, linha, strict=True))
        data_base = data_br(valores["Data Base"])
        if desde is not None and data_base < desde:
            continue
        registros.append({
            "titulo": valores["Tipo Titulo"].strip(),
            "vencimento": data_br(valores["Data Vencimento"]),
            "data_base": data_base,
            "taxa_compra": decimal_br(valores["Taxa Compra Manha"]),
            "taxa_venda": decimal_br(valores["Taxa Venda Manha"]),
            "pu_compra": decimal_br(valores["PU Compra Manha"]),
            "pu_venda": decimal_br(valores["PU Venda Manha"]),
        })
    return registros


def gravar(ctx: Contexto, registros: list[dict]) -> int:
    linhas = [{**r, **ctx.procedencia(r["data_base"])} for r in registros]
    for i in range(0, len(linhas), 5000):
        bloco = linhas[i:i + 5000]
        stmt = insert(TituloTesouroTaxa)
        stmt = stmt.on_conflict_do_update(
            index_elements=["titulo", "vencimento", "data_base"],
            set_={c: stmt.excluded[c] for c in ("taxa_compra", "taxa_venda", "pu_compra", "pu_venda",
                                                 "lote_ingestao_id", "coletado_em")})
        ctx.sessao.execute(stmt, bloco)
    ctx.lote.linhas_gravadas = len(linhas)
    return len(linhas)


def ingerir(sessao, desde=None) -> int:
    with lote(sessao, "TESOURO_TD", URL) as ctx:
        caminho, ctx.lote.hash_arquivo = baixar(URL, "TESOURO_TD")
        df = pd.read_csv(caminho, sep=";", encoding="latin-1", dtype=str, keep_default_na=False)
        return gravar(ctx, parse(df, desde))
