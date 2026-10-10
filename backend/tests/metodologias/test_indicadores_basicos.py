"""Casos calculados à mão. Valores redondos para conferência fácil."""

import pytest

from app.metodologias import indicadores_basicos as ib
from app.metodologias.registro import METRICAS, POR_ID


def test_acoes_em_circulacao():
    assert ib.acoes_em_circulacao(1_000, 50).valor == 950
    assert ib.acoes_em_circulacao(1_000, None).valor == 1_000
    assert not ib.acoes_em_circulacao(100, 100).disponivel
    assert "total_emitidas" in ib.acoes_em_circulacao(None, 0).motivo_indisponivel


def test_valor_de_mercado_soma_classes():
    # 600 ON a R$ 10 + 400 PN a R$ 12 = 6.000 + 4.800
    assert ib.valor_de_mercado([(600, 10), (400, 12)]).valor == 10_800
    assert not ib.valor_de_mercado([]).disponivel
    assert not ib.valor_de_mercado([(600, None)]).disponivel
    assert not ib.valor_de_mercado([(0, 10)]).disponivel


def test_divida_e_ev():
    assert ib.divida_bruta(100, 300).valor == 400
    assert ib.divida_bruta(None, 300).valor == 300
    assert not ib.divida_bruta(None, None).disponivel
    assert ib.divida_liquida(400, 150, 50).valor == 200
    assert ib.divida_liquida(400, 150, None).valor == 250
    assert ib.divida_liquida(100, 300, 0).valor == -200  # caixa líquido
    assert not ib.divida_liquida(400, None, 0).disponivel
    assert ib.valor_da_firma(1_000, -200).valor == 800
    assert not ib.valor_da_firma(None, 10).disponivel


def test_ebitda_usa_valor_absoluto_da_depreciacao():
    assert ib.ebitda(100, 30).valor == 130
    assert ib.ebitda(100, -30).valor == 130  # D&A aparece positiva na DFC (ajuste ao lucro)
    assert not ib.ebitda(100, None).disponivel


def test_lpa_vpa():
    assert ib.lpa(500, 100).valor == 5
    assert ib.vpa(2_000, 100).valor == 20
    assert not ib.lpa(500, 0).disponivel
    assert not ib.vpa(None, 100).disponivel


def test_p_l_casos():
    assert ib.p_l(10_000, 1_000).valor == 10
    negativo = ib.p_l(10_000, -500)
    assert negativo.valor == -20 and "negativo" in negativo.detalhes["aviso"]
    assert ib.p_l(10_000, 0).motivo_indisponivel == "lucro_liquido igual a zero"
    assert not ib.p_l(None, 100).disponivel


def test_p_vp_patrimonio_negativo_tem_aviso():
    assert ib.p_vp(10_000, 5_000).valor == 2
    assert "aviso" in ib.p_vp(10_000, -5_000).detalhes


def test_outros_multiplos():
    assert ib.p_receita(10_000, 20_000).valor == 0.5
    assert ib.p_ebit(10_000, 2_000).valor == 5
    assert ib.p_ebitda(10_000, 2_500).valor == 4
    assert ib.ev_ebit(12_000, 2_000).valor == 6
    assert ib.ev_ebitda(12_000, 3_000).valor == 4
    assert ib.ev_ebitda(-500, 3_000).valor == pytest.approx(-0.1666666, rel=1e-5)  # EV negativo
    assert ib.p_ativo(10_000, 40_000).valor == 0.25
    assert ib.p_capital_giro(10_000, 6_000, 4_000).valor == 5
    assert not ib.p_capital_giro(10_000, None, 4_000).disponivel
    assert ib.p_ativo_circulante_liquido(10_000, 6_000, 5_000).valor == 10
    assert "aviso" in ib.p_ativo_circulante_liquido(10_000, 6_000, 8_000).detalhes
    assert not ib.p_ativo_circulante_liquido(10_000, 6_000, None).disponivel


def test_provento_liquido():
    assert ib.provento_liquido(1.0, "JCP").valor == pytest.approx(0.85)
    assert ib.provento_liquido(1.0, "JCP", aliquota_jcp=0.20).valor == pytest.approx(0.80)
    assert ib.provento_liquido(1.0, "DIVIDENDO").valor == 1.0
    assert ib.provento_liquido(1.0, "JCP").detalhes["bruto"] == 1.0
    assert not ib.provento_liquido(None, "JCP").disponivel


def test_dividend_yield_e_payout():
    assert ib.dividend_yield(1.5, 25).valor == 0.06
    assert ib.dividend_yield(0, 25).valor == 0  # sem dividendos: DY zero
    assert not ib.dividend_yield(None, 25).disponivel
    assert not ib.dividend_yield(1, 0).disponivel
    assert ib.payout(2, 4).valor == 0.5
    assert not ib.payout(2, -1).disponivel
    assert not ib.payout(None, 4).disponivel


def test_rentabilidade():
    assert ib.roe(200, 1_000).valor == 0.2
    assert not ib.roe(200, -1_000).disponivel  # PL negativo
    assert ib.roe(-100, 1_000).valor == -0.1  # prejuízo: ROE negativo é válido
    assert ib.roa(100, 2_000).valor == 0.05
    # EBIT 1.000, alíquota 34% → NOPAT 660; capital = 2.000 + 1.000
    assert ib.roic(1_000, 2_000, 1_000).valor == pytest.approx(0.22)
    assert ib.roic(1_000, 2_000, 1_000, aliquota=0).valor == pytest.approx(1 / 3)
    assert not ib.roic(1_000, 1_000, -1_000).disponivel  # capital investido zero
    assert not ib.roic(None, 1, 1).disponivel
    assert ib.margem(250, 1_000, "lucro_liquido").valor == 0.25
    assert not ib.margem(250, 0, "lucro_liquido").disponivel
    assert ib.giro_ativos(1_000, 4_000).valor == 0.25


def test_endividamento():
    assert ib.divida_liquida_sobre(300, 100, "ebitda").valor == 3
    assert ib.pl_sobre_ativos(400, 1_000).valor == 0.4
    assert ib.passivos_sobre_ativos(600, 1_000).valor == 0.6
    assert ib.liquidez_corrente(300, 150).valor == 2


def test_cagr():
    # 100 → 161,051 em 5 anos = 10% a.a.
    assert ib.cagr(100, 161.051, 5).valor == pytest.approx(0.10)
    assert not ib.cagr(-100, 200, 5).disponivel  # lucro negativo no início
    assert not ib.cagr(100, 0, 5).disponivel
    assert not ib.cagr(100, 200, 0).disponivel
    assert not ib.cagr(None, 200, 5).disponivel


def test_liquidez_media_diaria():
    r = ib.liquidez_media_diaria([100, 200, None, 300])
    assert r.valor == 200 and r.detalhes["pregoes"] == 3
    assert not ib.liquidez_media_diaria([]).disponivel


def test_registro_consistente():
    assert len(POR_ID) == len(METRICAS), "ids duplicados no registro"
    for m in METRICAS:
        assert m.formula and m.referencia and m.unidade
        assert m.como_dict()["id"] == m.id
