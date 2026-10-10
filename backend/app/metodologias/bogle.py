"""John Bogle, *O Investidor de Bom Senso*.

- Impacto dos custos no retorno composto (taxa de administração de FII/ETF/fundo).
- Gestão ativa × índice: diferença de patrimônio final.
- Decomposição do retorno esperado: dividend yield + crescimento do lucro + variação do múltiplo.
"""

from app.metodologias.tipos import Numero, Resultado, faltando, indisponivel, ok


def valor_futuro(inicial: float, aporte_anual: float, retorno_anual: float, anos: int,
                 custo_anual: float = 0.0) -> float:
    """Patrimônio após `anos`, com aportes no fim de cada ano e retorno líquido = (1+r)(1−c) − 1."""
    liquido = (1 + retorno_anual) * (1 - custo_anual) - 1
    patrimonio = inicial
    for _ in range(anos):
        patrimonio = patrimonio * (1 + liquido) + aporte_anual
    return patrimonio


def impacto_custos(inicial: Numero, aporte_anual: Numero, retorno_anual: Numero, anos: int,
                   custo_anual: Numero) -> Resultado:
    """Quanto do patrimônio final os custos consomem: 1 − VF(com custo) ÷ VF(sem custo)."""
    if f := faltando(inicial=inicial, aporte_anual=aporte_anual, retorno_anual=retorno_anual, custo_anual=custo_anual):
        return f
    if anos <= 0:
        return indisponivel("horizonte não positivo")
    if not 0 <= custo_anual < 1:
        return indisponivel("custo anual fora de [0, 100%)")
    sem = valor_futuro(inicial, aporte_anual, retorno_anual, anos)
    com = valor_futuro(inicial, aporte_anual, retorno_anual, anos, custo_anual)
    if sem <= 0:
        return indisponivel("patrimônio final sem custos não positivo")
    return ok(1 - com / sem, valor_sem_custos=sem, valor_com_custos=com, custo_total=sem - com)


def ativo_vs_indice(inicial: Numero, retorno_bruto: Numero, anos: int, custo_ativo: Numero,
                    custo_indice: Numero, alfa_bruto: Numero = 0.0) -> Resultado:
    """Diferença de patrimônio final (ativo − índice). Ativo rende o mercado + alfa bruto, menos seu custo."""
    if f := faltando(inicial=inicial, retorno_bruto=retorno_bruto, custo_ativo=custo_ativo,
                     custo_indice=custo_indice, alfa_bruto=alfa_bruto):
        return f
    ativo = valor_futuro(inicial, 0, retorno_bruto + alfa_bruto, anos, custo_ativo)
    indice = valor_futuro(inicial, 0, retorno_bruto, anos, custo_indice)
    return ok(ativo - indice, valor_ativo=ativo, valor_indice=indice)


def decomposicao_retorno(dividend_yield: Numero, crescimento_lucro: Numero, pl_inicial: Numero, pl_final: Numero,
                         anos: int) -> Resultado:
    """Retorno esperado ≈ DY + crescimento do lucro + [(P/L final ÷ P/L inicial)^(1/anos) − 1]."""
    if f := faltando(dividend_yield=dividend_yield, crescimento_lucro=crescimento_lucro, pl_inicial=pl_inicial,
                     pl_final=pl_final):
        return f
    if anos <= 0:
        return indisponivel("horizonte não positivo")
    if pl_inicial <= 0 or pl_final <= 0:
        return indisponivel("P/L não positivo: variação do múltiplo não definida")
    especulativo = (pl_final / pl_inicial) ** (1 / anos) - 1
    investimento = dividend_yield + crescimento_lucro
    return ok(investimento + especulativo, retorno_investimento=investimento, retorno_especulativo=especulativo)
