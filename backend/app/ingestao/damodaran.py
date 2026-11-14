"""Damodaran Online: prêmio de risco de mercado (maduro e dos EUA) e prêmio de risco país do Brasil.

Fonte: planilha pública "Country Default Spreads and Risk Premiums" do prof. Aswath Damodaran (NYU Stern),
atualizada em janeiro e julho: https://pages.stern.nyu.edu/~adamodar/pc/datasets/ctryprem.xlsx
Aba "ERPs by country": data da atualização (B2), prêmio maduro (E3), prêmio dos EUA (E4) e, por país,
spread de default pelo rating (coluna D) e prêmio de risco país (coluna F).

Séries gravadas (em % a.a., datadas na atualização da planilha):
- DAMODARAN_ERP_MADURO, DAMODARAN_ERP_EUA, DAMODARAN_CRP_BRASIL e DAMODARAN_SPREAD_BRASIL.
"""

import io
from datetime import date, datetime

import openpyxl
from sqlalchemy.dialects.postgresql import insert

from app.db.modelos import SerieEconomica
from app.ingestao.base import EsquemaInesperado, cliente_http, lote

URL = "https://pages.stern.nyu.edu/~adamodar/pc/datasets/ctryprem.xlsx"
ABA = "ERPs by country"


def parse(conteudo: bytes) -> tuple[date, dict[str, float]]:
    """(data da atualização, {código da série: valor em % a.a.})."""
    try:
        planilha = openpyxl.load_workbook(io.BytesIO(conteudo), read_only=True, data_only=True)
    except Exception as erro:  # noqa: BLE001
        raise EsquemaInesperado(f"Damodaran: planilha ilegível ({erro!r})") from erro
    if ABA not in planilha.sheetnames:
        raise EsquemaInesperado(f"Damodaran: aba '{ABA}' não encontrada ({planilha.sheetnames[:5]})")
    linhas = list(planilha[ABA].iter_rows(values_only=True))
    data_ref = linhas[1][1] if len(linhas) > 1 else None
    maduro = linhas[2][4] if len(linhas) > 2 else None
    eua = linhas[3][4] if len(linhas) > 3 else None
    brasil = next((lin for lin in linhas if lin and str(lin[0] or "").strip() == "Brazil"), None)
    if not isinstance(data_ref, datetime) or not isinstance(maduro, int | float) or brasil is None:
        raise EsquemaInesperado("Damodaran: a aba 'ERPs by country' mudou de formato")
    spread, crp = brasil[3], brasil[5]
    if not isinstance(spread, int | float) or not isinstance(crp, int | float):
        raise EsquemaInesperado("Damodaran: linha do Brasil sem spread ou prêmio de risco país")
    valores = {"DAMODARAN_ERP_MADURO": maduro, "DAMODARAN_CRP_BRASIL": crp, "DAMODARAN_SPREAD_BRASIL": spread}
    if isinstance(eua, int | float):
        valores["DAMODARAN_ERP_EUA"] = eua
    return data_ref.date(), {k: float(v) * 100 for k, v in valores.items()}


def ingerir(sessao, cliente=None) -> int:
    proprio = cliente is None
    cliente = cliente or cliente_http()
    try:
        with lote(sessao, "DAMODARAN", URL) as ctx:
            resposta = cliente.get(URL)
            resposta.raise_for_status()
            data_ref, valores = parse(resposta.content)
            for codigo, valor in valores.items():
                linha = {"codigo": codigo, "data": data_ref, "valor": valor, **ctx.procedencia(data_ref)}
                stmt = insert(SerieEconomica).values(**linha)
                sessao.execute(stmt.on_conflict_do_update(
                    index_elements=["codigo", "data"],
                    set_={k: stmt.excluded[k] for k in linha if k not in ("codigo", "data")}))
            ctx.lote.linhas_gravadas = len(valores)
            return len(valores)
    finally:
        if proprio:
            cliente.close()
