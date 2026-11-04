"""CVM — informe trimestral de FII: imóveis de cada fundo, com área, vacância, inadimplência e peso na receita.

Arquivo: https://dados.cvm.gov.br/dados/FII/DOC/INF_TRIMESTRAL/DADOS/inf_trimestral_fii_{ano}.zip (ODbL).
O pacote traz vários CSVs; entram os que descrevem imóveis e têm coluna de vacância. As colunas são achadas
pelo nome (sem depender da posição), e percentuais informados em 0–100 são convertidos para fração.
"""

import io
import zipfile
from datetime import date

import pandas as pd
from sqlalchemy import delete, select

from app.db.modelos import Fii, FiiImovel
from app.ingestao.base import Contexto, EsquemaInesperado, baixar, data_br, decimal_br, lote
from app.ingestao.cvm_companhias import ler_csv_cvm

URL = "https://dados.cvm.gov.br/dados/FII/DOC/INF_TRIMESTRAL/DADOS/inf_trimestral_fii_{ano}.zip"

# campo → pedaços que identificam a coluna (o primeiro que casar vence)
CAMPOS = {
    "cnpj": ("cnpj_fundo_classe", "cnpj_fundo", "cnpj"),
    "data": ("data_referencia",),
    "versao": ("versao",),
    "nome": ("nome_imovel", "nome"),
    "endereco": ("endereco",),
    "classe": ("classe",),
    "area_m2": ("area",),
    "numero_unidades": ("numero_unidades", "unidades"),
    "percentual_vacancia": ("vacancia",),
    "percentual_inadimplencia": ("inadimplencia",),
    "percentual_receitas_fii": ("receitas_fii", "receita"),
}
PERCENTUAIS = ("percentual_vacancia", "percentual_inadimplencia", "percentual_receitas_fii")


def _mapa(colunas: list[str]) -> dict[str, str]:
    minusculas = {c.lower(): c for c in colunas}
    mapa = {}
    for campo, pedacos in CAMPOS.items():
        for pedaco in pedacos:
            achada = next((orig for low, orig in minusculas.items() if pedaco in low and orig not in mapa.values()),
                          None)
            if achada:
                mapa[campo] = achada
                break
    return mapa


def parse(df: pd.DataFrame, arquivo: str) -> list[dict]:
    """Linhas de imóveis; vazio se o CSV não for de imóveis (sem coluna de vacância)."""
    mapa = _mapa(list(df.columns))
    if "percentual_vacancia" not in mapa:
        return []
    for obrigatoria in ("cnpj", "data", "nome"):
        if obrigatoria not in mapa:
            raise EsquemaInesperado(f"{arquivo}: coluna de {obrigatoria} não encontrada")
    linhas = df.to_dict("records")
    if "versao" in mapa:  # só a versão mais recente de cada (fundo, trimestre)
        maior: dict[tuple, int] = {}
        for lin in linhas:
            chave = (lin[mapa["cnpj"]], lin[mapa["data"]])
            maior[chave] = max(maior.get(chave, 0), int(lin[mapa["versao"]] or 0))
        linhas = [lin for lin in linhas
                  if int(lin[mapa["versao"]] or 0) == maior[(lin[mapa["cnpj"]], lin[mapa["data"]])]]
    saida = []
    for lin in linhas:
        nome = str(lin[mapa["nome"]]).strip()
        competencia = data_br(lin[mapa["data"]])
        if not nome or competencia is None:
            continue
        item = {"cnpj": str(lin[mapa["cnpj"]]).strip(), "competencia": competencia, "nome": nome[:300]}
        for campo in ("endereco", "classe"):
            if campo in mapa:
                item[campo] = (str(lin[mapa[campo]]).strip() or None)
                item[campo] = item[campo][:500 if campo == "endereco" else 50] if item[campo] else None
        for campo in ("area_m2", "numero_unidades", *PERCENTUAIS):
            if campo in mapa:
                v = decimal_br(lin[mapa[campo]])
                item[campo] = int(v) if campo == "numero_unidades" and v is not None else v
        saida.append(item)
    # Percentuais em 0–100 (ex.: "12,5") viram fração; arquivo já em fração (≤ 1) fica como está.
    for campo in PERCENTUAIS:
        valores = [i[campo] for i in saida if i.get(campo) is not None]
        if valores and max(valores) > 1:
            for i in saida:
                if i.get(campo) is not None:
                    i[campo] = i[campo] / 100
    return saida


def gravar(ctx: Contexto, imoveis: list[dict]) -> int:
    ids = {cnpj: id_ for cnpj, id_ in ctx.sessao.execute(select(Fii.cnpj, Fii.id))}
    por_fundo: dict[tuple[int, date], list[dict]] = {}
    for i in imoveis:
        fii_id = ids.get(i["cnpj"])
        if fii_id is not None:
            por_fundo.setdefault((fii_id, i["competencia"]), []).append(i)
    for (fii_id, competencia), lista in por_fundo.items():  # reprocessar substitui o trimestre inteiro
        ctx.sessao.execute(delete(FiiImovel).where(FiiImovel.fii_id == fii_id, FiiImovel.competencia == competencia))
        for i in lista:
            valores = {k: v for k, v in i.items() if k != "cnpj"}
            ctx.sessao.add(FiiImovel(fii_id=fii_id, **valores, **ctx.procedencia(competencia)))
    gravados = sum(len(v) for v in por_fundo.values())
    ctx.lote.linhas_gravadas = gravados
    return gravados


def processar_zip(ctx: Contexto, z: zipfile.ZipFile) -> int:
    imoveis = []
    for nome in z.namelist():
        if nome.lower().endswith(".csv") and "imovel" in nome.lower():
            imoveis += parse(ler_csv_cvm(io.BytesIO(z.read(nome))), nome)
    if not imoveis:
        raise EsquemaInesperado("informe trimestral sem tabela de imóveis com vacância")
    return gravar(ctx, imoveis)


def ingerir(sessao, ano: int | None = None) -> int:
    ano = ano or date.today().year
    url = URL.format(ano=ano)
    with lote(sessao, "CVM_FII_TRIMESTRAL", url) as ctx:
        caminho, ctx.lote.hash_arquivo = baixar(url, "CVM_FII_TRIMESTRAL")
        return processar_zip(ctx, zipfile.ZipFile(caminho))
