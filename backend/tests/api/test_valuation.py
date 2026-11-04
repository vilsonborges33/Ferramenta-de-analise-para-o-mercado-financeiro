"""Fase 4: valuation com premissas do usuário, conferido à mão, salvo e exportado com fórmulas."""

import io
import shutil
import subprocess
from datetime import date
from decimal import Decimal

import pytest
from openpyxl import load_workbook

from app.db.modelos import SerieEconomica
from app.ingestao.base import lote
from tests.api.test_ponta_a_ponta import cliente  # noqa: F401  (fixture)

# Premissas simples o bastante para conferir à mão.
DCF = {"receita_base": 1000.0, "crescimento_receita": [0.10, 0.10], "margem_ebit": 0.20, "aliquota": 0.0,
       "da_pct_receita": 0.0, "capex_pct_receita": 0.0, "capital_giro_pct_variacao_receita": 0.0,
       "taxa_desconto": 0.10, "crescimento_perpetuo": 0.0, "divida_liquida": 100.0}


def fcff_a_mao():
    # anos: receita 1100 e 1210 → FCFF 220 e 242; VT = 242 / 0,10 = 2420
    vp = 220 / 1.1 + 242 / 1.1 ** 2 + 2420 / 1.1 ** 2
    return (vp - 100) / 1_000_000  # 1 milhão de ações (EXMP)


@pytest.fixture
def com_selic(cliente, sessao):  # noqa: F811
    with lote(sessao, "BCB_SGS") as ctx:
        sessao.add(SerieEconomica(codigo="SELIC_META", data=date(2025, 1, 2), valor=Decimal("10.0"),
                                  **ctx.procedencia(date(2025, 1, 2))))
    sessao.commit()
    return cliente


def test_inicio_traz_insumos_premissas_e_comparativo(com_selic):
    r = com_selic.get("/valuation/EXMP3").json()
    assert r["insumos"]["acoes"] == pytest.approx(1_000_000) and r["insumos"]["selic"] == pytest.approx(0.10)
    assert r["insumos"]["receita"] == pytest.approx(8_000_000)
    assert r["premissas"]["gordon"]["custo_capital"] == pytest.approx(0.15)  # Selic + 5%
    assert {c["metodo"] for c in r["comparativo"]} == {m["id"] for m in r["metodos"]}
    assert "Não constituem recomendação" in r["aviso"]
    assert com_selic.get("/valuation/XXXX3").status_code == 404


def test_metodos_conferidos_a_mao(com_selic):
    calc = lambda m, p: com_selic.post("/valuation/EXMP3/calcular", json={"metodo": m, "premissas": p}).json()  # noqa: E731
    assert calc("dcf_fcff", DCF)["valor_por_acao"] == pytest.approx(fcff_a_mao())
    fcfe = calc("dcf_fcfe", {**DCF, "juros_anuais": 20.0, "nova_divida_anual": 0.0})
    # FCFE = FCFF − 20 (IR zero): 200 e 222; VT = 2220; sem subtrair dívida
    assert fcfe["valor_por_acao"] == pytest.approx((200 / 1.1 + 222 / 1.21 + 2220 / 1.21) / 1_000_000)
    gordon = calc("gordon", {"dividendo_atual": 1.0, "custo_capital": 0.15, "crescimento": 0.05})
    assert gordon["valor_por_acao"] == pytest.approx(10.5) and gordon["margem_seguranca"] == pytest.approx(
        1 - 10 / 10.5)
    dois = calc("ddm_dois_estagios", {"dividendo_atual": 1.0, "custo_capital": 0.10, "crescimento_alto": 0.0,
                                      "anos_alto": 1, "crescimento_estavel": 0.0})
    assert dois["valor_por_acao"] == pytest.approx(10.0)
    teto = calc("preco_teto_projetivo", {"lucro_projetado": 1_000_000, "payout": 0.5, "yield_minimo": 0.05})
    assert teto["valor_por_acao"] == pytest.approx(10.0)  # 0,50 por ação ÷ 5%
    sem_div = calc("gordon", {"dividendo_atual": None})
    assert sem_div["valor_por_acao"] is None and sem_div["motivo_indisponivel"]
    mult = calc("multiplos", {})
    assert mult["valor_por_acao"] is None and "pares" in mult["motivo_indisponivel"]
    sens = calc("dcf_fcff", DCF)["detalhes"]["sensibilidade"]
    assert sens["valores"][2][2] == pytest.approx(fcff_a_mao())  # centro da tabela = premissas escolhidas
    erro = com_selic.post("/valuation/EXMP3/calcular", json={"metodo": "xyz"})
    assert erro.status_code == 422


def _recalcular_no_libreoffice(conteudo: bytes, pasta) -> object:
    pasta.mkdir(parents=True, exist_ok=True)
    entrada = pasta / "dcf.xlsx"
    entrada.write_bytes(conteudo)
    saida = pasta / "saida"
    subprocess.run(["soffice", "--headless", "--convert-to", "xlsx", "--outdir", str(saida), str(entrada)],
                   check=True, capture_output=True, timeout=120)
    return load_workbook(saida / "dcf.xlsx", data_only=True)


def test_exportacao_do_dcf_com_formulas(com_selic, tmp_path):
    for metodo, extra in (("dcf_fcff", {}), ("dcf_fcfe", {"juros_anuais": 20.0, "nova_divida_anual": 5.0})):
        pedido = {"metodo": metodo, "premissas": {**DCF, **extra}}
        sistema = com_selic.post("/valuation/EXMP3/calcular", json=pedido).json()["valor_por_acao"]
        r = com_selic.post("/valuation/EXMP3/exportar", json=pedido)
        assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
        folha = load_workbook(io.BytesIO(r.content))["DCF"]
        assert str(folha["C3"].value).startswith("=") and "Premissas!" in str(folha["C4"].value)
        if shutil.which("soffice"):  # recalcula as fórmulas e compara com o valor do sistema
            dcf = _recalcular_no_libreoffice(r.content, tmp_path / metodo)["DCF"]
            valores = {dcf.cell(i, 1).value: dcf.cell(i, 2).value for i in range(1, dcf.max_row + 1)}
            assert valores["Valor por ação"] == pytest.approx(sistema)
    assert com_selic.post("/valuation/EXMP3/exportar", json={"metodo": "gordon"}).status_code == 422


def test_meus_valuations(com_selic):
    assert com_selic.get("/valuations").status_code == 401
    com_selic.post("/auth/registrar", json={"email": "val@exemplo.com", "senha": "senha-forte-1"})
    novo = com_selic.post("/valuations", json={"ticker": "exmp3", "metodo": "dcf_fcff", "nome": "Cenário base",
                                               "premissas": DCF, "narrativa": "Cresce com o mercado."}).json()
    assert novo["resultado"]["valor_por_acao"] == pytest.approx(fcff_a_mao())
    assert novo["insumos"]["acoes"] == pytest.approx(1_000_000)  # retrato dos insumos guardado
    lista = com_selic.get("/valuations", params={"ticker": "EXMP3"}).json()
    assert [v["nome"] for v in lista] == ["Cenário base"]
    xlsx = com_selic.get(f"/valuations/{novo['id']}/exportar.xlsx")
    assert xlsx.status_code == 200
    assert com_selic.delete(f"/valuations/{novo['id']}").status_code == 204
    assert com_selic.get("/valuations").json() == []
    assert com_selic.delete(f"/valuations/{novo['id']}").status_code == 404
