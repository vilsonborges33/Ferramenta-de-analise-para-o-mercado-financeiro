"""SEC EDGAR: companyfacts simulado (formato da API) → períodos padronizados, conferidos à mão."""

from datetime import date
from decimal import Decimal

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.modelos import Ativo, CotacaoDiaria, DemonstracaoPadronizada, Empresa, Provento, SerieEconomica
from app.db.sessao import obter_sessao
from app.ingestao import sec_edgar, us_treasury
from app.ingestao.base import EsquemaInesperado, lote
from app.main import app
from app.servicos.indicadores import recalcular


def fato(val, end, start=None, form="10-K", filed="2025-02-01", accn="0001-25-000001"):
    return {"val": val, "end": end, "start": start, "form": form, "filed": filed, "accn": accn}


def duracoes(anual_2023, anual_2024, ytd_2024, ytd_2025):
    return [fato(anual_2023, "2023-12-31", "2023-01-01", filed="2024-02-01"),
            fato(anual_2024, "2024-12-31", "2024-01-01"),
            fato(ytd_2024, "2024-06-30", "2024-01-01", form="10-Q", filed="2024-08-01"),
            fato(ytd_2025, "2025-06-30", "2025-01-01", form="10-Q", filed="2025-08-01", accn="0001-25-000009")]


FACTS = {"entityName": "Exemplo REIT Inc.", "facts": {
    "us-gaap": {
        "Revenues": {"units": {"USD": duracoes(1000, 1200, 600, 700)}},
        "OperatingIncomeLoss": {"units": {"USD": duracoes(300, 360, 170, 200)}},
        "NetIncomeLoss": {"units": {"USD": duracoes(100, 150, 70, 90)}},
        "DepreciationDepletionAndAmortization": {"units": {"USD": duracoes(200, 220, 100, 120)}},
        "GainLossOnSaleOfRealEstateInvestmentProperty": {"units": {"USD": duracoes(0, 20, 0, 10)}},
        "PaymentsToAcquirePropertyPlantAndEquipment": {"units": {"USD": duracoes(40, 50, 20, 30)}},
        "PaymentsForCapitalImprovements": {"units": {"USD": duracoes(10, 12, 5, 6)}},
        "PaymentsOfDividends": {"units": {"USD": duracoes(80, 90, 40, 50)}},
        "Assets": {"units": {"USD": [fato(5000, "2024-12-31"), fato(5500, "2025-06-30", form="10-Q")]}},
        "StockholdersEquity": {"units": {"USD": [fato(2000, "2024-12-31"), fato(2100, "2025-06-30", form="10-Q")]}},
        "LongTermDebt": {"units": {"USD": [fato(1500, "2024-12-31"), fato(1600, "2025-06-30", form="10-Q")]}},
        "CashAndCashEquivalentsAtCarryingValue": {"units": {"USD": [fato(100, "2025-06-30", form="10-Q")]}},
    },
    "dei": {"EntityCommonStockSharesOutstanding": {"units": {"shares": [
        fato(90, "2025-01-20", accn="0001-25-000001"),
        fato(60, "2025-07-25", form="10-Q", filed="2025-08-01", accn="0001-25-000009"),
        fato(40, "2025-07-25", form="10-Q", filed="2025-08-01", accn="0001-25-000009")]}}},
}}


def test_padronizacao_anual_e_12_meses():
    periodos = {(p.periodo, p.tipo): p for p in sec_edgar.padronizar(FACTS)}
    anual = periodos[("2024-A", "ano")]
    assert anual.campos["receita_liquida"] == 1200 and anual.campos["capex"] == -50
    assert anual.campos["patrimonio_liquido"] == 2000 and anual.campos["passivo_total"] == 3000
    ttm = periodos[("2025-T2", "ttm")]
    assert ttm.fim == date(2025, 6, 30)
    assert ttm.campos["receita_liquida"] == 1300  # 1200 + 700 − 600
    assert ttm.campos["lucro_liquido_controladores"] == 170  # 150 + 90 − 70
    assert ttm.campos["capex"] == -60 and ttm.campos["dividendos_pagos"] == -100
    assert ttm.campos["ativo_total"] == 5500 and ttm.campos["emprestimos_lp"] == 1600
    assert [i.get("subtraido") for i in ttm.insumos["receita_liquida"]][-1] is True  # procedência da conta
    assert ("2023-A", "ano") in periodos
    acoes, data_ref, origem = sec_edgar.acoes_em_circulacao(FACTS)
    assert acoes == 100 and data_ref == date(2025, 7, 25) and origem["classes"] == 2  # soma das classes
    assert sec_edgar.classificar("6798") == ("REIT", "geral") and sec_edgar.classificar("6022") == ("STOCK", "banco")


def test_contato_obrigatorio(monkeypatch):
    from app.config import obter_configuracao
    monkeypatch.setattr(obter_configuracao(), "contato_user_agent", "analise-mercado (contato: seu-email@exemplo.com)")
    with pytest.raises(EsquemaInesperado, match="CONTATO_USER_AGENT"):
        sec_edgar.cabecalhos()
    monkeypatch.setattr(obter_configuracao(), "contato_user_agent", "analise eu@meudominio.com")
    assert sec_edgar.cabecalhos()["User-Agent"] == "analise eu@meudominio.com"


def test_treasury():
    csv = 'Date,"1 Mo","10 Yr","30 Yr"\n06/30/2025,4.30,4.24,4.78\n06/27/2025,4.31,,4.80\n'
    assert us_treasury.parse(csv) == [(date(2025, 6, 30), 4.24)]
    with pytest.raises(EsquemaInesperado):
        us_treasury.parse("a,b\n1,2\n")


@pytest.fixture
def cliente(sessao, monkeypatch):
    from app.config import obter_configuracao
    monkeypatch.setattr(obter_configuracao(), "contato_user_agent", "analise eu@meudominio.com")
    monkeypatch.setattr(obter_configuracao(), "etfs_eua", "SPY")

    def responder(request):
        url = str(request.url)
        if url.endswith("company_tickers.json"):
            return httpx.Response(200, json={"0": {"cik_str": 1234, "ticker": "EXRT", "title": "Exemplo REIT"}})
        if "submissions" in url:
            return httpx.Response(200, json={"name": "Exemplo REIT Inc.", "sic": "6798",
                                             "sicDescription": "Real Estate Investment Trusts"})
        return httpx.Response(200, json=FACTS)

    cliente_sec = httpx.Client(transport=httpx.MockTransport(responder))
    total = sec_edgar.ingerir(sessao, ["EXRT", "NAOEXISTE"], cliente=cliente_sec, pausa=0)
    assert total == 3  # 2023-A, 2024-A e 12 meses
    reit = sessao.scalar(select(Ativo).where(Ativo.ticker == "EXRT"))
    spy = sessao.scalar(select(Ativo).where(Ativo.ticker == "SPY"))
    with lote(sessao, "YAHOO_FINANCE") as ctx:
        for a, preco in ((reit, "34.0"), (spy, "500.0")):
            sessao.add(CotacaoDiaria(ativo_id=a.id, data=date(2025, 7, 30), fechamento=Decimal(preco),
                                     volume_financeiro=Decimal("1000000"), **ctx.procedencia(date(2025, 7, 30))))
        sessao.add(Provento(ativo_id=spy.id, tipo="DIVIDENDO", valor_por_cota=Decimal("6.5"),
                            data_com=date(2025, 6, 20), data_ex=date(2025, 6, 23),
                            **ctx.procedencia(date(2025, 6, 20))))
    with lote(sessao, "US_TREASURY") as ctx:
        sessao.add(SerieEconomica(codigo="UST10Y", data=date(2025, 7, 30), valor=Decimal("4.2"),
                                  **ctx.procedencia(date(2025, 7, 30))))
    sessao.commit()
    recalcular(sessao)
    app.dependency_overrides[obter_sessao] = lambda: sessao
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_paginas_e_metricas_dos_eua(cliente, sessao):
    empresa = sessao.scalar(select(Empresa).where(Empresa.cik == "0000001234"))
    assert empresa.pais == "US" and sessao.query(DemonstracaoPadronizada).filter_by(empresa_id=empresa.id).count() == 3
    d = cliente.get("/eua/EXRT").json()
    assert d["moeda"] == "USD" and d["classe"] == "REIT"
    ind = {n["metrica"]: n["valor"] for g in d["grupos"].values() for n in g}
    # FFO = 170 + D&A 12m (220 + 120 − 100 = 240) − ganho (20 + 10 − 0 = 30) = 380; 100 ações; US$ 34
    assert ind["reit.ffo"] == pytest.approx(380) and ind["reit.ffo_acao"] == pytest.approx(3.8)
    assert ind["reit.p_ffo"] == pytest.approx(3400 / 380)
    assert ind["reit.affo"] == pytest.approx(380 - 13)  # manutenção 12m = 12 + 6 − 5
    assert ind["reit.payout_ffo"] == pytest.approx(100 / 380)
    assert ind["basico.p_l"] == pytest.approx(3400 / 170)
    etf = cliente.get("/eua/SPY").json()
    assert {n["metrica"] for g in etf["grupos"].values() for n in g} == {"basico.dy", "basico.liquidez_diaria"}
    assert next(n for g in etf["grupos"].values() for n in g if n["metrica"] == "basico.dy")["valor"] == pytest.approx(
        6.5 / 500)
    assert [a["ticker"] for a in cliente.get("/eua", params={"busca": "ex"}).json()] == ["EXRT"]
    assert cliente.get("/acoes/EXRT").status_code == 404  # páginas da B3 não mostram ativos dos EUA
    r = cliente.get("/screening/acoes", params={"mercado": "EUA", "liquidez_min": ""}).json()
    assert r["moeda"] == "USD" and [i["ticker"] for i in r["itens"]] == ["EXRT"]
    assert all(i["ticker"] != "EXRT" for i in cliente.get("/screening/acoes").json()["itens"])
    v = cliente.get("/valuation/EXRT").json()
    assert v["insumos"]["selic"] == pytest.approx(0.042) and v["insumos"]["nome_taxa"] == "Treasury 10 anos"
    assert v["premissas"]["gordon"]["crescimento"] == pytest.approx(0.025)


def test_carteira_recusa_ativo_dos_eua(cliente):
    cliente.post("/auth/registrar", json={"email": "eua@exemplo.com", "senha": "senha-forte-1"})
    cid = cliente.post("/carteiras", json={"nome": "X"}).json()["id"]
    r = cliente.post(f"/carteiras/{cid}/lancamentos", json={"ticker": "EXRT", "tipo": "COMPRA", "data": "2025-07-30",
                                                            "quantidade": 1, "preco": 34})
    assert r.status_code == 422 and "EUA" in r.json()["detail"]
