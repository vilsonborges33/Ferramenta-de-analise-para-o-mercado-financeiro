"""Fase 5: página do fundo, Gordon ajustado, documentos do FNET e Fund Screening (valores à mão)."""

from datetime import date
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import select, update

from app.db.modelos import Ativo, Fii, FiiImovel, FiiInformeMensal, Provento, TituloTesouroTaxa
from app.ingestao.base import lote
from app.servicos import fundos
from app.servicos.indicadores import recalcular
from tests.api.test_fii_ponta_a_ponta import cliente as cliente_fii  # noqa: F401  (fixture)

EXTRAS = {"Imoveis_Renda_Acabados": "90000000", "CRI": "10000000", "Disponibilidades": "20000000",
          "Obrigacoes_Aquisicao_Imoveis": "15000000", "Rendimentos_Distribuir": "1000000"}


@pytest.fixture
def cliente(cliente_fii, sessao):  # noqa: F811
    fii = sessao.scalar(select(Fii))
    sessao.execute(update(FiiInformeMensal).where(FiiInformeMensal.competencia == date(2024, 12, 1))
                   .values(extras=EXTRAS, ativo_total=Decimal("120000000"), total_passivo=Decimal("16000000")))
    ativo = sessao.scalar(select(Ativo).where(Ativo.ticker == "HGLG11"))
    with lote(sessao, "CVM_FII_TRIMESTRAL") as ctx:
        for nome, area, vac in (("Galpão A", 1000, "0.10"), ("Galpão B", 3000, "0")):
            sessao.add(FiiImovel(fii_id=fii.id, competencia=date(2024, 9, 30), nome=nome, area_m2=Decimal(area),
                                 percentual_vacancia=Decimal(vac), **ctx.procedencia(date(2024, 9, 30))))
    with lote(sessao, "YAHOO_FINANCE") as ctx:
        for mes in range(1, 13):  # R$ 1,00 por mês → R$ 12,00 em 12 meses
            d = date(2024, mes, 10)
            sessao.add(Provento(ativo_id=ativo.id, tipo="RENDIMENTO_FII", valor_por_cota=Decimal("1"), data_com=d,
                                data_ex=d, **ctx.procedencia(d)))
    with lote(sessao, "TESOURO_TD") as ctx:
        for venc, taxa in ((date(2029, 1, 1), "12.0"), (date(2035, 1, 1), "13.0")):
            sessao.add(TituloTesouroTaxa(titulo="Tesouro Prefixado", vencimento=venc, data_base=date(2025, 1, 2),
                                         taxa_compra=Decimal(taxa), **ctx.procedencia(date(2025, 1, 2))))
    sessao.commit()
    recalcular(sessao)
    return cliente_fii


def test_pagina_do_fundo(cliente):
    r = cliente.get("/fiis/HGLG11/fundo").json()
    grupos = {g["grupo"]: g["percentual"] for g in r["composicao"]["grupos"]}
    assert grupos == pytest.approx({"Imóveis": 0.75, "Caixa e renda fixa": 1 / 6, "CRI e CRA": 1 / 12})
    assert r["tipo"] == "Tijolo" and r["composicao"]["cobertura"] == pytest.approx(1.0)
    assert r["endividamento"]["alavancagem"] == pytest.approx(16 / 120)
    obrigacoes = {o["grupo"] for o in r["endividamento"]["obrigacoes"]}
    assert obrigacoes == {"Aquisição de imóveis", "Rendimentos a distribuir"}
    assert [i["nome"] for i in r["imoveis"]] and r["competencia_imoveis"] == "2024-09-30"
    assert len(r["historico"]) == 12 and r["historico"][-1]["cotistas"] == 5012
    ind = {n["metrica"]: n for g in cliente.get("/fiis/HGLG11").json()["grupos"].values() for n in g}
    assert ind["fii.vacancia"]["valor"] == pytest.approx(0.025)  # (1000 × 10%) ÷ 4000 m²
    assert ind["fii.alavancagem"]["valor"] == pytest.approx(16 / 120)
    assert cliente.get("/fiis/XXXX11/fundo").status_code == 404


def test_gordon_ajustado(cliente):
    r = cliente.get("/fiis/HGLG11/gordon").json()
    # Tesouro Prefixado mais longo 13% × (1 − 15%) = 11,05% + prêmio 2% = 13,05%; g = 0
    assert r["taxa_base"] == pytest.approx(0.13) and "2035" in r["descricao_taxa"]
    assert r["dividendo_12m"] == pytest.approx(12.0)
    assert r["preco_teto"] == pytest.approx(12 / 0.1305)
    assert r["margem_seguranca"] == pytest.approx(1 - 150 / (12 / 0.1305))
    bruta = cliente.get("/fiis/HGLG11/gordon", params={"liquida": False, "premio": 0.0, "crescimento": 0.02}).json()
    assert bruta["preco_teto"] == pytest.approx(12 * 1.02 / (0.13 - 0.02))
    manual = cliente.get("/fiis/HGLG11/gordon", params={"taxa": 0.10, "liquida": False, "premio": 0}).json()
    assert manual["preco_teto"] == pytest.approx(120) and manual["descricao_taxa"] == "informada pelo usuário"
    assert cliente.get("/fiis/HGLG11/gordon", params={"base": "xyz"}).status_code == 422


def test_screening_de_fiis(cliente):
    r = cliente.get("/screening/fiis").json()
    item = r["itens"][0]
    assert item["ticker"] == "HGLG11" and item["tipo"] == "Tijolo" and item["segmento"] == "Logística"
    assert item["dy"] == pytest.approx(12 / 150) and item["vacancia"] == pytest.approx(0.025)
    assert item["gordon_teto"] == pytest.approx(12 / 0.1305)
    assert cliente.get("/screening/fiis", params={"p_vp_max": 1.0}).json()["itens"] == []
    assert cliente.get("/screening/fiis", params={"tipos": ["Papel"]}).json()["itens"] == []
    assert len(cliente.get("/screening/fiis", params={"segmentos": ["Logística"], "dy_min": 0.05}).json()["itens"]) == 1
    csv = cliente.get("/screening/fiis/exportar", params={"formato": "csv"}).content.decode("utf-8-sig")
    assert "HGLG11" in csv and "Não constituem recomendação" in csv
    assert cliente.get("/screening/fiis", params={"ordenar_por": "xyz"}).status_code == 422


def test_documentos_do_fnet(cliente, sessao):
    pedidos = []

    def responder(request):
        pedidos.append(request)
        return httpx.Response(200, json={"data": [{"id": 123, "categoriaDocumento": "Relatórios",
                                                    "tipoDocumento": "Relatório Gerencial", "dataEntrega": "10/01/2025",
                                                    "dataReferencia": "12/2024", "status": "AC"}]})

    r = fundos.documentos_fnet(sessao, "HGLG11", cliente=httpx.Client(transport=httpx.MockTransport(responder)))
    assert r["documentos"][0]["url"].endswith("id=123&cvm=true") and r["erro"] is None
    assert "cnpjFundo=11728688000147" in str(pedidos[0].url)
    falha = fundos.documentos_fnet(sessao, "HGLG11", cliente=httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(503))))
    assert falha["documentos"] == [] and falha["erro"]
