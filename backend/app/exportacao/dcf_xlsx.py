"""Exporta um DCF (FCFF ou FCFE) para .xlsx com fórmulas abertas: mudar uma premissa recalcula a planilha.

Aba "Premissas": valores editáveis. Aba "DCF": projeção ano a ano, valor terminal e valor por ação, tudo em
fórmulas que apontam para as premissas. O valor calculado pelo sistema fica ao lado, para conferência.
"""

import io

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

_ENTRADA = PatternFill("solid", fgColor="FFF4D6")  # células editáveis
_PCT, _RS, _NUM = "0.00%", '"R$" #,##0.00', "#,##0"


def dcf_para_xlsx(resultado: dict, ticker: str, acoes: float | None, aviso: str, fontes: str) -> bytes:
    p = resultado["premissas"]
    fcfe = resultado["metodo"] == "dcf_fcfe"
    n = len(p["crescimento_receita"])
    livro = Workbook()

    pr = livro.active
    pr.title = "Premissas"
    linhas = [
        ("Receita base (R$)", p["receita_base"], _NUM), ("Margem EBIT", p["margem_ebit"], _PCT),
        ("Alíquota de IR/CSLL", p["aliquota"], _PCT), ("D&A (% da receita)", p["da_pct_receita"], _PCT),
        ("Capex (% da receita)", p["capex_pct_receita"], _PCT),
        ("Capital de giro (% do aumento da receita)", p["capital_giro_pct_variacao_receita"], _PCT),
        ("Taxa de desconto (" + ("Ke" if fcfe else "WACC") + ")", p["taxa_desconto"], _PCT),
        ("Crescimento perpétuo", p["crescimento_perpetuo"], _PCT),
        ("Dívida líquida (R$)", 0 if fcfe else p["divida_liquida"], _NUM),
        ("Ações em circulação", acoes, _NUM), ("Cotação (R$)", resultado.get("preco"), _RS),
        ("Juros anuais (R$, só FCFE)", p.get("juros_anuais", 0), _NUM),
        ("Nova dívida por ano (R$, só FCFE)", p.get("nova_divida_anual", 0), _NUM),
    ]
    pr.append([f"{ticker} — {resultado['nome']}", ""])
    pr["A1"].font = Font(bold=True)
    celula = {}
    for i, (rotulo, valor, formato) in enumerate(linhas, start=2):
        pr.cell(i, 1, rotulo)
        c = pr.cell(i, 2, valor)
        c.number_format, c.fill = formato, _ENTRADA
        celula[rotulo.split(" (")[0]] = f"Premissas!$B${i}"
    pr.column_dimensions["A"].width = 44
    pr.column_dimensions["B"].width = 20
    pr.append([])
    pr.append(["Células amarelas são editáveis; a aba DCF recalcula sozinha."])
    pr.append([aviso])
    pr.append([f"Fontes: {fontes}"])
    ref = lambda chave: celula[chave]  # noqa: E731

    d = livro.create_sheet("DCF")
    d["A1"] = "Ano"
    d["B1"] = "Base"
    rotulos = ["Crescimento da receita", "Receita", "EBIT", "NOPAT", "D&A", "Capex", "Variação do capital de giro",
               "FCFF"]
    if fcfe:
        rotulos += ["Juros após IR", "Nova dívida", "FCFE"]
    rotulos += ["Fator de desconto", "Valor presente do fluxo"]
    linha = {r: i for i, r in enumerate(rotulos, start=2)}
    for r, i in linha.items():
        d.cell(i, 1, r)
    d.cell(linha["Receita"], 2, f"={ref('Receita base')}").number_format = _NUM
    fluxo = "FCFE" if fcfe else "FCFF"
    for k in range(1, n + 1):
        col = get_column_letter(k + 2)
        ant = get_column_letter(k + 1)
        d[f"{col}1"] = k
        g = d[f"{col}{linha['Crescimento da receita']}"]
        g.value, g.number_format, g.fill = p["crescimento_receita"][k - 1], _PCT, _ENTRADA
        formulas = {
            "Receita": f"={ant}{linha['Receita']}*(1+{col}{linha['Crescimento da receita']})",
            "EBIT": f"={col}{linha['Receita']}*{ref('Margem EBIT')}",
            "NOPAT": f"={col}{linha['EBIT']}*(1-{ref('Alíquota de IR/CSLL')})",
            "D&A": f"={col}{linha['Receita']}*{ref('D&A')}",
            "Capex": f"={col}{linha['Receita']}*{ref('Capex')}",
            "Variação do capital de giro":
                f"=({col}{linha['Receita']}-{ant}{linha['Receita']})*{ref('Capital de giro')}",
            "FCFF": f"={col}{linha['NOPAT']}+{col}{linha['D&A']}-{col}{linha['Capex']}-"
                    f"{col}{linha['Variação do capital de giro']}",
            "Fator de desconto": f"=1/(1+{ref('Taxa de desconto')})^{col}1",
            "Valor presente do fluxo": f"={col}{linha[fluxo]}*{col}{linha['Fator de desconto']}",
        }
        if fcfe:
            formulas.update({
                "Juros após IR": f"={ref('Juros anuais')}*(1-{ref('Alíquota de IR/CSLL')})",
                "Nova dívida": f"={ref('Nova dívida por ano')}",
                "FCFE": f"={col}{linha['FCFF']}-{col}{linha['Juros após IR']}+{col}{linha['Nova dívida']}",
            })
        for r, f in formulas.items():
            c = d[f"{col}{linha[r]}"]
            c.value = f
            c.number_format = "0.0000" if r == "Fator de desconto" else _NUM
    ultima = get_column_letter(n + 2)
    base = max(linha.values()) + 2
    resumo = [
        ("Soma do valor presente dos fluxos", f"=SUM(C{linha['Valor presente do fluxo']}:{ultima}"
                                              f"{linha['Valor presente do fluxo']})", _NUM),
        ("Valor terminal (Gordon)", f"={ultima}{linha[fluxo]}*(1+{ref('Crescimento perpétuo')})/"
                                    f"({ref('Taxa de desconto')}-{ref('Crescimento perpétuo')})", _NUM),
        ("Valor presente do terminal", f"=B{base + 1}*{ultima}{linha['Fator de desconto']}", _NUM),
        ("Valor " + ("do patrimônio" if fcfe else "operacional"), f"=B{base}+B{base + 2}", _NUM),
        ("(−) Dívida líquida", f"={ref('Dívida líquida')}", _NUM),
        ("Valor do patrimônio", f"=B{base + 3}-B{base + 4}", _NUM),
        ("Valor por ação", f"=B{base + 5}/{ref('Ações em circulação')}", _RS),
        ("Margem de segurança", f"=(B{base + 6}-{ref('Cotação')})/B{base + 6}", _PCT),
        ("Peso do valor terminal", f"=B{base + 2}/B{base + 3}", _PCT),
    ]
    for i, (rotulo, formula, formato) in enumerate(resumo):
        d.cell(base + i, 1, rotulo).font = Font(bold=rotulo == "Valor por ação")
        d.cell(base + i, 2, formula).number_format = formato
    linha_conf = base + len(resumo) + 1
    d.cell(linha_conf, 1, "Valor por ação calculado pelo sistema (conferência)")
    d.cell(linha_conf, 2, resultado.get("valor_por_acao")).number_format = _RS
    d.column_dimensions["A"].width = 46
    for k in range(2, n + 3):
        d.column_dimensions[get_column_letter(k)].width = 16
    d.cell(linha_conf + 2, 1, aviso)

    saida = io.BytesIO()
    livro.save(saida)
    return saida.getvalue()
