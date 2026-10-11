"""FII: informes mensais + cotação → indicadores → API. Valores fictícios calculados à mão."""

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.db.sessao import obter_sessao
from app.ingestao import cotahist, cvm_fii
from app.ingestao.base import lote
from app.main import app
from app.servicos.indicadores import recalcular
from tests import amostras


@pytest.fixture
def cliente(sessao):
    with lote(sessao, "B3_COTAHIST") as ctx:
        registros = cotahist.parse(amostras.linha_cotahist("20250102", "HGLG11", 150.0, 8_000_000, codbdi="12",
                                                           isin="BRHGLGCTF004"))
        cotahist.criar_ativos_fii(ctx, registros)
        cotahist.gravar(ctx, registros)
    fundos = [{"cnpj": "11.728.688/0001-47", "nome": "FII EXEMPLO", "isin": "BRHGLGCTF004", "segmento": "Logística",
               "mandato": "Renda", "tipo_gestao": "Ativa", "administrador": "ADM", "publico_alvo": "Geral",
               "data_inicio": date(2010, 1, 1), "data_referencia": date(2024, 12, 1)}]
    informes = [{"cnpj": "11.728.688/0001-47", "competencia": date(2024, mes, 1), "versao": 1,
                 "patrimonio_liquido": Decimal("120000000"), "cotas_emitidas": Decimal("1000000"),
                 "valor_patrimonial_cota": Decimal("120"), "numero_cotistas": 5000 + mes,
                 "rentabilidade_patrimonial_mes": Decimal("0.01"), "dividend_yield_mes": Decimal("0.008")}
                for mes in range(1, 13)]
    with lote(sessao, "CVM_FII_MENSAL") as ctx:
        cvm_fii.gravar(ctx, fundos, informes)
    recalcular(sessao)
    app.dependency_overrides[obter_sessao] = lambda: sessao
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_indicadores_do_fii(cliente):
    dados = cliente.get("/fiis/HGLG11").json()
    assert dados["nome"] == "FII EXEMPLO" and dados["segmento"] == "Logística"
    ind = {n["metrica"]: n for g in dados["grupos"].values() for n in g}
    assert ind["fii.p_vp"]["valor"] == pytest.approx(1.25)  # 150 ÷ 120
    assert ind["fii.numero_cotistas"]["valor"] == 5012  # informe mais recente
    assert ind["fii.dy_informado_12m"]["valor"] == pytest.approx(0.096)
    assert ind["fii.rentab_patrimonial_12m"]["valor"] == pytest.approx(1.01**12 - 1)
    assert ind["basico.dy"]["valor"] is None
    assert {p["fonte"] for p in ind["fii.p_vp"]["procedencia"]} == {"B3_COTAHIST", "CVM_FII_MENSAL"}
    assert "basico.p_l" not in ind  # indicadores de empresa não aparecem para FII
    assert cliente.get("/fiis").json() == []
    assert cliente.get("/fiis", params={"busca": "hglg"}).json()[0]["ticker"] == "HGLG11"
    assert cliente.get("/fiis", params={"busca": "logística"}).json() == []  # nome do fundo: "FII EXEMPLO"
    assert cliente.get("/fiis", params={"busca": "exemplo"}).json()[0]["ticker"] == "HGLG11"
    assert cliente.get("/acoes/HGLG11").status_code == 404
