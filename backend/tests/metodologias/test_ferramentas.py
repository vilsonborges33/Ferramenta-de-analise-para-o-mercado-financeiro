"""Ferramentas da Fase 8 — casos calculados à mão."""

import pytest

from app.metodologias import ferramentas as f


def test_juros_compostos_sem_aporte():
    r = f.juros_compostos(1000, 0, 0.01, 12)
    assert r.valor == pytest.approx(1000 * 1.01**12)  # 1126,83
    assert r.detalhes["investido"] == 1000
    assert len(r.detalhes["serie"]) == 13


def test_juros_compostos_com_aporte_no_fim():
    # 0 inicial, 100/mês a 1%, 3 meses: 100 → 201 → 303,01
    r = f.juros_compostos(0, 100, 0.01, 3)
    assert r.valor == pytest.approx(303.01)
    assert r.detalhes["juros"] == pytest.approx(3.01)


def test_juros_compostos_bordas():
    assert f.juros_compostos(1000, 0, 0.01, 0).valor is None
    assert f.juros_compostos(1000, 0, -1, 5).valor is None
    assert f.juros_compostos(-1, 0, 0.01, 5).valor is None
    assert "taxa" in f.juros_compostos(1000, 0, None, 5).motivo_indisponivel
    assert f.juros_compostos(1000, 0, 0, 5).valor == 1000


def test_taxa_equivalente():
    assert f.taxa_equivalente(0.01, "mes", "ano").valor == pytest.approx(1.01**12 - 1)  # 12,68%
    assert f.taxa_equivalente(0.12, "ano", "mes").valor == pytest.approx(1.12 ** (1 / 12) - 1)  # 0,9489%
    # CDI 14,15% a.a. → diária útil (252)
    assert f.taxa_equivalente(0.1415, "ano", "dia_util").valor == pytest.approx(1.1415 ** (1 / 252) - 1)
    todas = f.taxa_equivalente(0.01, "mes", "ano").detalhes["todas"]
    assert todas["mes"] == pytest.approx(0.01)
    assert todas["semestre"] == pytest.approx(1.01**6 - 1)


def test_taxa_equivalente_bordas():
    assert f.taxa_equivalente(0.01, "mes", "decada").valor is None
    assert f.taxa_equivalente(-1, "mes", "ano").valor is None
    assert f.taxa_equivalente(None, "mes", "ano").valor is None


def test_taxa_real():
    assert f.taxa_real(0.10, 0.04).valor == pytest.approx(1.10 / 1.04 - 1)
    assert f.taxa_real(0.10, -1).valor is None


def test_aporte_necessario_e_periodos():
    # Meta 303,01 em 3 meses a 1% partindo de 0 → PMT = 100
    assert f.aporte_necessario(0, 303.01, 0.01, 3) == pytest.approx(100)
    assert f.aporte_necessario(0, 300, 0, 3) == pytest.approx(100)
    assert f.aporte_necessario(10_000, 100, 0.01, 12) == 0  # já passa da meta
    assert f.periodos_ate(0, 100, 0.01, 303.01) == 3
    assert f.periodos_ate(0, 100, 0, 250) == 3
    assert f.periodos_ate(500, 0, 0.01, 400) == 0
    assert f.periodos_ate(0, 0, 0, 100) is None


def test_plano_aposentadoria():
    # 0 inicial, R$ 1.000/mês, 12,68% a.a. (= 1% a.m.), 10 anos, DY 8%, meta R$ 5.000/mês
    r = f.plano_aposentadoria(0, 1000, 1.01**12 - 1, 10, 0.08, 5000)
    final = 1000 * (1.01**120 - 1) / 0.01  # 230.038,69
    assert r.valor == pytest.approx(final)
    assert r.detalhes["taxa_mensal"] == pytest.approx(0.01)
    assert r.detalhes["renda_mensal"] == pytest.approx(final * 0.08 / 12)
    assert r.detalhes["patrimonio_necessario"] == pytest.approx(750_000)
    assert r.detalhes["aporte_necessario"] == pytest.approx(750_000 * 0.01 / (1.01**120 - 1))
    assert r.detalhes["atinge_meta"] is False
    assert len(r.detalhes["serie"]) == 11
    n = r.detalhes["meses_ate_meta"]
    assert 1000 * (1.01**n - 1) / 0.01 >= 750_000 > 1000 * (1.01 ** (n - 1) - 1) / 0.01


def test_plano_aposentadoria_bordas():
    assert f.plano_aposentadoria(0, 1000, 0.1, 0, 0.08, 5000).valor is None
    assert f.plano_aposentadoria(0, 1000, 0.1, 10, 0, 5000).valor is None
    assert f.plano_aposentadoria(0, 1000, -1, 10, 0.08, 5000).valor is None
    assert f.plano_aposentadoria(None, 1000, 0.1, 10, 0.08, 5000).valor is None
