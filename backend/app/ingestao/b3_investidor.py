"""Importação dos extratos da Área do Investidor da B3 (arquivo .xlsx exportado pelo próprio usuário).

Dois leiautes são reconhecidos pelos cabeçalhos:
- **Negociação** ("Data do Negócio", "Tipo de Movimentação", "Código de Negociação", "Quantidade", "Preço"):
  compras e vendas.
- **Movimentação** ("Entrada/Saída", "Data", "Movimentação", "Produto", "Quantidade", "Preço unitário"):
  liquidações de compra e venda, desdobramentos, bonificações e grupamentos. Proventos, empréstimos, leilões
  de frações etc. são ignorados (os proventos vêm da fonte de mercado).
Use um dos dois arquivos para o mesmo período: as liquidações da Movimentação repetem as compras da Negociação.
"""

import io
import re
import unicodedata
from datetime import date, datetime

from openpyxl import load_workbook

from app.ingestao.base import EsquemaInesperado


def _norm(texto) -> str:
    t = unicodedata.normalize("NFD", str(texto or "").strip().lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def _numero(valor) -> float | None:
    if valor is None:
        return None
    if isinstance(valor, int | float):
        return float(valor)
    t = str(valor).replace("R$", "").strip()
    if t in ("", "-"):
        return None
    t = t.replace(".", "").replace(",", ".") if "," in t else t
    try:
        return float(t)
    except ValueError:
        return None


def _data(valor) -> date | None:
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    m = re.match(r"(\d{2})/(\d{2})/(\d{4})", str(valor or "").strip())
    return date(int(m[3]), int(m[2]), int(m[1])) if m else None


def ticker_do_produto(produto: str) -> str | None:
    """'PETR4 - PETROLEO BRASILEIRO S.A.' → PETR4; mercado fracionário 'PETR4F' → PETR4."""
    codigo = str(produto or "").split(" - ")[0].strip().upper()
    if not re.fullmatch(r"[A-Z]{4}\d{1,2}F?", codigo):
        return None
    return codigo[:-1] if codigo.endswith("F") else codigo


def _linhas(conteudo: bytes) -> tuple[list[str], list[tuple]]:
    try:
        planilha = load_workbook(io.BytesIO(conteudo), read_only=True, data_only=True).worksheets[0]
    except Exception as erro:  # arquivo que não é .xlsx
        raise EsquemaInesperado("arquivo não é uma planilha .xlsx da B3") from erro
    linhas = list(planilha.iter_rows(values_only=True))
    if not linhas:
        raise EsquemaInesperado("planilha vazia")
    return [_norm(c) for c in linhas[0]], linhas[1:]


MOVIMENTACOES = {
    "transferencia - liquidacao": ("COMPRA", "VENDA"),
    "compra": ("COMPRA", None),
    "venda": (None, "VENDA"),
    "desdobro": ("DESDOBRAMENTO", None),
    "bonificacao em ativos": ("BONIFICACAO", None),
    "grupamento": (None, "GRUPAMENTO"),
}


def ler(conteudo: bytes) -> dict:
    """Devolve {tipo_arquivo, movimentos: [{data, ticker, tipo, quantidade, preco}], ignoradas, erros}."""
    cab, linhas = _linhas(conteudo)
    col = {nome: i for i, nome in enumerate(cab)}

    def pega(lin: tuple, nome: str):
        return lin[col[nome]] if nome in col and col[nome] < len(lin) else None

    movimentos, erros, ignoradas = [], [], 0
    if "data do negocio" in col and "codigo de negociacao" in col:
        tipo_arquivo = "NEGOCIACAO"
        for n, lin in enumerate(linhas, start=2):
            if not any(lin):
                continue
            d = _data(pega(lin, "data do negocio"))
            tipo = _norm(pega(lin, "tipo de movimentacao"))
            ticker = ticker_do_produto(pega(lin, "codigo de negociacao"))
            qtd, preco = _numero(pega(lin, "quantidade")), _numero(pega(lin, "preco"))
            if tipo not in ("compra", "venda"):
                ignoradas += 1
                continue
            if not (d and ticker and qtd and preco is not None):
                erros.append(f"linha {n}: data, código, quantidade ou preço inválido")
                continue
            movimentos.append({"data": d, "ticker": ticker, "tipo": tipo.upper(), "quantidade": qtd, "preco": preco})
    elif "movimentacao" in col and "produto" in col and "entrada/saida" in col:
        tipo_arquivo = "MOVIMENTACAO"
        for n, lin in enumerate(linhas, start=2):
            if not any(lin):
                continue
            regra = MOVIMENTACOES.get(_norm(pega(lin, "movimentacao")))
            entrada = _norm(pega(lin, "entrada/saida")).startswith("credito")
            tipo = regra[0 if entrada else 1] if regra else None
            if tipo is None:
                ignoradas += 1  # proventos, empréstimos, leilões de frações, atualizações…
                continue
            d = _data(pega(lin, "data"))
            ticker = ticker_do_produto(pega(lin, "produto"))
            qtd = _numero(pega(lin, "quantidade"))
            preco = _numero(pega(lin, "preco unitario"))
            if not (d and ticker and qtd):
                erros.append(f"linha {n}: data, produto ou quantidade inválido")
                continue
            if tipo in ("COMPRA", "VENDA") and preco is None:
                erros.append(f"linha {n}: liquidação sem preço unitário")
                continue
            movimentos.append({"data": d, "ticker": ticker, "tipo": tipo, "quantidade": qtd, "preco": preco or 0.0})
    else:
        raise EsquemaInesperado("leiaute não reconhecido: use o extrato de Negociação ou de Movimentação da B3")
    return {"tipo_arquivo": tipo_arquivo, "movimentos": movimentos, "ignoradas": ignoradas, "erros": erros}
