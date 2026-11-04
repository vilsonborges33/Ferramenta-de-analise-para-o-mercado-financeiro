"""Avaliação das condições de alerta (lógica pura)."""

from app.servicos.alertas import avaliar, descrever


def test_avaliar_comparacoes():
    assert avaliar("preco_abaixo", 30, 29.9) is True
    assert avaliar("preco_abaixo", 30, 30.1) is False
    assert avaliar("preco_acima", 30, 30) is True
    assert avaliar("dy_acima", 0.08, 0.0723) is False
    assert avaliar("pvp_abaixo", 1.0, 0.87) is True


def test_avaliar_teto_bazin_compara_com_o_preco():
    assert avaliar("abaixo_teto_bazin", None, 61.07, preco=50.71) is True
    assert avaliar("abaixo_teto_bazin", None, 40.0, preco=50.71) is False
    assert avaliar("abaixo_teto_bazin", None, 61.07, preco=None) is None


def test_dado_indisponivel_nao_dispara():
    assert avaliar("pl_abaixo", 10, None) is None
    assert avaliar("preco_abaixo", None, 10) is None
    assert avaliar("inexistente", 1, 1) is None


def test_descrever():
    assert descrever("dy_acima", 0.08) == "Dividend yield 12 m acima de 8,00%"
    assert descrever("preco_abaixo", 1234.5) == "Cotação abaixo de 1.234,50"
    assert descrever("abaixo_teto_bazin", None) == "Cotação abaixo do preço teto de Bazin"
