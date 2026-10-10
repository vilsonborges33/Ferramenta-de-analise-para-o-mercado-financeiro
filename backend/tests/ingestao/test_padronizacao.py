"""Padronização com linhas sintéticas (valores fictícios, só para conferir a aritmética)."""

from datetime import date

import pytest

from app.ingestao.padronizacao import Regra, padronizar


def linha(documento, tipo, codigo, descricao, valor, fim, inicio=None, versao=1, consolidado=True, ref=None):
    return {
        "documento": documento, "tipo": tipo, "conta_codigo": codigo, "conta_descricao": descricao,
        "valor": valor, "data_fim": fim, "data_inicio": inicio, "versao": versao, "consolidado": consolidado,
        "data_referencia": ref or fim,
    }


def itr(ano, q, receita_tri, receita_acum, lucro_tri, da_acum, versao=1):
    fim = {1: date(ano, 3, 31), 2: date(ano, 6, 30), 3: date(ano, 9, 30)}[q]
    ini_tri = date(ano, 3 * q - 2, 1)
    ini_ano = date(ano, 1, 1)
    linhas = [
        linha("ITR", "DRE", "3.01", "Receita", receita_tri, fim, ini_tri, versao),
        linha("ITR", "DRE", "3.11", "Lucro", lucro_tri, fim, ini_tri, versao),
        linha("ITR", "DFC_MI", "6.01.01.02", "Depreciação e amortização", da_acum, fim, ini_ano, versao),
        linha("ITR", "BPA", "1", "Ativo Total", 1000 + q, fim, None, versao),
        linha("ITR", "BPP", "2.03", "Patrimônio Líquido Consolidado", 500 + q, fim, None, versao),
        linha("ITR", "BPP", "2.03.09", "Participação dos Acionistas Não Controladores", 50, fim, None, versao),
    ]
    if q > 1:
        linhas.append(linha("ITR", "DRE", "3.01", "Receita", receita_acum, fim, ini_ano, versao))
        lucro_acum = {2: 21, 3: 33}[q]
        linhas.append(linha("ITR", "DRE", "3.11", "Lucro", lucro_acum, fim, ini_ano, versao))
    return linhas


def dfp(ano, receita, lucro, da):
    fim, ini = date(ano, 12, 31), date(ano, 1, 1)
    return [
        linha("DFP", "DRE", "3.01", "Receita", receita, fim, ini),
        linha("DFP", "DRE", "3.11", "Lucro", lucro, fim, ini),
        linha("DFP", "DFC_MI", "6.01.01.02", "Depreciação e amortização", da, fim, ini),
        linha("DFP", "BPA", "1", "Ativo Total", 2000, fim),
        linha("DFP", "BPP", "2.03", "Patrimônio Líquido Consolidado", 900, fim),
    ]


def por_chave(periodos):
    return {(p.periodo, p.tipo_periodo): p for p in periodos}


def test_trimestres_q4_e_ttm():
    linhas = (
        itr(2024, 1, 100, 100, 10, 5) + itr(2024, 2, 110, 210, 11, 11) + itr(2024, 3, 120, 330, 12, 18)
        + dfp(2024, 460, 50, 26)
    )
    p = por_chave(padronizar(linhas))
    assert p[("2024-A", "ano")].campos["receita_liquida"] == 460
    assert p[("2024-T2", "trimestre")].campos["receita_liquida"] == 110
    # DFC trimestral = acumulado − acumulado anterior
    assert p[("2024-T1", "trimestre")].campos["depreciacao_amortizacao"] == 5
    assert p[("2024-T2", "trimestre")].campos["depreciacao_amortizacao"] == 6
    assert p[("2024-T3", "trimestre")].campos["depreciacao_amortizacao"] == 7
    # 4º trimestre = anual − 9 meses
    t4 = p[("2024-T4", "trimestre")]
    assert t4.campos["receita_liquida"] == 460 - 330
    assert t4.campos["lucro_liquido"] == 50 - 33
    assert t4.campos["depreciacao_amortizacao"] == 26 - 18
    assert t4.campos["ativo_total"] == 2000  # balanço da DFP
    # TTM no 4º trimestre = soma dos 4 trimestres = anual
    ttm = p[("2024-T4", "ttm")]
    assert ttm.campos["receita_liquida"] == pytest.approx(460)
    assert ttm.campos["lucro_liquido_controladores"] == pytest.approx(50)
    assert ttm.campos["patrimonio_liquido_controladores"] == 900
    assert ("2024-T3", "ttm") not in p  # sem 4 trimestres anteriores


def test_ttm_atravessa_o_ano():
    linhas = (
        itr(2024, 1, 100, 100, 10, 5) + itr(2024, 2, 110, 210, 11, 11) + itr(2024, 3, 120, 330, 12, 18)
        + dfp(2024, 460, 50, 26) + itr(2025, 1, 140, 140, 14, 9)
    )
    ttm = por_chave(padronizar(linhas))[("2025-T1", "ttm")]
    assert ttm.campos["receita_liquida"] == 110 + 120 + 130 + 140
    assert ttm.data_inicio == date(2024, 4, 1)
    assert ttm.campos["patrimonio_liquido_controladores"] == 501 - 50
    assert ttm.campos["passivo_total"] == 1001 - 501
    assert len(ttm.insumos["receita_liquida"]) >= 4


def test_versao_mais_recente_e_consolidado_preferido():
    fim, ini = date(2023, 12, 31), date(2023, 1, 1)
    linhas = [
        linha("DFP", "DRE", "3.01", "Receita", 100, fim, ini, versao=1),
        linha("DFP", "DRE", "3.01", "Receita", 120, fim, ini, versao=2),
        linha("DFP", "DRE", "3.01", "Receita", 999, fim, ini, versao=3, consolidado=False),
    ]
    anual = por_chave(padronizar(linhas))[("2023-A", "ano")]
    assert anual.campos["receita_liquida"] == 120
    assert anual.consolidado is True and anual.versao_usada == 2


def test_somente_individual_e_usado_quando_nao_ha_consolidado():
    fim, ini = date(2023, 12, 31), date(2023, 1, 1)
    anual = por_chave(padronizar([linha("DFP", "DRE", "3.01", "Receita", 80, fim, ini, consolidado=False)]))
    assert anual[("2023-A", "ano")].consolidado is False


def test_contas_somadas_capex_e_dividendos():
    fim, ini = date(2023, 12, 31), date(2023, 1, 1)
    linhas = [
        linha("DFP", "DFC_MI", "6.02.01", "Aquisição de imobilizado", -30, fim, ini),
        linha("DFP", "DFC_MI", "6.02.02", "Adições ao intangível", -5, fim, ini),
        linha("DFP", "DFC_MI", "6.02.03", "Venda de imobilizado", 3, fim, ini),
        linha("DFP", "DFC_MI", "6.03.01", "Dividendos pagos", -20, fim, ini),
        linha("DFP", "DFC_MI", "6.03.02", "Juros sobre o capital próprio pagos", -10, fim, ini),
    ]
    c = por_chave(padronizar(linhas))[("2023-A", "ano")].campos
    assert c["capex"] == -35
    assert c["dividendos_pagos"] == -30


def test_plano_banco_por_descricao():
    fim, ini = date(2023, 12, 31), date(2023, 1, 1)
    linhas = [
        linha("DFP", "DRE", "3.09", "Lucro ou Prejuízo Líquido Consolidado do Período", 300, fim, ini),
        linha("DFP", "DRE", "3.09.01", "Atribuído a Sócios da Empresa Controladora", 280, fim, ini),
        linha("DFP", "BPP", "2.08", "Patrimônio Líquido Consolidado", 2000, fim),
        linha("DFP", "BPP", "2.08.09", "Participação de Acionistas Não Controladores", 100, fim),
    ]
    c = por_chave(padronizar(linhas, "banco"))[("2023-A", "ano")].campos
    assert c["lucro_liquido"] == 300
    assert c["lucro_liquido_controladores"] == 280
    assert c["patrimonio_liquido_controladores"] == 1900
    assert "ebit" not in c


def test_regra_por_nivel():
    r = Regra("BPP", "x", prefixo="2.", padrao="patrim", nivel=2)
    assert r.casa("2.03", "Patrimônio Líquido")
    assert not r.casa("2.03.01", "Patrimônio Líquido")
