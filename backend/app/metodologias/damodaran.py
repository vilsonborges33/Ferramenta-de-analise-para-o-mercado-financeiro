"""Aswath Damodaran, *Valuation*.

- Custo do capital próprio: Ke = rf + β × ERP + λ × CRP (prêmio de risco país do Brasil).
- Beta desalavancado/realavancado (Hamada): βL = βU × (1 + (1 − t) × D/E).
- Conversão de taxa entre moedas pelo diferencial de inflação.
- Modelo de desconto de dividendos: Gordon e dois estágios.
- Valuation relativa: preço implícito pela mediana do múltiplo do setor.
- Narrativa → números: toda premissa precisa de justificativa escrita.

Parâmetros de mercado (ERP, CRP, betas setoriais) vêm dos datasets públicos do Damodaran, sempre
com data de referência (docs/FONTES_DE_DADOS.md).
"""

from collections.abc import Mapping, Sequence
from statistics import median

from app.metodologias.tipos import Numero, Resultado, faltando, indisponivel, ok


def custo_capital_proprio(taxa_livre_risco: Numero, beta: Numero, premio_risco_mercado: Numero,
                          premio_risco_pais: Numero = 0.0, lambda_pais: float = 1.0) -> Resultado:
    """Ke = rf + β × ERP + λ × CRP. λ = exposição ao risco país (padrão 1)."""
    if f := faltando(taxa_livre_risco=taxa_livre_risco, beta=beta, premio_risco_mercado=premio_risco_mercado,
                     premio_risco_pais=premio_risco_pais):
        return f
    return ok(taxa_livre_risco + beta * premio_risco_mercado + lambda_pais * premio_risco_pais)


def beta_desalavancado(beta_alavancado: Numero, divida_sobre_equity: Numero, aliquota: float) -> Resultado:
    """βU = βL ÷ (1 + (1 − t) × D/E)."""
    if f := faltando(beta_alavancado=beta_alavancado, divida_sobre_equity=divida_sobre_equity):
        return f
    denominador = 1 + (1 - aliquota) * divida_sobre_equity
    if denominador <= 0:
        return indisponivel("D/E inválido")
    return ok(beta_alavancado / denominador)


def beta_realavancado(beta_desalavancado_: Numero, divida_sobre_equity: Numero, aliquota: float) -> Resultado:
    """βL = βU × (1 + (1 − t) × D/E)."""
    if f := faltando(beta_desalavancado=beta_desalavancado_, divida_sobre_equity=divida_sobre_equity):
        return f
    if divida_sobre_equity < 0:
        return indisponivel("D/E negativo")
    return ok(beta_desalavancado_ * (1 + (1 - aliquota) * divida_sobre_equity))


def converter_taxa(taxa_origem: Numero, inflacao_origem: Numero, inflacao_destino: Numero) -> Resultado:
    """Taxa em outra moeda: (1 + r) × (1 + π_destino) ÷ (1 + π_origem) − 1 (ex.: USD → BRL)."""
    if f := faltando(taxa_origem=taxa_origem, inflacao_origem=inflacao_origem, inflacao_destino=inflacao_destino):
        return f
    return ok((1 + taxa_origem) * (1 + inflacao_destino) / (1 + inflacao_origem) - 1)


def gordon(dividendo_atual: Numero, custo_capital: Numero, crescimento: Numero) -> Resultado:
    """P = D0 × (1 + g) ÷ (Ke − g). Exige Ke > g e dividendo positivo."""
    if f := faltando(dividendo_atual=dividendo_atual, custo_capital=custo_capital, crescimento=crescimento):
        return f
    if dividendo_atual <= 0:
        return indisponivel("sem dividendos: modelo de Gordon não se aplica")
    if custo_capital <= crescimento:
        return indisponivel("custo de capital ≤ crescimento: modelo de Gordon não converge")
    return ok(dividendo_atual * (1 + crescimento) / (custo_capital - crescimento))


def ddm_dois_estagios(dividendo_atual: Numero, custo_capital: Numero, crescimento_alto: Numero, anos_alto: int,
                      crescimento_estavel: Numero, custo_capital_estavel: Numero = None) -> Resultado:
    """Dividendos crescem a g1 por n anos e depois a g2 para sempre.

    P = Σ_{t=1..n} D0(1+g1)^t ÷ (1+Ke)^t + [D_n(1+g2) ÷ (Ke2 − g2)] ÷ (1+Ke)^n.
    `custo_capital_estavel` (Ke2) é opcional; por padrão igual ao Ke do primeiro estágio.
    """
    if f := faltando(dividendo_atual=dividendo_atual, custo_capital=custo_capital, crescimento_alto=crescimento_alto,
                     crescimento_estavel=crescimento_estavel):
        return f
    ke2 = custo_capital if custo_capital_estavel is None else custo_capital_estavel
    if dividendo_atual <= 0:
        return indisponivel("sem dividendos: modelo de desconto de dividendos não se aplica")
    if anos_alto < 1:
        return indisponivel("primeiro estágio precisa de ao menos 1 ano")
    if ke2 <= crescimento_estavel:
        return indisponivel("custo de capital do estágio estável ≤ crescimento perpétuo")
    vp, dividendo = 0.0, dividendo_atual
    for t in range(1, anos_alto + 1):
        dividendo *= 1 + crescimento_alto
        vp += dividendo / (1 + custo_capital) ** t
    terminal = dividendo * (1 + crescimento_estavel) / (ke2 - crescimento_estavel)
    vp_terminal = terminal / (1 + custo_capital) ** anos_alto
    return ok(vp + vp_terminal, vp_primeiro_estagio=vp, vp_terminal=vp_terminal)


def preco_por_multiplo_setor(multiplos_pares: Sequence[Numero], metrica_por_acao: Numero,
                             minimo_pares: int = 3) -> Resultado:
    """Preço implícito = mediana do múltiplo dos pares do setor × métrica por ação da empresa.

    Múltiplos ≤ 0 dos pares são descartados (sem interpretação). Para EV/EBITDA, passe a métrica já
    convertida (EBITDA por ação) e ajuste a dívida líquida por ação fora desta função.
    """
    validos = [m for m in multiplos_pares if m is not None and m > 0]
    if len(validos) < minimo_pares:
        return indisponivel(f"menos de {minimo_pares} pares com múltiplo positivo no setor")
    if metrica_por_acao is None:
        return indisponivel("dado indisponível: métrica da empresa")
    if metrica_por_acao <= 0:
        return indisponivel("métrica da empresa não positiva: múltiplo não se aplica")
    m = median(validos)
    return ok(m * metrica_por_acao, mediana_setor=m, pares=len(validos))


def premissas_sem_justificativa(premissas: Mapping[str, object], justificativas: Mapping[str, str]) -> list[str]:
    """Narrativa → números: devolve as premissas numéricas que não têm texto justificando o valor."""
    return [chave for chave in premissas if not (justificativas.get(chave) or "").strip()]
