from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.db.modelos import Ativo, CotacaoDiaria, Provento, SerieEconomica
from app.ingestao.base import lote
from app.metodologias import portfolio
from app.servicos import historico
from tests.api.test_ponta_a_ponta import RECEITAS, cliente  # noqa: F401  (fixture)


def test_historico_anual_da_dfp(cliente):  # noqa: F811
    r = cliente.get("/acoes/EXMP3/historico").json()
    anos = r["anos"]
    assert [a["ano"] for a in anos] == sorted(RECEITAS)
    ultimo = anos[-1]
    assert ultimo["receita_liquida"] == pytest.approx(8000 * 1000) and ultimo["fonte"] == "CVM_DFP"
    assert ultimo["lucro_liquido"] == pytest.approx(1_000_000)
    assert ultimo["margem_liquida"] == pytest.approx(0.125) and ultimo["roe"] == pytest.approx(0.2)
    assert ultimo["divida_liquida"] == pytest.approx(1_400_000)
    assert ultimo["cotacao_fim_ano"] is None  # a única cotação é de 2025, depois do exercício de 2024
    assert cliente.get("/acoes/XXXX3/historico").status_code == 404


def test_dividendos_por_ano_liquidos(cliente, sessao):  # noqa: F811
    ativo = sessao.scalar(select(Ativo).where(Ativo.ticker == "EXMP3"))
    with lote(sessao, "YAHOO_FINANCE") as ctx:
        for tipo, valor, dia in (("DIVIDENDO", "0.50", date(2025, 3, 10)), ("JCP", "0.40", date(2025, 8, 10))):
            sessao.add(Provento(ativo_id=ativo.id, tipo=tipo, valor_por_cota=Decimal(valor), data_com=dia,
                                data_ex=dia, **ctx.procedencia(dia)))
    sessao.commit()
    r = cliente.get("/ativos/EXMP3/dividendos").json()
    assert len(r["pagamentos"]) == 2 and r["pagamentos"][0]["tipo"] == "JCP"
    assert r["pagamentos"][0]["valor_liquido"] == pytest.approx(0.34)  # JCP com 15% de IR
    ano_2025 = next(a for a in r["anos"] if a["ano"] == 2025)
    assert ano_2025["total_liquido"] == pytest.approx(0.84)
    assert ano_2025["dividend_yield"] == pytest.approx(0.084)  # cotação R$ 10
    assert r["dy_medio"] == pytest.approx(0.084)


def test_volatilidade_e_taxa_acumulada():
    assert not portfolio.volatilidade_anualizada([10.0] * 5).disponivel
    assert portfolio.volatilidade_anualizada([10.0] * 30).valor == pytest.approx(0)
    precos = [10.0, 11.0] * 15
    r = portfolio.retornos_simples(precos)
    import numpy as np
    assert portfolio.volatilidade_anualizada(precos).valor == pytest.approx(np.std(r, ddof=1) * 252 ** 0.5)
    assert portfolio.taxa_acumulada([0.04] * 252).valor == pytest.approx(1.0004 ** 252 - 1)
    assert not portfolio.taxa_acumulada([]).disponivel


def test_risco_12m(cliente, sessao):  # noqa: F811
    ativo = sessao.scalar(select(Ativo).where(Ativo.ticker == "EXMP4"))
    hoje = date(2025, 6, 30)
    with lote(sessao, "YAHOO_FINANCE") as ctx:
        for n in range(40):
            dia = hoje - timedelta(days=40 - n)
            sessao.add(CotacaoDiaria(ativo_id=ativo.id, data=dia, fechamento=Decimal(12 + (n % 2)),
                                     **ctx.procedencia(dia)))
    with lote(sessao, "BCB_SGS") as ctx:
        for n in range(30):
            dia = hoje - timedelta(days=n)
            sessao.add(SerieEconomica(codigo="CDI", data=dia, valor=Decimal("0.04"), **ctx.procedencia(dia)))
    sessao.commit()
    r = historico.risco(sessao, "EXMP4", hoje)
    assert r["volatilidade_12m"]["valor"] > 0 and r["cdi_12m"] == pytest.approx(1.0004 ** 30 - 1)
    esperado = (r["retorno_12m"] - r["cdi_12m"]) / r["volatilidade_12m"]["valor"]
    assert r["sharpe_12m"]["valor"] == pytest.approx(esperado)
    sem = historico.risco(sessao, "EXMP3", hoje)  # só uma cotação
    assert sem["volatilidade_12m"]["valor"] is None and "histórico curto" in sem["sharpe_12m"]["motivo_indisponivel"]


def test_valuation_com_parametros_do_usuario(cliente):  # noqa: F811
    r = cliente.get("/acoes/EXMP3/valuation", params={"fator_graham": 10}).json()
    assert r["graham_valor"] == pytest.approx(50 ** 0.5) and "Não constituem" in r["aviso"]
    assert r["greenblatt_posicao"] in (1, 2) and r["total_formula_magica"] == 2
    assert cliente.get("/acoes/BEXM3/valuation").status_code == 404  # sem cotação


def test_cotacoes_trazem_volume(cliente):  # noqa: F811
    pontos = cliente.get("/ativos/EXMP3/cotacoes").json()
    assert pontos[-1]["volume"] == pytest.approx(5_000_000)
