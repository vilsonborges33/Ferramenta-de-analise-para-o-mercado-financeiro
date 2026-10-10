"""DCF (livro 8), Damodaran (livro 9) e Gordon ajustado de FII — casos calculados à mão."""

import pytest

from app.metodologias import damodaran, dcf, fii

# --------------------------------------------------------------------- DCF


def test_projecao_e_fcff():
    p = dcf.PremissasProjecao(receita_base=100, crescimento_receita=[0.1, 0.1], margem_ebit=0.2, aliquota=0.3,
                              da_pct_receita=0.05, capex_pct_receita=0.07, capital_giro_pct_variacao_receita=0.1)
    a1, a2 = dcf.projetar(p)
    # ano 1: receita 110, EBIT 22, NOPAT 15,4, D&A 5,5, capex 7,7, ΔCG 1,0 → FCFF 12,2
    assert (a1.receita, a1.ebit) == pytest.approx((110, 22))
    assert a1.fcff == pytest.approx(12.2)
    # ano 2: receita 121, NOPAT 16,94, D&A 6,05, capex 8,47, ΔCG 1,1 → 13,42
    assert a2.fcff == pytest.approx(13.42)
    margens = dcf.projetar(dcf.PremissasProjecao(100, [0.0, 0.0], [0.1, 0.2], aliquota=0))
    assert [a.ebit for a in margens] == pytest.approx([10, 20])
    with pytest.raises(ValueError):
        dcf.projetar(dcf.PremissasProjecao(100, [0.1, 0.1], [0.1]))


def test_fcff_fcfe_wacc():
    assert dcf.fcff(100, 0.34, 20, 30, 5).valor == pytest.approx(51)
    assert not dcf.fcff(None, 0.34, 1, 1, 1).disponivel
    # 51 − 10 × 0,66 + 4 = 48,4
    assert dcf.fcfe(51, 10, 0.34, 4).valor == pytest.approx(48.4)
    assert not dcf.fcfe(51, None, 0.34, 4).disponivel
    # 0,6 × 15% + 0,4 × 10% × 0,66 = 11,64%
    w = dcf.wacc(600, 400, 0.15, 0.10, 0.34)
    assert w.valor == pytest.approx(0.1164) and w.detalhes["peso_equity"] == pytest.approx(0.6)
    assert not dcf.wacc(0, 0, 0.1, 0.1, 0.3).disponivel
    assert not dcf.wacc(-1, 10, 0.1, 0.1, 0.3).disponivel
    assert not dcf.wacc(None, 10, 0.1, 0.1, 0.3).disponivel


def test_valor_terminal_e_avaliacao():
    assert dcf.valor_terminal(10, 0.10, 0.02).valor == pytest.approx(127.5)  # 10,2 ÷ 0,08
    assert not dcf.valor_terminal(10, 0.05, 0.05).disponivel
    assert not dcf.valor_terminal(None, 0.1, 0.02).disponivel
    # perpetuidade de 10 a 10%: valor = 100; equity = 100 − 20; por ação = 80 ÷ 8 = 10
    r = dcf.avaliar([10, 10], 0.10, 0.0, divida_liquida=20, acoes=8)
    assert r.valor == pytest.approx(10)
    assert r.detalhes["valor_operacional"] == pytest.approx(100)
    assert r.detalhes["vp_fluxos"] == pytest.approx(10 / 1.1 + 10 / 1.21)
    assert r.detalhes["peso_terminal"] == pytest.approx((100 / 1.21) / 100)
    assert dcf.avaliar([10, 10], 0.10, 0.0).valor == pytest.approx(100)  # sem ações → equity
    assert not dcf.avaliar([], 0.1, 0.0).disponivel
    assert not dcf.avaliar([10], 0.02, 0.03).disponivel
    assert not dcf.avaliar([10], -1, -2).disponivel
    assert not dcf.avaliar([10], None, 0.0).disponivel


def test_tabela_sensibilidade():
    tabela = dcf.tabela_sensibilidade([10, 10], [0.08, 0.10], [0.0, 0.09])
    assert tabela[1][0] == pytest.approx(100)
    assert tabela[0][1] is None  # r ≤ g
    assert tabela[0][0] == pytest.approx(125)  # perpetuidade 10 ÷ 0,08


# --------------------------------------------------------------- Damodaran


def test_custo_capital_e_betas():
    # 4,5% + 1,2 × 5% + 3% (risco país) = 13,5%
    assert damodaran.custo_capital_proprio(0.045, 1.2, 0.05, 0.03).valor == pytest.approx(0.135)
    assert damodaran.custo_capital_proprio(0.045, 1.2, 0.05, 0.03, lambda_pais=0.5).valor == pytest.approx(0.12)
    assert not damodaran.custo_capital_proprio(None, 1, 0.05).disponivel
    assert damodaran.beta_desalavancado(1.2, 0.5, 0.34).valor == pytest.approx(1.2 / 1.33)
    assert not damodaran.beta_desalavancado(1.2, -10, 0.34).disponivel
    assert damodaran.beta_realavancado(0.9, 0.5, 0.34).valor == pytest.approx(1.197)
    assert not damodaran.beta_realavancado(0.9, -0.5, 0.34).disponivel
    assert not damodaran.beta_realavancado(None, 0.5, 0.34).disponivel
    # 10% em US$ com inflação de 2,5% → BRL com inflação de 4,5%: 1,10 × 1,045 ÷ 1,025 − 1
    assert damodaran.converter_taxa(0.10, 0.025, 0.045).valor == pytest.approx(1.10 * 1.045 / 1.025 - 1)
    assert not damodaran.converter_taxa(0.1, None, 0.04).disponivel


def test_gordon_e_dois_estagios():
    assert damodaran.gordon(2, 0.12, 0.05).valor == pytest.approx(30)  # 2,10 ÷ 0,07
    assert not damodaran.gordon(0, 0.12, 0.05).disponivel  # sem dividendos
    assert not damodaran.gordon(2, 0.05, 0.05).disponivel
    assert not damodaran.gordon(None, 0.12, 0.05).disponivel
    # D1 = 1,2; D2 = 1,44; terminal = 1,44 × 1,05 ÷ 0,05 = 30,24
    esperado = 1.2 / 1.1 + 1.44 / 1.21 + 30.24 / 1.21
    r = damodaran.ddm_dois_estagios(1, 0.10, 0.20, 2, 0.05)
    assert r.valor == pytest.approx(esperado) and r.detalhes["vp_terminal"] == pytest.approx(30.24 / 1.21)
    # Ke do estágio estável diferente
    r2 = damodaran.ddm_dois_estagios(1, 0.10, 0.20, 2, 0.05, custo_capital_estavel=0.08)
    assert r2.valor == pytest.approx(1.2 / 1.1 + 1.44 / 1.21 + (1.512 / 0.03) / 1.21)
    assert not damodaran.ddm_dois_estagios(0, 0.1, 0.2, 2, 0.05).disponivel
    assert not damodaran.ddm_dois_estagios(1, 0.1, 0.2, 0, 0.05).disponivel
    assert not damodaran.ddm_dois_estagios(1, 0.04, 0.2, 2, 0.05).disponivel
    assert not damodaran.ddm_dois_estagios(None, 0.1, 0.2, 2, 0.05).disponivel


def test_multiplos_do_setor_e_narrativa():
    r = damodaran.preco_por_multiplo_setor([8, 10, 12, -5, None], 2)
    assert r.valor == pytest.approx(20) and r.detalhes["pares"] == 3
    assert not damodaran.preco_por_multiplo_setor([8, 10], 2).disponivel
    assert not damodaran.preco_por_multiplo_setor([8, 10, 12], -1).disponivel  # prejuízo
    assert not damodaran.preco_por_multiplo_setor([8, 10, 12], None).disponivel
    faltam = damodaran.premissas_sem_justificativa({"crescimento": 0.1, "margem": 0.2, "wacc": 0.12},
                                                   {"crescimento": "Expansão de lojas", "margem": "  "})
    assert faltam == ["margem", "wacc"]


# --------------------------------------------------------- FII: Gordon ajustado


def test_gordon_ajustado_fii():
    assert fii.taxa_liquida(0.12).valor == pytest.approx(0.102)
    assert not fii.taxa_liquida(None).disponivel
    # k = 12% × 0,85 + 2% = 12,2%; preço = 10 × 1,03 ÷ (0,122 − 0,03)
    r = fii.gordon_ajustado(10, 0.12, 0.02, 0.03)
    assert r.valor == pytest.approx(10.3 / 0.092) and r.detalhes["taxa_exigida"] == pytest.approx(0.122)
    assert fii.gordon_ajustado(10, 0.12, 0.02, 0.03, usar_taxa_liquida=False).valor == pytest.approx(10.3 / 0.11)
    assert not fii.gordon_ajustado(0, 0.12, 0.02, 0.03).disponivel
    assert not fii.gordon_ajustado(10, 0.02, 0.0, 0.05).disponivel
    assert not fii.gordon_ajustado(None, 0.12, 0.02, 0.03).disponivel
