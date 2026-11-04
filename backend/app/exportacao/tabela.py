"""Exporta tabelas (screening, favoritos) para .csv e .xlsx, com fonte, data e aviso de não recomendação."""

import csv
import io
from dataclasses import dataclass

from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter


@dataclass(frozen=True)
class Coluna:
    chave: str
    titulo: str
    formato: str = "texto"  # texto | numero | percentual | moeda


def _rodape(aviso: str, fonte: str, atualizado_em: str | None) -> list[str]:
    return [aviso, f"Fontes: {fonte}", f"Cotações até {atualizado_em or '—'}"]


def para_csv(linhas: list[dict], colunas: list[Coluna], aviso: str, fonte: str, atualizado_em: str | None) -> bytes:
    """CSV no padrão do Excel em português: separador ';', vírgula decimal e BOM UTF-8."""
    saida = io.StringIO()
    escritor = csv.writer(saida, delimiter=";")
    escritor.writerow([c.titulo for c in colunas])
    for linha in linhas:
        valores = []
        for c in colunas:
            v = linha.get(c.chave)
            if v is None:
                valores.append("")
            elif isinstance(v, float):
                valores.append(f"{v:.6f}".rstrip("0").rstrip(".").replace(".", ","))
            else:
                valores.append(str(v))
        escritor.writerow(valores)
    escritor.writerow([])
    for texto in _rodape(aviso, fonte, atualizado_em):
        escritor.writerow([texto])
    return ("﻿" + saida.getvalue()).encode("utf-8")


_FORMATOS_XLSX = {"numero": "#,##0.00", "percentual": "0.00%", "moeda": '"R$" #,##0.00'}


def para_xlsx(linhas: list[dict], colunas: list[Coluna], aviso: str, fonte: str, atualizado_em: str | None,
              titulo: str = "Screening", moeda: str = "BRL") -> bytes:
    formatos = {**_FORMATOS_XLSX, "moeda": '"US$" #,##0.00' if moeda == "USD" else _FORMATOS_XLSX["moeda"]}
    livro = Workbook()
    folha = livro.active
    folha.title = titulo[:31]
    folha.append([c.titulo for c in colunas])
    for celula in folha[1]:
        celula.font = Font(bold=True)
    for linha in linhas:
        folha.append([linha.get(c.chave) for c in colunas])
    for i, c in enumerate(colunas, start=1):
        if c.formato in formatos:
            for (celula,) in folha.iter_rows(min_row=2, max_row=len(linhas) + 1, min_col=i, max_col=i):
                celula.number_format = formatos[c.formato]
        folha.column_dimensions[get_column_letter(i)].width = max(10, len(c.titulo) + 2)
    folha.freeze_panes = "B2"
    folha.append([])
    for texto in _rodape(aviso, fonte, atualizado_em):
        folha.append([texto])
    saida = io.BytesIO()
    livro.save(saida)
    return saida.getvalue()

