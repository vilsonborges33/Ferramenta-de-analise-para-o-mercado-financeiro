"""Siegel, Bogle, Lo & Foerster (portfólio) e Dalio — casos calculados à mão."""

import math

import numpy as np
import pytest

from app.metodologias import bogle, dalio, portfolio, siegel

# ------------------------------------------------------------------ Siegel


def test_retorno_real_e_acumulados():
    assert siegel.retorno_real(0.10, 0.04).valor == pytest.approx(1.10 / 1.04 - 1)
    assert not siegel.retorno_real(0.1, -1).disponivel
    assert not siegel.retorno_real(None, 0.04).disponivel
    # 10 → 11 com dividendo 1 → 12: 100 × 12/10 = 120; 120 × 12/11
    r = siegel.indice_retorno_total([10, 11, 12], [0, 1, 0])
    assert r.detalhes["serie"][1] == pytest.approx(120) and r.valor == pytest.approx(120 * 12 / 11)
    assert not siegel.indice_retorno_total([10], [0]).disponivel
    assert not siegel.indice_retorno_total([0, 1], [0, 0]).disponivel
    real = siegel.acumulado_real([0.10, 0.10], [0.0, 0.10])
    assert real.valor == pytest.approx(1.1) and len(real.detalhes["serie"]) == 3
    assert not siegel.acumulado_real([0.1], []).disponivel


def test_cape_reversao_premio():
    assert siegel.lpa_real([1, 2], [100, 200]) == pytest.approx([2, 2])
    r = siegel.cape(100, [5] * 12)
    assert r.valor == pytest.approx(20) and r.detalhes["lpa_medio"] == 5
    assert not siegel.cape(100, [5] * 9).disponivel
    assert not siegel.cape(100, [-5] * 10).disponivel
    assert not siegel.cape(None, [5] * 10).disponivel
    # média 12, desvio populacional √(8/3)
    z = siegel.desvio_da_media(20, [10, 12, 14])
    assert z.valor == pytest.approx(8 / math.sqrt(8 / 3))
    assert not siegel.desvio_da_media(20, [10, 12]).disponivel
    assert not siegel.desvio_da_media(20, [10, 10, 10]).disponivel
    assert not siegel.desvio_da_media(None, [1, 2, 3]).disponivel
    assert siegel.premio_risco_acoes(20, 0.03).valor == pytest.approx(0.02)
    assert not siegel.premio_risco_acoes(0, 0.03).disponivel


# ------------------------------------------------------------------- Bogle


def test_bogle_custos():
    assert bogle.valor_futuro(1000, 0, 0.10, 2) == pytest.approx(1210)
    assert bogle.valor_futuro(0, 100, 0.10, 2) == pytest.approx(210)  # aportes no fim do ano
    # custo 1%: retorno líquido 1,1 × 0,99 − 1 = 8,9% → 1000 × 1,089²
    r = bogle.impacto_custos(1000, 0, 0.10, 2, 0.01)
    assert r.detalhes["valor_com_custos"] == pytest.approx(1000 * 1.089**2)
    assert r.valor == pytest.approx(1 - 1.089**2 / 1.21)
    assert not bogle.impacto_custos(1000, 0, 0.1, 0, 0.01).disponivel
    assert not bogle.impacto_custos(1000, 0, 0.1, 2, 1.5).disponivel
    assert not bogle.impacto_custos(0, 0, 0.1, 2, 0.01).disponivel
    assert not bogle.impacto_custos(None, 0, 0.1, 2, 0.01).disponivel
    d = bogle.ativo_vs_indice(1000, 0.10, 1, 0.02, 0.001)
    assert d.valor == pytest.approx(1000 * 1.1 * 0.98 - 1000 * 1.1 * 0.999)
    assert not bogle.ativo_vs_indice(None, 0.1, 1, 0.02, 0.001).disponivel


def test_bogle_decomposicao():
    # 4% + 5% + [(12,1/10)^(1/2) − 1 = 10%] = 19%
    r = bogle.decomposicao_retorno(0.04, 0.05, 10, 12.1, 2)
    assert r.valor == pytest.approx(0.19) and r.detalhes["retorno_especulativo"] == pytest.approx(0.10)
    assert not bogle.decomposicao_retorno(0.04, 0.05, -10, 12, 2).disponivel
    assert not bogle.decomposicao_retorno(0.04, 0.05, 10, 12, 0).disponivel
    assert not bogle.decomposicao_retorno(None, 0.05, 10, 12, 2).disponivel


# --------------------------------------------------------- Lo & Foerster


COV = np.array([[0.04, 0.0], [0.0, 0.09]])  # σ = 20% e 30%, correlação zero


def test_estatisticas_e_carteira():
    assert portfolio.retornos_simples([10, 11, 9.9]) == pytest.approx([0.1, -0.1])
    r = np.array([[0.01, 0.02], [0.03, 0.00], [-0.01, 0.01]])
    medias, cov = portfolio.estatisticas(r, periodos_ano=1)
    assert medias == pytest.approx([0.01, 0.01]) and cov.shape == (2, 2)
    assert portfolio.retorno_carteira([0.5, 0.5], [0.1, 0.2]) == pytest.approx(0.15)
    assert portfolio.volatilidade_carteira([0.5, 0.5], COV) == pytest.approx(math.sqrt(0.25 * 0.04 + 0.25 * 0.09))
    assert portfolio.sharpe(0.12, 0.2, 0.02).valor == pytest.approx(0.5)
    assert not portfolio.sharpe(0.12, 0, 0.02).disponivel
    assert not portfolio.sharpe(None, 0.2, 0.02).disponivel


def test_beta_e_capm():
    mercado = [0.01, -0.02, 0.03, 0.00]
    assert portfolio.beta([2 * x for x in mercado], mercado).valor == pytest.approx(2)
    assert not portfolio.beta([1, 2], [1, 2]).disponivel
    assert not portfolio.beta([1, 2, 3], [1, 1, 1]).disponivel
    assert portfolio.capm(0.05, 1.2, 0.10).valor == pytest.approx(0.11)


def test_otimizacoes_markowitz():
    # mínima variância sem correlação: w1 = σ2² ÷ (σ1² + σ2²) = 0,09 ÷ 0,13
    mv = portfolio.minima_variancia(COV)
    assert mv.detalhes["pesos"][0] == pytest.approx(0.09 / 0.13, abs=1e-4)
    assert mv.valor == pytest.approx(math.sqrt(0.0036 / 0.13), abs=1e-5)
    # tangente: w ∝ Σ⁻¹(μ − rf) = [0,05/0,04; 0,10/0,09] = [1,25; 1,111]
    ms = portfolio.maximo_sharpe([0.10, 0.15], COV, 0.05)
    assert ms.detalhes["pesos"][0] == pytest.approx(1.25 / (1.25 + 10 / 9), abs=1e-3)
    assert not portfolio.maximo_sharpe([0.01, 0.02], COV, 0.05).disponivel
    f = portfolio.fronteira_eficiente([0.10, 0.15], COV, pontos=5)
    retornos = [p["retorno"] for p in f.detalhes["pontos"]]
    vols = [p["volatilidade"] for p in f.detalhes["pontos"]]
    assert retornos == sorted(retornos) and vols == sorted(vols)  # acima da mínima variância, ambos crescem
    assert all(abs(sum(p["pesos"]) - 1) < 1e-6 and min(p["pesos"]) >= -1e-9 for p in f.detalhes["pontos"])
    assert not portfolio.fronteira_eficiente([0.1], np.array([[0.04]])).disponivel


def test_fatores_e_diversificacao():
    assert portfolio.numero_efetivo_ativos([0.5, 0.5]).valor == pytest.approx(2)
    assert portfolio.numero_efetivo_ativos([1, 0, 0]).valor == pytest.approx(1)
    assert not portfolio.numero_efetivo_ativos([0, 0]).disponivel
    precos = [100] + [110] * 11 + [120, 50]  # 14 meses; ignora o último
    assert portfolio.momento(precos).valor == pytest.approx(120 / 110 - 1)
    assert not portfolio.momento([1] * 12).disponivel
    assert not portfolio.momento([0] + [1] * 12).disponivel
    assert portfolio.percentis({"A": 0.1, "B": 0.3, "C": None, "D": 0.2}) == {"A": 0.0, "D": 0.5, "B": 1.0}
    assert portfolio.percentis({"A": 1.0}) == {"A": 1.0}


# ------------------------------------------------------------------- Dalio


def test_correlacao_e_contribuicao():
    a = np.array([0.01, -0.02, 0.03, 0.00])
    r = dalio.matriz_correlacao(np.column_stack([a, 2 * a, -a]))
    assert r.detalhes["matriz"][0][1] == pytest.approx(1) and r.detalhes["matriz"][0][2] == pytest.approx(-1)
    assert not dalio.matriz_correlacao(np.column_stack([a])).disponivel
    assert not dalio.matriz_correlacao(np.column_stack([a, np.zeros(4)])).disponivel
    c = dalio.contribuicao_risco([0.5, 0.5], np.array([[0.04, 0], [0, 0.04]]))
    assert c.detalhes["contribuicoes"] == pytest.approx([0.5, 0.5])
    assert not dalio.contribuicao_risco([0, 0], COV).disponivel


def test_paridade_de_risco_e_all_weather():
    assert dalio.paridade_inverso_volatilidade([0.1, 0.2]).detalhes["pesos"] == pytest.approx([2 / 3, 1 / 3])
    assert not dalio.paridade_inverso_volatilidade([0.1, 0]).disponivel
    # sem correlação, contribuições iguais ⇔ pesos ∝ 1/σ
    pr = dalio.paridade_risco(COV)
    assert pr.detalhes["pesos"] == pytest.approx([0.6, 0.4], abs=1e-4)
    contrib = dalio.contribuicao_risco(pr.detalhes["pesos"], COV).detalhes["contribuicoes"]
    assert contrib == pytest.approx([0.5, 0.5], abs=1e-4)
    aw = dalio.alocacao_all_weather(100_000)
    assert sum(aw.detalhes["alvos"].values()) == pytest.approx(100_000)
    assert aw.detalhes["alvos"]["titulos_longos"] == pytest.approx(40_000)
    assert not dalio.alocacao_all_weather(100, {"acoes": 0.5}).disponivel
