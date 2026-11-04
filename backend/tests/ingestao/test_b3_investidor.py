"""Extratos da Área do Investidor B3 (Negociação e Movimentação), montados como a B3 exporta."""

import io
from datetime import date, datetime

import pytest
from openpyxl import Workbook

from app.ingestao import b3_investidor as b3
from app.ingestao.base import EsquemaInesperado


def planilha(cabecalho, linhas) -> bytes:
    livro = Workbook()
    folha = livro.active
    folha.append(cabecalho)
    for linha in linhas:
        folha.append(linha)
    saida = io.BytesIO()
    livro.save(saida)
    return saida.getvalue()


def test_negociacao():
    conteudo = planilha(
        ["Data do Negócio", "Tipo de Movimentação", "Mercado", "Prazo/Vencimento", "Instituição",
         "Código de Negociação", "Quantidade", "Preço", "Valor"],
        [["02/01/2025", "Compra", "Mercado à Vista", "-", "CORRETORA", "PETR4", 100, 38.5, 3850],
         [datetime(2025, 1, 3), "Venda", "Mercado Fracionário", "-", "CORRETORA", "PETR4F", 5, "R$ 40,00", 200],
         ["04/01/2025", "Compra", "Mercado à Vista", "-", "CORRETORA", "XX", 1, 1, 1]])
    r = b3.ler(conteudo)
    assert r["tipo_arquivo"] == "NEGOCIACAO" and len(r["erros"]) == 1
    assert r["movimentos"] == [
        {"data": date(2025, 1, 2), "ticker": "PETR4", "tipo": "COMPRA", "quantidade": 100, "preco": 38.5},
        {"data": date(2025, 1, 3), "ticker": "PETR4", "tipo": "VENDA", "quantidade": 5, "preco": 40.0}]


def test_movimentacao():
    conteudo = planilha(
        ["Entrada/Saída", "Data", "Movimentação", "Produto", "Instituição", "Quantidade", "Preço unitário",
         "Valor da Operação"],
        [["Credito", "02/01/2025", "Transferência - Liquidação", "HGLG11 - CSHG LOGISTICA", "X", 10, 160.0, 1600],
         ["Debito", "10/01/2025", "Transferência - Liquidação", "HGLG11 - CSHG LOGISTICA", "X", 2, 165.0, 330],
         ["Credito", "15/01/2025", "Rendimento", "HGLG11 - CSHG LOGISTICA", "X", 8, 1.1, 8.8],
         ["Credito", "20/01/2025", "Desdobro", "BBAS3 - BANCO DO BRASIL", "X", 100, "-", "-"],
         ["Credito", "21/01/2025", "Bonificação em Ativos", "ITSA4 - ITAUSA", "X", 3, "-", "-"]])
    r = b3.ler(conteudo)
    assert r["tipo_arquivo"] == "MOVIMENTACAO" and r["ignoradas"] == 1 and r["erros"] == []
    assert [(m["ticker"], m["tipo"], m["quantidade"], m["preco"]) for m in r["movimentos"]] == [
        ("HGLG11", "COMPRA", 10, 160.0), ("HGLG11", "VENDA", 2, 165.0), ("BBAS3", "DESDOBRAMENTO", 100, 0.0),
        ("ITSA4", "BONIFICACAO", 3, 0.0)]


def test_arquivo_invalido():
    with pytest.raises(EsquemaInesperado, match="não é uma planilha"):
        b3.ler(b"texto qualquer")
    with pytest.raises(EsquemaInesperado, match="leiaute não reconhecido"):
        b3.ler(planilha(["A", "B"], [[1, 2]]))
    assert b3.ticker_do_produto("TAEE11 - TAESA") == "TAEE11" and b3.ticker_do_produto("Tesouro Selic 2029") is None
