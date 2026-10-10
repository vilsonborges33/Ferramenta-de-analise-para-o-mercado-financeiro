"""Graham, Bazin, Lynch e Greenblatt — casos calculados à mão."""

import math

import pytest

from app.metodologias import bazin, graham, greenblatt, lynch

# ------------------------------------------------------------------ Graham


def test_graham_valor_intrinseco():
    assert graham.valor_intrinseco(4, 25).valor == pytest.approx(math.sqrt(2250))  # 47,43
    assert graham.valor_intrinseco(4, 25, fator=10).valor == pytest.approx(math.sqrt(1000))
    assert "prejuízo" in graham.valor_intrinseco(-1, 25).motivo_indisponivel
    assert "negativo" in graham.valor_intrinseco(4, -3).motivo_indisponivel
    assert not graham.valor_intrinseco(None, 3).disponivel


def test_graham_revisado():
    # LPA 5; g 10% → 8,5 + 20 = 28,5; × 4,4 ÷ 15 (Selic 15%) → 5 × 28,5 × 4,4 ÷ 15 = 41,8
    r = graham.valor_revisado(5, 0.10, 0.15)
    assert r.valor == pytest.approx(41.8) and r.detalhes["multiplo_implicito"] == pytest.approx(28.5)
    assert not graham.valor_revisado(-5, 0.1, 0.15).disponivel
    assert not graham.valor_revisado(5, 0.1, 0).disponivel
    assert not graham.valor_revisado(5, -0.05, 0.15).disponivel  # 8,5 − 10 < 0
    assert not graham.valor_revisado(5, None, 0.15).disponivel


def test_graham_margem_seguranca():
    assert graham.margem_seguranca(50, 40).valor == pytest.approx(0.2)
    assert graham.margem_seguranca(50, 60).valor == pytest.approx(-0.2)
    assert not graham.margem_seguranca(0, 10).disponivel


def dados_defensivo(**alteracoes):
    base = dict(receita_anual=5e9, ativo_circulante=3e9, passivo_circulante=1e9, divida_longo_prazo=1.5e9,
                lucros_anuais=[100] * 10, anos_com_dividendos=25,
                lpa_anuais=[1, 1, 1, 1.1, 1.2, 1.2, 1.3, 1.4, 1.4, 1.5], preco=18, vpa=12)
    base.update(alteracoes)
    return graham.DadosDefensivo(**base)


def test_graham_checklist_todos_atendidos():
    # LPA médio 3 últimos = 1,4333; início = 1 → +43%; P/L = 18 ÷ 1,4333 = 12,6; P/VP = 1,5
    r = graham.checklist_defensivo(dados_defensivo())
    assert r.valor == 7 and r.detalhes["indisponiveis"] == 0


def test_graham_checklist_falhas_e_indisponiveis():
    r = graham.checklist_defensivo(dados_defensivo(
        receita_anual=1e9, divida_longo_prazo=5e9, lucros_anuais=[100] * 9 + [-1], anos_com_dividendos=None,
        preco=40, vpa=12))
    nomes = {c["nome"]: c["atendido"] for c in r.detalhes["criterios"]}
    assert nomes["Porte adequado"] is False
    assert nomes["Condição financeira sólida"] is False
    assert nomes["Lucros positivos"] is False
    assert nomes["Dividendos ininterruptos"] is None
    assert nomes["P/L moderado"] is False  # 40 ÷ 1,43 = 27,9
    assert nomes["P/VP moderado"] is False  # 3,3 e produto > 22,5
    assert r.valor == 1  # só crescimento do LPA


def test_graham_checklist_historico_curto_e_pvp_compensado():
    r = graham.checklist_defensivo(dados_defensivo(lucros_anuais=[1, 2], lpa_anuais=[1, 2], vpa=None,
                                                   receita_anual=None, passivo_circulante=0,
                                                   anos_com_dividendos=None))
    assert r.valor == 0 and r.detalhes["indisponiveis"] >= 5
    # P/VP 2 > 1,5, mas P/L × P/VP = 9 × 2 = 18 ≤ 22,5 → atende
    lpas = [1] * 7 + [2, 2, 2]
    r2 = graham.checklist_defensivo(dados_defensivo(lpa_anuais=lpas, preco=18, vpa=9))
    assert {c["nome"]: c["atendido"] for c in r2.detalhes["criterios"]}["P/VP moderado"] is True
    # LPA médio inicial negativo
    r3 = graham.checklist_defensivo(dados_defensivo(lpa_anuais=[-1, -1, -1] + [1] * 7))
    assert {c["nome"]: c["atendido"] for c in r3.detalhes["criterios"]}["Crescimento do LPA"] is True
    r4 = graham.checklist_defensivo(dados_defensivo(lpa_anuais=[1] * 7 + [-1, -1, -1]))
    assert {c["nome"]: c["atendido"] for c in r4.detalhes["criterios"]}["P/L moderado"] is False


# ------------------------------------------------------------------- Bazin


def test_bazin_preco_teto_e_potencial():
    assert bazin.preco_teto(1.2).valor == pytest.approx(20)
    assert bazin.preco_teto(1.2, 0.08).valor == pytest.approx(15)
    assert "sem proventos" in bazin.preco_teto(0).motivo_indisponivel
    assert not bazin.preco_teto(1, 0).disponivel
    assert not bazin.preco_teto(None).disponivel
    assert bazin.potencial(20, 16).valor == pytest.approx(0.25)
    assert not bazin.potencial(20, 0).disponivel


def test_bazin_media_e_criterios():
    assert bazin.dividendo_medio_anual([9, 1, 2, 3], 3).valor == 2
    assert not bazin.dividendo_medio_anual([1, 2], 3).disponivel
    assert not bazin.dividendo_medio_anual([1, 2], 0).disponivel
    assert bazin.endividamento_baixo(50, 100).valor == 1
    assert bazin.endividamento_baixo(150, 100).valor == 0
    assert bazin.endividamento_baixo(-50, 100).valor == 1  # caixa líquido
    assert bazin.endividamento_baixo(10, -100).valor == 0
    assert not bazin.endividamento_baixo(None, 1).disponivel
    assert bazin.regularidade_proventos([1, 1, 1, 1, 1]).valor == 1
    r = bazin.regularidade_proventos([1, 0, 1, 1, 1])
    assert r.valor == 0 and r.detalhes["anos_com_pagamento"] == 4
    assert not bazin.regularidade_proventos([1, 1]).disponivel


def test_bazin_projetivo():
    # lucro 1.000 × payout 50% ÷ 100 ações = R$ 5 por ação ÷ 6% = 83,33
    r = bazin.preco_teto_projetivo(1000, 0.5, 100)
    assert r.valor == pytest.approx(83.3333, rel=1e-4) and r.detalhes["dividendo_projetado"] == 5
    assert not bazin.preco_teto_projetivo(1000, 0.5, 0).disponivel
    assert not bazin.preco_teto_projetivo(1000, 2, 100).disponivel
    assert not bazin.preco_teto_projetivo(-1000, 0.5, 100).disponivel  # prejuízo projetado
    assert bazin.yield_projetivo(5, 50).valor == pytest.approx(0.1)
    assert not bazin.yield_projetivo(5, 0).disponivel


# ------------------------------------------------------------------- Lynch


def test_lynch_peg_e_indice():
    assert lynch.peg(15, 0.15).valor == pytest.approx(1)
    assert not lynch.peg(-5, 0.15).disponivel
    assert not lynch.peg(15, 0).disponivel
    # (12 + 4) ÷ 8 = 2
    assert lynch.indice_lynch(0.12, 0.04, 8).valor == pytest.approx(2)
    assert not lynch.indice_lynch(0.12, 0.04, 0).disponivel


def test_lynch_preco_justo_sem_teto_com_aviso():
    r = lynch.preco_justo(2, 0.15, lucro_base=80, lucro_atual=100)
    assert r.valor == pytest.approx(30) and "aviso" not in r.detalhes
    alto = lynch.preco_justo(2, 0.80)
    assert alto.valor == pytest.approx(160)  # sem teto
    assert alto.detalhes["aviso"] == lynch.AVISO_ATIPICO
    assert "aviso" in lynch.preco_justo(2, 0.15, lucro_base=10, lucro_atual=100).detalhes  # efeito de base
    assert "aviso" in lynch.preco_justo(2, 0.15, lucro_base=-5, lucro_atual=100).detalhes
    assert lynch.preco_justo(2, 0.15, fator=2).valor == pytest.approx(60)
    assert not lynch.preco_justo(-2, 0.15).disponivel
    assert not lynch.preco_justo(2, -0.1).disponivel


@pytest.mark.parametrize("crescimento, lucros, pvp, setor, esperado", [
    (0.30, [10, 20, 30, -5], 2.0, None, "recuperacao"),
    (0.30, [10, -2, 15, 20], 2.0, None, "recuperacao"),
    (0.05, [10, 11, 12, 13], 2.0, "Siderurgia e Metalurgia", "ciclica"),
    (0.05, [10, 40, 5, 30], 2.0, "Varejo", "ciclica"),
    (0.05, [10, 11, 12, 13], 0.7, "Varejo", "ativos_ocultos"),
    (0.25, [10, 11, 12, 13], 3.0, "Varejo", "crescimento_rapido"),
    (0.12, [10, 11, 12, 13], 3.0, "Varejo", "robusta"),
    (0.04, [10, 11, 12, 13], 3.0, "Varejo", "crescimento_lento"),
])
def test_lynch_categorias(crescimento, lucros, pvp, setor, esperado):
    r = lynch.classificar(crescimento, lucros, pvp, setor)
    assert r.detalhes["categoria"] == esperado and r.detalhes["regra"]


def test_lynch_categoria_sem_crescimento():
    assert not lynch.classificar(None, [10, 11, 12, 13], 2.0, None).disponivel


# -------------------------------------------------------------- Greenblatt


def test_greenblatt_indicadores():
    assert greenblatt.earnings_yield(100, 1000).valor == pytest.approx(0.1)
    assert not greenblatt.earnings_yield(100, -50).disponivel  # EV negativo
    # (500 − 100) − (300 − 50) = 150
    assert greenblatt.capital_giro_liquido(500, 100, 300, 50).valor == 150
    assert not greenblatt.capital_giro_liquido(None, 1, 1, 1).disponivel
    r = greenblatt.retorno_sobre_capital(100, 150, 350)
    assert r.valor == pytest.approx(0.2) and r.detalhes["capital_empregado"] == 500
    assert greenblatt.retorno_sobre_capital(100, -200, 400).valor == pytest.approx(0.25)  # CG negativo → 0
    assert not greenblatt.retorno_sobre_capital(100, -10, 0).disponivel


def test_greenblatt_ranking_e_exclusoes():
    C = greenblatt.Candidato
    candidatos = [
        C("AAAA3", 0.10, 0.30, setor="Varejo", liquidez_diaria=5e6),
        C("BBBB3", 0.15, 0.10, setor="Varejo", liquidez_diaria=5e6),
        C("CCCC3", 0.05, 0.20, setor="Varejo", liquidez_diaria=5e6),
        C("BANC4", 0.20, 0.50, tipo_plano_contas="banco"),
        C("ENER3", 0.20, 0.50, setor="Energia Elétrica"),
        C("SEMD3", None, 0.40, setor="Varejo", liquidez_diaria=5e6),
        C("ILIQ3", 0.30, 0.90, setor="Varejo", liquidez_diaria=1e3),
    ]
    r = greenblatt.ranking(candidatos, greenblatt.ParametrosGreenblatt(liquidez_minima=1e6))
    # EY: B1 A2 C3; ROC: A1 C2 B3 → somas A3 B4 C5
    assert [(p.ticker, p.soma) for p in r.ranking] == [("AAAA3", 3), ("BBBB3", 4), ("CCCC3", 5)]
    assert r.excluidos == {"BANC4": "financeira/seguradora", "ENER3": "utility",
                           "SEMD3": "dados insuficientes (EY ou ROC indisponível)",
                           "ILIQ3": "liquidez abaixo do mínimo"}
    sem_exclusao = greenblatt.ranking(candidatos[:5], greenblatt.ParametrosGreenblatt(
        excluir_financeiras=False, excluir_utilities=False))
    assert sem_exclusao.ranking[0].ticker in {"BANC4", "ENER3"} and len(sem_exclusao.ranking) == 5
