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


def taxa_liquida(taxa_bruta: Numero, aliquota_ir: float = 0.15) -> Resultado:
    """Taxa do Tesouro líquida de IR (padrão 15%, prazo > 2 anos), para comparar com rendimentos
    de FII, isentos para a pessoa física."""
    if f := faltando(taxa_bruta=taxa_bruta):
        return f
    return ok(taxa_bruta * (1 - aliquota_ir))


def gordon_ajustado(dividendo_12m: Numero, taxa_tesouro: Numero, premio: Numero, crescimento: Numero,
                    aliquota_ir: float = 0.15, usar_taxa_liquida: bool = True) -> Resultado:
    """Preço teto do FII = D12m × (1 + g) ÷ (k − g), com k = taxa do Tesouro (líquida ou bruta) + prêmio.

    Damodaran (modelo de Gordon), adaptado: taxa exigida a partir do título público de referência.
    """
    if f := faltando(dividendo_12m=dividendo_12m, taxa_tesouro=taxa_tesouro, premio=premio, crescimento=crescimento):
        return f
    if dividendo_12m <= 0:
        return indisponivel("sem rendimentos nos últimos 12 meses")
    base = taxa_tesouro * (1 - aliquota_ir) if usar_taxa_liquida else taxa_tesouro
    k = base + premio
    if k <= crescimento:
        return indisponivel("taxa exigida ≤ crescimento: modelo não converge")
    return ok(dividendo_12m * (1 + crescimento) / (k - crescimento), taxa_exigida=k)
