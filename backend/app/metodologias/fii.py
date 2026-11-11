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


# ---------------------------------------------------------------- composição, dívida e risco (Fase 5)

# Colunas do arquivo "ativo_passivo" do informe mensal da CVM → grupo da composição do ativo.
# Só as linhas "folha" entram (os subtotais Total_* e Direitos_Bens_Imoveis ficam de fora para não somar duas vezes).
GRUPOS_ATIVO: dict[str, tuple[str, ...]] = {
    "Imóveis": ("terrenos", "imoveis_renda_acabados", "imoveis_renda_construcao", "imoveis_venda_acabados",
                "imoveis_venda_construcao", "outros_direitos_reais"),
    "CRI e CRA": ("cri", "cri_cra"),
    "LCI, LCA, LH e LIG": ("lci", "lci_lca", "lh", "lig"),
    "Cotas de FII": ("fii",),
    "Ações e sociedades": ("acoes", "acoes_sociedades_atividades_fii", "cotas_sociedades_atividades_fii"),
    "Caixa e renda fixa": ("disponibilidades", "titulos_publicos", "titulos_privados", "fundos_renda_fixa"),
    "Outros valores mobiliários": ("debentures", "bonus_subscricao", "certificados_deposito_valores_mobiliarios",
                                   "cedulas_debentures", "fundo_acoes", "fip", "fidc", "fdic", "outras_cotas_fi",
                                   "notas_promissorias", "notas_comerciais", "cepac", "outros_valores_mobiliarios"),
    "Valores a receber": ("contas_receber_aluguel", "contas_receber_venda_imoveis", "outros_valores_receber"),
}
OBRIGACOES: dict[str, tuple[str, ...]] = {
    "Aquisição de imóveis": ("obrigacoes_aquisicao_imoveis",),
    "Securitização de recebíveis": ("obrigacoes_securitizacao_recebiveis",),
    "Adiantamentos (venda e aluguéis)": ("adiantamento_venda_imoveis", "adiantamento_alugueis"),
    "Rendimentos a distribuir": ("rendimentos_distribuir",),
    "Taxas a pagar": ("taxa_administracao_pagar", "taxa_performance_pagar"),
    "Derivativos, provisões e outros": ("instrumentos_financeiros_derivativos", "provisoes_contingencias",
                                       "outros_valores_pagar"),
}


def _valores(linha: dict, grupos: dict[str, tuple[str, ...]]) -> dict[str, float]:
    normal = {str(k).strip().lower(): v for k, v in linha.items()}
    saida = {}
    for grupo, colunas in grupos.items():
        total = 0.0
        for c in colunas:
            v = normal.get(c)
            try:
                total += float(str(v).replace(",", ".")) if v not in (None, "") else 0.0
            except ValueError:
                continue
        saida[grupo] = total
    return saida


def composicao_ativo(linha_ativo_passivo: dict | None, ativo_total: Numero = None) -> Resultado:
    """Composição do ativo em grupos (valor e % do total classificado), a partir do informe mensal."""
    if not linha_ativo_passivo:
        return indisponivel("dado indisponível: informe mensal sem detalhamento do ativo")
    valores = _valores(linha_ativo_passivo, GRUPOS_ATIVO)
    soma = sum(v for v in valores.values() if v > 0)
    if soma <= 0:
        return indisponivel("informe mensal sem valores de ativo classificáveis")
    grupos = [{"grupo": g, "valor": v, "percentual": v / soma} for g, v in valores.items() if v > 0]
    grupos.sort(key=lambda g: -g["valor"])
    cobertura = soma / ativo_total if ativo_total else None
    return ok(soma, grupos=grupos, cobertura_do_ativo_total=cobertura)


def tipo_do_fundo(grupos: Sequence[dict], limite: float = 0.6) -> str:
    """Classificação pela composição: Tijolo, Papel, Fundo de fundos ou Híbrido (≥ 60% num tipo)."""
    pct = {g["grupo"]: g["percentual"] for g in grupos}
    if pct.get("Imóveis", 0) >= limite:
        return "Tijolo"
    if pct.get("CRI e CRA", 0) + pct.get("LCI, LCA, LH e LIG", 0) >= limite:
        return "Papel"
    if pct.get("Cotas de FII", 0) >= limite:
        return "Fundo de fundos"
    return "Híbrido"


def obrigacoes(linha_ativo_passivo: dict | None) -> list[dict]:
    if not linha_ativo_passivo:
        return []
    return [{"grupo": g, "valor": v} for g, v in _valores(linha_ativo_passivo, OBRIGACOES).items() if v]


PASSIVO_NAO_ONEROSO = ("Rendimentos a distribuir", "Taxas a pagar")


def passivo_nao_oneroso(linha_ativo_passivo: dict | None) -> float:
    """Rendimentos já declarados e taxas a pagar: saem no mês seguinte e não são dívida do fundo."""
    if not linha_ativo_passivo:
        return 0.0
    valores = _valores(linha_ativo_passivo, OBRIGACOES)
    return sum(valores.get(g, 0.0) for g in PASSIVO_NAO_ONEROSO)


def alavancagem(total_passivo: Numero, ativo_total: Numero, nao_oneroso: Numero = 0) -> Resultado:
    """Alavancagem bruta = (passivo total − rendimentos a distribuir − taxas a pagar) ÷ ativo total.

    Fica a dívida de fato: obrigações por aquisição de imóveis, CRI emitidos, adiantamentos e provisões.
    """
    if f := faltando(total_passivo=total_passivo, ativo_total=ativo_total):
        return f
    if ativo_total <= 0:
        return indisponivel("ativo total não positivo")
    return ok(max(total_passivo - (nao_oneroso or 0), 0.0) / ativo_total)


def vacancia_ponderada(imoveis: Sequence[tuple[Numero, Numero]]) -> Resultado:
    """Vacância física média ponderada pela área: Σ(área × vacância) ÷ Σ área. Sem área, média simples."""
    validos = [(a, v) for a, v in imoveis if v is not None]
    if not validos:
        return indisponivel("dado indisponível: informe trimestral sem vacância dos imóveis")
    com_area = [(float(a), float(v)) for a, v in validos if a is not None and float(a) > 0]
    if com_area:
        area = sum(a for a, _ in com_area)
        return ok(sum(a * v for a, v in com_area) / area, imoveis=len(com_area), ponderada=True)
    return ok(sum(float(v) for _, v in validos) / len(validos), imoveis=len(validos), ponderada=False)


def estatistica_retornos(retornos_mensais: Sequence[float]) -> Resultado:
    """Meses positivos e negativos, maior e menor retorno mensal."""
    r = [x for x in retornos_mensais if x is not None]
    if len(r) < 3:
        return indisponivel("histórico curto: menos de 3 meses de cotação")
    positivos = sum(1 for x in r if x > 0)
    negativos = sum(1 for x in r if x < 0)
    return ok(positivos / len(r), meses=len(r), positivos=positivos, negativos=negativos, maior=max(r), menor=min(r))
