"""Análises dos livros por ativo (/ativos/{ticker}/analises) e a planilha de prêmios de risco do Damodaran."""

import io
from datetime import date, datetime
from decimal import Decimal

import openpyxl
import pytest

from app.db.modelos import SerieEconomica, TituloTesouroTaxa
from app.ingestao import damodaran
from app.ingestao.base import EsquemaInesperado, lote
from tests.api.test_ponta_a_ponta import cliente  # noqa: F401  (fixture)


def _planilha(brasil=True, aba="ERPs by country") -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = aba
    ws.append(["Country and Equity Risk Premiums"])
    ws.append(["Date of update:", datetime(2026, 1, 1)])
    ws.append(["Enter the current risk premium for a mature equity market", None, None, None, 0.0423])
    ws.append(["Enter the current risk premium for the US =", None, None, None, 0.0446])
    ws.append(["Country", "Region", "Moody's rating", "Default Spread", "Total ERP", "CRP"])
    if brasil:
        ws.append(["Brazil", "Central and South America", "Ba1", 0.0213, 0.0747, 0.0324])
    saida = io.BytesIO()
    wb.save(saida)
    return saida.getvalue()


def test_planilha_do_damodaran():
    data_ref, valores = damodaran.parse(_planilha())
    assert data_ref == date(2026, 1, 1)
    assert valores == pytest.approx({"DAMODARAN_ERP_MADURO": 4.23, "DAMODARAN_ERP_EUA": 4.46,
                                     "DAMODARAN_CRP_BRASIL": 3.24, "DAMODARAN_SPREAD_BRASIL": 2.13})
    with pytest.raises(EsquemaInesperado):
        damodaran.parse(_planilha(brasil=False))
    with pytest.raises(EsquemaInesperado):
        damodaran.parse(_planilha(aba="Outra"))
    with pytest.raises(EsquemaInesperado):
        damodaran.parse(b"nao e xlsx")


def test_analises_da_acao(cliente, sessao):  # noqa: F811
    # Empresa exemplo: lucro de R$ 1 mi em todos os anos (2019–2024), 1 mi de ações, PL R$ 5 mi, cotação R$ 10.
    with lote(sessao, "BCB_SGS") as ctx:
        sessao.add(SerieEconomica(codigo="SELIC_META", data=date(2025, 1, 2), valor=Decimal("10"),
                                  **ctx.procedencia(date(2025, 1, 2))))
    with lote(sessao, "DAMODARAN") as ctx:
        for codigo, valor in (("DAMODARAN_ERP_MADURO", "4"), ("DAMODARAN_CRP_BRASIL", "3"),
                              ("DAMODARAN_SPREAD_BRASIL", "2")):
            sessao.add(SerieEconomica(codigo=codigo, data=date(2026, 1, 1), valor=Decimal(valor),
                                      **ctx.procedencia(date(2026, 1, 1))))
    with lote(sessao, "TESOURO_TD") as ctx:
        sessao.add(TituloTesouroTaxa(titulo="Tesouro Prefixado", vencimento=date(2035, 1, 1),
                                     data_base=date(2025, 1, 2), taxa_compra=Decimal("13"),
                                     **ctx.procedencia(date(2025, 1, 2))))
    sessao.commit()
    r = cliente.get("/ativos/EXMP3/analises").json()
    assert "Não constituem" in r["aviso"]

    rev = r["graham"]["valor_revisado"]  # LPA 1 × (8,5 + 2 × 0) × 4,4 ÷ 10
    assert rev["valor"] == pytest.approx(1 * 8.5 * 4.4 / 10) and rev["crescimento"] == pytest.approx(0)
    checklist = r["graham"]["checklist"]
    criterios = {c["nome"]: c["atendido"] for c in checklist["detalhes"]["criterios"]}
    assert criterios["Porte adequado"] is False  # receita de R$ 8 mi
    assert criterios["Lucros positivos"] is None  # só 6 anos de DFP: não dá para afirmar
    assert criterios["Dividendos ininterruptos"] is False  # 2025 completo e sem proventos
    assert criterios["P/VP moderado"] is True  # P/VP 2 > 1,5, mas P/L × P/VP = 10 × 2 = 20 ≤ 22,5
    assert checklist["valor"] == sum(1 for v in criterios.values() if v)

    assert r["lynch"]["categoria"]["detalhes"]["categoria"] == "crescimento_lento"
    assert r["lynch"]["indice"]["valor"] is None  # sem proventos: DY indisponível
    assert r["bazin"]["regularidade"]["valor"] is None  # menos de 5 anos completos de proventos
    assert r["bazin"]["endividamento_baixo"]["valor"] == 1  # DL R$ 1,4 mi ÷ PL R$ 5 mi ≤ 1
    assert r["siegel"]["reversao_media"]["valor"] is None  # sem cotação nos fins de ano
    assert r["portfolio"]["beta"]["valor"] is None and "Ibovespa" in r["portfolio"]["beta"]["motivo_indisponivel"]

    ke = r["damodaran"]["custo_capital_proprio"]  # (13% − 2%) + 1,0 × 4% + 3%
    assert ke["valor"] == pytest.approx(0.18) and ke["beta_estimado"] is False
    assert ke["taxa_livre_risco"] == pytest.approx(0.11) and ke["premio_pais"] == pytest.approx(0.03)
    assert cliente.get("/ativos/XXXX3/analises").status_code == 404
