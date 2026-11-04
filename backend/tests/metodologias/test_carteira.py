"""Carteira: preço médio, resultado, eventos, proventos e rentabilidade por cotas — conferidos à mão."""

from datetime import date

import pytest

from app.metodologias import carteira as c


def mov(d, tipo, qtd, preco=0.0, taxas=0.0, ativo="ABCD3"):
    return c.Movimento(date(2025, 1, d), ativo, tipo, qtd, preco, taxas)


def test_preco_medio_venda_e_resultado():
    p = c.consolidar([mov(2, "COMPRA", 100, 10, 2), mov(5, "COMPRA", 100, 12), mov(9, "VENDA", 50, 15, 1)])["ABCD3"]
    # custo = 1000 + 2 + 1200 = 2202 → PM 11,01; venda de 50 a 15: (15 − 11,01) × 50 − 1 = 198,50
    assert p.quantidade == 150 and p.preco_medio == pytest.approx(11.01)
    assert p.resultado_realizado == pytest.approx(198.5) and p.custo == pytest.approx(150 * 11.01)
    assert p.total_investido == pytest.approx(2202) and p.primeira_compra == date(2025, 1, 2)


def test_eventos_e_venda_total():
    p = c.consolidar([mov(2, "COMPRA", 100, 10), mov(3, "DESDOBRAMENTO", 100)])["ABCD3"]
    assert p.quantidade == 200 and p.preco_medio == pytest.approx(5)  # custo 1000 ÷ 200
    p = c.consolidar([mov(2, "COMPRA", 100, 10), mov(3, "GRUPAMENTO", 90)])["ABCD3"]
    assert p.quantidade == 10 and p.preco_medio == pytest.approx(100)
    p = c.consolidar([mov(2, "COMPRA", 10, 10), mov(3, "VENDA", 10, 8)])["ABCD3"]
    assert p.quantidade == 0 and p.preco_medio is None and p.resultado_realizado == pytest.approx(-20)
    with pytest.raises(c.ErroCarteira, match="acima da posição"):
        c.consolidar([mov(2, "COMPRA", 10, 10), mov(3, "VENDA", 11, 8)])
    with pytest.raises(c.ErroCarteira):
        c.consolidar([mov(2, "XPTO", 1, 1)])


def test_proventos_pela_quantidade_na_data_com_e_yoc():
    p = c.consolidar([mov(2, "COMPRA", 100, 10), mov(10, "COMPRA", 100, 10), mov(20, "VENDA", 200, 11)])["ABCD3"]
    recebidos = c.proventos_recebidos(p, [(date(2025, 1, 1), 1.0), (date(2025, 1, 5), 0.5),
                                          (date(2025, 1, 15), 0.5), (date(2025, 1, 25), 9.0)])
    assert recebidos == [(date(2025, 1, 5), 50.0), (date(2025, 1, 15), 100.0)]
    assert c.yield_on_cost(1.2, 10).valor == pytest.approx(0.12)
    assert not c.yield_on_cost(None, 10).disponivel


def test_rentabilidade_por_cotas_neutraliza_aportes():
    # dia 1: aporte de 100; dia 2: sobe 10% (110); dia 3: aporte de 110 → 220 sem ganho; dia 4: provento de 22
    r = c.rentabilidade_cotas([100, 110, 220, 220], [100, 0, 110, 0], [0, 0, 0, 22])
    assert r.valor == pytest.approx(1.1 * 1.1 - 1)
    assert r.detalhes["acumulado"] == pytest.approx([0, 0.1, 0.1, 0.21])
    assert not c.rentabilidade_cotas([1], [0], [0]).disponivel
    assert c.alocacao({"A": 75, "B": 25, "C": 0}) == {"A": 0.75, "B": 0.25}
