import pytest

from app.metodologias import fii


def test_p_vp_cota():
    assert fii.p_vp_cota(95, 100).valor == 0.95
    assert not fii.p_vp_cota(95, 0).disponivel
    assert not fii.p_vp_cota(None, 100).disponivel


def test_composicao_12_meses():
    # 12 meses de 1% → 1,01^12 − 1
    assert fii.composicao_percentuais([0.01] * 12).valor == pytest.approx(1.01**12 - 1)
    # usa só os 12 últimos
    assert fii.composicao_percentuais([0.5] + [0.0] * 12).valor == 0
    assert not fii.composicao_percentuais([0.01] * 11).disponivel
    assert not fii.composicao_percentuais([0.01] * 11 + [None]).disponivel


def test_soma_12_meses():
    assert fii.soma_percentuais([0.008] * 12).valor == pytest.approx(0.096)
    assert not fii.soma_percentuais([]).disponivel


def test_composicao_tipo_e_obrigacoes():
    from app.metodologias import fii as m
    linha = {"Imoveis_Renda_Acabados": "700", "Terrenos": "100", "CRI": "50", "Disponibilidades": "150",
             "Direitos_Bens_Imoveis": "800", "Total_Investido": "1000",  # subtotais não entram
             "Obrigacoes_Aquisicao_Imoveis": "120", "Rendimentos_Distribuir": "8", "Total_Passivo": "128"}
    r = m.composicao_ativo(linha, 1000)
    assert r.valor == pytest.approx(1000) and r.detalhes["cobertura_do_ativo_total"] == pytest.approx(1)
    grupos = {g["grupo"]: g["percentual"] for g in r.detalhes["grupos"]}
    assert grupos == pytest.approx({"Imóveis": 0.8, "Caixa e renda fixa": 0.15, "CRI e CRA": 0.05})
    assert m.tipo_do_fundo(r.detalhes["grupos"]) == "Tijolo"
    assert m.tipo_do_fundo([{"grupo": "CRI e CRA", "percentual": 0.9}]) == "Papel"
    assert m.tipo_do_fundo([{"grupo": "Cotas de FII", "percentual": 0.7}]) == "Fundo de fundos"
    assert m.tipo_do_fundo([{"grupo": "Imóveis", "percentual": 0.5}, {"grupo": "CRI e CRA", "percentual": 0.5}]) \
        == "Híbrido"
    assert {o["grupo"]: o["valor"] for o in m.obrigacoes(linha)} == {
        "Aquisição de imóveis": 120, "Rendimentos a distribuir": 8}
    assert not m.composicao_ativo(None).disponivel and not m.composicao_ativo({"Terrenos": "0"}).disponivel


def test_alavancagem_vacancia_e_retornos():
    from app.metodologias import fii as m
    assert m.alavancagem(128, 1000).valor == pytest.approx(0.128)
    assert not m.alavancagem(1, 0).disponivel
    # HGLG11 em 09/2026 (informe CVM): R$ 1.289,6 mi de passivo, dos quais R$ 53,4 mi de rendimentos a
    # distribuir e R$ 3,4 mi de taxas; R$ 8.835,7 mi de ativo → 13,95%, como na Ward.
    extras = {"Rendimentos_Distribuir": "53364083.37", "Taxa_Administracao_Pagar": "3367664.80",
              "Obrigacoes_Securitizacao_Recebiveis": "658265359.42"}
    assert m.passivo_nao_oneroso(extras) == pytest.approx(56731748.17)
    assert m.alavancagem(1289637537.45, 8835655334.84, m.passivo_nao_oneroso(extras)).valor == pytest.approx(
        0.1395, abs=5e-5)
    assert m.passivo_nao_oneroso(None) == 0
    v = m.vacancia_ponderada([(1000, 0.10), (3000, 0.0), (None, 0.5)])
    assert v.valor == pytest.approx(0.025) and v.detalhes["ponderada"]
    assert m.vacancia_ponderada([(None, 0.1), (None, 0.3)]).valor == pytest.approx(0.2)
    assert not m.vacancia_ponderada([]).disponivel
    e = m.estatistica_retornos([0.01, -0.02, 0.03, 0.0])
    assert e.valor == pytest.approx(0.5) and e.detalhes["negativos"] == 1 and e.detalhes["menor"] == -0.02
    assert not m.estatistica_retornos([0.01]).disponivel
