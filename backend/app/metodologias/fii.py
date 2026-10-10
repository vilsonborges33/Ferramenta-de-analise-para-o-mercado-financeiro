"""Indicadores de fundos imobiliários a partir dos informes mensais da CVM.

Referência: Benjamin Graham, *O Investidor Inteligente* — preço comparado ao valor patrimonial.
"""

from collections.abc import Sequence

from app.metodologias.tipos import Numero, Resultado, faltando, indisponivel, ok


def p_vp_cota(preco: Numero, valor_patrimonial_cota: Numero) -> Resultado:
    """P/VP do FII = cotação ÷ valor patrimonial por cota."""
    if f := faltando(preco=preco, valor_patrimonial_cota=valor_patrimonial_cota):
        return f
    if valor_patrimonial_cota <= 0:
        return indisponivel("valor patrimonial por cota não positivo")
    return ok(preco / valor_patrimonial_cota)


def composicao_percentuais(percentuais_mensais: Sequence[Numero], meses_exigidos: int = 12) -> Resultado:
    """Retorno acumulado = Π(1 + r_mês) − 1, com r em fração. Exige a janela completa."""
    if len(percentuais_mensais) < meses_exigidos or any(p is None for p in percentuais_mensais):
        return indisponivel(f"dado indisponível: menos de {meses_exigidos} meses de informes")
    acumulado = 1.0
    for r in percentuais_mensais[-meses_exigidos:]:
        acumulado *= 1 + r
    return ok(acumulado - 1)


def soma_percentuais(percentuais_mensais: Sequence[Numero], meses_exigidos: int = 12) -> Resultado:
    """Soma simples dos percentuais mensais (usada para o DY informado em 12 meses)."""
    if len(percentuais_mensais) < meses_exigidos or any(p is None for p in percentuais_mensais):
        return indisponivel(f"dado indisponível: menos de {meses_exigidos} meses de informes")
    return ok(sum(percentuais_mensais[-meses_exigidos:]))
