"""REITs (EUA): FFO e AFFO, as medidas de geração de caixa usadas no lugar do lucro.

Definição NAREIT: FFO = lucro líquido + depreciação e amortização imobiliária − ganhos na venda de imóveis.
AFFO (simplificado) = FFO − investimentos de manutenção (capital improvements). Usados por Damodaran
(*Valuation*, empresas imobiliárias) no lugar do lucro, porque a depreciação de imóveis distorce o resultado.
"""

from app.metodologias.tipos import Numero, Resultado, faltando, indisponivel, ok


def ffo(lucro_liquido: Numero, depreciacao: Numero, ganho_venda_imoveis: Numero = 0.0) -> Resultado:
    if f := faltando(lucro_liquido=lucro_liquido, depreciacao=depreciacao):
        return f
    return ok(lucro_liquido + depreciacao - (ganho_venda_imoveis or 0.0))


def affo(ffo_: Numero, capex_manutencao: Numero) -> Resultado:
    """capex_manutencao como saída de caixa (negativo, como na DFC) ou positivo; o efeito é sempre redutor."""
    if f := faltando(ffo=ffo_, capex_manutencao=capex_manutencao):
        return f
    return ok(ffo_ - abs(capex_manutencao))


def por_acao(valor: Numero, acoes: Numero) -> Resultado:
    if f := faltando(valor=valor, acoes=acoes):
        return f
    if acoes <= 0:
        return indisponivel("quantidade de ações não positiva")
    return ok(valor / acoes)


def p_ffo(valor_mercado: Numero, ffo_: Numero) -> Resultado:
    """Preço sobre FFO (o "P/L" dos REITs)."""
    if f := faltando(valor_mercado=valor_mercado, ffo=ffo_):
        return f
    if ffo_ <= 0:
        return indisponivel("FFO não positivo: múltiplo sem interpretação")
    return ok(valor_mercado / ffo_)


def payout_ffo(dividendos_pagos: Numero, ffo_: Numero) -> Resultado:
    """Dividendos pagos ÷ FFO (cobertura dos dividendos pela geração de caixa)."""
    if f := faltando(dividendos_pagos=dividendos_pagos, ffo=ffo_):
        return f
    if ffo_ <= 0:
        return indisponivel("FFO não positivo")
    return ok(abs(dividendos_pagos) / ffo_)
