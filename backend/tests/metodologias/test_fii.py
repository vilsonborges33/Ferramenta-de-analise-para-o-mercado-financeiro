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
