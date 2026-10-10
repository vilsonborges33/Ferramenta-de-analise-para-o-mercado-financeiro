"""CVM: informe mensal estruturado de FII → `fii` e `fii_informe_mensal`.

Arquivo anual: https://dados.cvm.gov.br/dados/FII/DOC/INF_MENSAL/DADOS/inf_mensal_fii_AAAA.zip
com três CSVs: `_geral_` (cadastro), `_complemento_` (PL, cotas, cotistas, rentabilidade) e
`_ativo_passivo_` (composição do ativo e passivo).

Com a Resolução CVM 175 algumas colunas passaram a usar o sufixo "_Classe" (ex.: CNPJ_Fundo_Classe);
os dois nomes são aceitos. Colunas obrigatórias ausentes interrompem a ingestão.
"""

import io
import zipfile
from datetime import date

import pandas as pd
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.db.modelos import Fii, FiiInformeMensal
from app.ingestao.base import Contexto, EsquemaInesperado, baixar, data_br, decimal_br, lote
from app.ingestao.cotahist import ligar_fiis_por_isin
from app.ingestao.cvm_companhias import ler_csv_cvm

URL = "https://dados.cvm.gov.br/dados/FII/DOC/INF_MENSAL/DADOS/inf_mensal_fii_{ano}.zip"

ALTERNATIVAS = {
    "cnpj": ("CNPJ_Fundo_Classe", "CNPJ_Fundo"),
    "nome": ("Nome_Fundo_Classe", "Nome_Fundo"),
    "data": ("Data_Referencia",),
    "versao": ("Versao",),
}


def _coluna(df: pd.DataFrame, chave: str, arquivo: str) -> str:
    for nome in ALTERNATIVAS[chave]:
        if nome in df.columns:
            return nome
    raise EsquemaInesperado(f"{arquivo}: nenhuma das colunas {ALTERNATIVAS[chave]}")


def _normalizar(df: pd.DataFrame, arquivo: str) -> pd.DataFrame:
    """Renomeia as colunas-chave e mantém só a versão mais recente de cada (CNPJ, mês)."""
    df = df.rename(columns={_coluna(df, "cnpj", arquivo): "_cnpj", _coluna(df, "data", arquivo): "_data",
                            _coluna(df, "versao", arquivo): "_versao"})
    df["_versao"] = df["_versao"].astype(int)
    return df.sort_values("_versao").drop_duplicates(["_cnpj", "_data"], keep="last")


def _int(texto) -> int | None:
    v = decimal_br(texto)
    return None if v is None else int(v)


def _get(linha: dict, *nomes):
    for n in nomes:
        if n in linha and str(linha[n]).strip() != "":
            return linha[n]
    return None


def parse(geral: pd.DataFrame, complemento: pd.DataFrame, ativo_passivo: pd.DataFrame) -> tuple[list, list]:
    geral = _normalizar(geral, "geral")
    complemento = _normalizar(complemento, "complemento")
    ativo_passivo = _normalizar(ativo_passivo, "ativo_passivo")
    coluna_nome = _coluna(geral, "nome", "geral")

    fundos = {}
    for linha in geral.sort_values("_data").to_dict("records"):
        fundos[linha["_cnpj"]] = {  # fica o cadastro do mês mais recente
            "cnpj": linha["_cnpj"],
            "nome": linha[coluna_nome].strip(),
            "isin": (_get(linha, "Codigo_ISIN") or "").strip() or None,
            "segmento": _get(linha, "Segmento_Atuacao"),
            "mandato": _get(linha, "Mandato"),
            "tipo_gestao": _get(linha, "Tipo_Gestao"),
            "administrador": _get(linha, "Nome_Administrador"),
            "publico_alvo": _get(linha, "Publico_Alvo"),
            "data_inicio": data_br(_get(linha, "Data_Funcionamento")),
            "data_referencia": data_br(linha["_data"]),
        }

    ap = {(lin["_cnpj"], lin["_data"]): lin for lin in ativo_passivo.to_dict("records")}
    informes = []
    for linha in complemento.to_dict("records"):
        a = ap.get((linha["_cnpj"], linha["_data"]), {})
        informes.append({
            "cnpj": linha["_cnpj"],
            "competencia": data_br(linha["_data"]),
            "versao": linha["_versao"],
            "patrimonio_liquido": decimal_br(_get(linha, "Patrimonio_Liquido")),
            "cotas_emitidas": decimal_br(_get(linha, "Cotas_Emitidas")),
            "valor_patrimonial_cota": decimal_br(_get(linha, "Valor_Patrimonial_Cotas")),
            "numero_cotistas": _int(_get(linha, "Total_Numero_Cotistas")),
            "cotistas_pf": _int(_get(linha, "Numero_Cotistas_Pessoa_Fisica")),
            "cotistas_pj": _int(_get(linha, "Numero_Cotistas_Pessoa_Juridica_Nao_Financeira")),
            "cotistas_bancos": _int(_get(linha, "Numero_Cotistas_Banco_Comercial")),
            "rentabilidade_efetiva_mes": decimal_br(_get(linha, "Percentual_Rentabilidade_Efetiva_Mes")),
            "rentabilidade_patrimonial_mes": decimal_br(_get(linha, "Percentual_Rentabilidade_Patrimonial_Mes")),
            "dividend_yield_mes": decimal_br(_get(linha, "Percentual_Dividend_Yield_Mes")),
            "taxa_administracao_mes": decimal_br(_get(linha, "Percentual_Despesas_Taxa_Administracao")),
            "ativo_total": decimal_br(_get(linha, "Valor_Ativo")),
            "imoveis_renda_acabados": decimal_br(_get(a, "Imoveis_Renda_Acabados")),
            "imoveis_renda_construcao": decimal_br(_get(a, "Imoveis_Renda_Construcao")),
            "imoveis_venda": decimal_br(_get(a, "Imoveis_Venda_Acabados")),
            "caixa": decimal_br(_get(a, "Disponibilidades")),
            "total_passivo": decimal_br(_get(a, "Total_Passivo")),
            "rendimentos_a_distribuir": decimal_br(_get(a, "Rendimentos_Distribuir")),
            "obrigacoes_aquisicao_imoveis": decimal_br(_get(a, "Obrigacoes_Aquisicao_Imoveis")),
            # Linha completa do ativo/passivo para a composição detalhada (Fase 5).
            "extras": {k: v for k, v in a.items() if not k.startswith("_")} or None,
        })
    return list(fundos.values()), informes


def gravar(ctx: Contexto, fundos: list[dict], informes: list[dict]) -> int:
    for f in fundos:
        valores = {**f, **ctx.procedencia(f["data_referencia"])}
        stmt = insert(Fii).values(**valores)
        stmt = stmt.on_conflict_do_update(index_elements=["cnpj"],
                                          set_={k: stmt.excluded[k] for k in valores if k != "cnpj"})
        ctx.sessao.execute(stmt)
    ids = {cnpj: id_ for cnpj, id_ in ctx.sessao.execute(select(Fii.cnpj, Fii.id))}
    gravados = 0
    for i in informes:
        fii_id = ids.get(i["cnpj"])
        if fii_id is None:
            continue
        valores = {k: v for k, v in i.items() if k != "cnpj"}
        valores.update(fii_id=fii_id, **ctx.procedencia(i["competencia"]))
        stmt = insert(FiiInformeMensal).values(**valores)
        stmt = stmt.on_conflict_do_update(
            index_elements=["fii_id", "competencia", "versao"],
            set_={k: stmt.excluded[k] for k in valores if k not in ("fii_id", "competencia", "versao")})
        ctx.sessao.execute(stmt)
        gravados += 1
    ligar_fiis_por_isin(ctx.sessao)
    ctx.lote.linhas_gravadas = gravados
    return gravados


def _ler(z: zipfile.ZipFile, parte: str, ano: int) -> pd.DataFrame:
    return ler_csv_cvm(io.BytesIO(z.read(f"inf_mensal_fii_{parte}_{ano}.csv")))


def ingerir(sessao, ano: int | None = None) -> int:
    ano = ano or date.today().year
    caminho, sha = baixar(URL.format(ano=ano), "CVM_FII_MENSAL")
    with zipfile.ZipFile(caminho) as z, lote(sessao, "CVM_FII_MENSAL", str(caminho)) as ctx:
        ctx.lote.hash_arquivo = sha
        fundos, informes = parse(_ler(z, "geral", ano), _ler(z, "complemento", ano), _ler(z, "ativo_passivo", ano))
        return gravar(ctx, fundos, informes)
