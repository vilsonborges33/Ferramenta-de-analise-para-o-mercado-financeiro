"""Fluxo de caixa descontado — *Valuation: Guia Fundamental e Modelagem em Excel* (McKinsey/Koller et al.)
e Damodaran, *Valuation*.

Convenções: taxas em fração; fluxos no fim de cada ano; ano 1 = primeiro ano projetado.

- Projeção: receita cresce a taxas anuais; EBIT = margem × receita; D&A e capex em % da receita;
  variação do capital de giro = % × variação da receita.
- FCFF = EBIT × (1 − t) + D&A − capex − ΔCG.
- FCFE = FCFF − juros × (1 − t) + nova dívida líquida.
- WACC = E/(D+E) × Ke + D/(D+E) × Kd × (1 − t).
- Valor terminal (Gordon) = FC_{n+1} ÷ (r − g), exige r > g.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from app.metodologias.tipos import Numero, Resultado, faltando, indisponivel, ok


@dataclass(frozen=True)
class PremissasProjecao:
    receita_base: float  # receita do último ano realizado
    crescimento_receita: Sequence[float]  # uma taxa por ano projetado
    margem_ebit: float | Sequence[float]
    aliquota: float = 0.34
    da_pct_receita: float = 0.0
    capex_pct_receita: float = 0.0
    capital_giro_pct_variacao_receita: float = 0.0


@dataclass(frozen=True)
class AnoProjetado:
    ano: int
    receita: float
    ebit: float
    nopat: float
    depreciacao: float
    capex: float
    variacao_capital_giro: float
    fcff: float


def _por_ano(valor: float | Sequence[float], n: int) -> list[float]:
    if isinstance(valor, int | float):
        return [float(valor)] * n
    lista = list(valor)
    if len(lista) != n:
        raise ValueError("série de premissas com tamanho diferente do horizonte")
    return lista


def projetar(p: PremissasProjecao) -> list[AnoProjetado]:
    n = len(p.crescimento_receita)
    margens = _por_ano(p.margem_ebit, n)
    anos = []
    receita_anterior = p.receita_base
    for i, g in enumerate(p.crescimento_receita):
        receita = receita_anterior * (1 + g)
        ebit = receita * margens[i]
        nopat = ebit * (1 - p.aliquota)
        da = receita * p.da_pct_receita
        capex = receita * p.capex_pct_receita
        dcg = (receita - receita_anterior) * p.capital_giro_pct_variacao_receita
        anos.append(AnoProjetado(i + 1, receita, ebit, nopat, da, capex, dcg, nopat + da - capex - dcg))
        receita_anterior = receita
    return anos


def fcff(ebit: Numero, aliquota: float, depreciacao: Numero, capex: Numero, variacao_capital_giro: Numero) -> Resultado:
    """FCFF = EBIT × (1 − t) + D&A − capex − ΔCG."""
    if f := faltando(ebit=ebit, depreciacao=depreciacao, capex=capex, variacao_capital_giro=variacao_capital_giro):
        return f
    return ok(ebit * (1 - aliquota) + depreciacao - capex - variacao_capital_giro)


def fcfe(fcff_: Numero, juros: Numero, aliquota: float, nova_divida_liquida: Numero) -> Resultado:
    """FCFE = FCFF − juros × (1 − t) + nova dívida líquida (captações − amortizações)."""
    if f := faltando(fcff=fcff_, juros=juros, nova_divida_liquida=nova_divida_liquida):
        return f
    return ok(fcff_ - juros * (1 - aliquota) + nova_divida_liquida)


def wacc(valor_equity: Numero, valor_divida: Numero, custo_equity: Numero, custo_divida: Numero,
         aliquota: float) -> Resultado:
    """WACC = E/(D+E) × Ke + D/(D+E) × Kd × (1 − t), com pesos a valor de mercado."""
    if f := faltando(valor_equity=valor_equity, valor_divida=valor_divida, custo_equity=custo_equity,
                     custo_divida=custo_divida):
        return f
    if valor_equity < 0 or valor_divida < 0 or valor_equity + valor_divida == 0:
        return indisponivel("pesos de capital inválidos (valores negativos ou soma zero)")
    total = valor_equity + valor_divida
    peso_e, peso_d = valor_equity / total, valor_divida / total
    return ok(peso_e * custo_equity + peso_d * custo_divida * (1 - aliquota), peso_equity=peso_e, peso_divida=peso_d)


def valor_terminal(fluxo_ultimo_ano: Numero, taxa: Numero, crescimento_perpetuo: Numero) -> Resultado:
    """Gordon: FC_n × (1 + g) ÷ (r − g). Indisponível se r ≤ g."""
    if f := faltando(fluxo_ultimo_ano=fluxo_ultimo_ano, taxa=taxa, crescimento_perpetuo=crescimento_perpetuo):
        return f
    if taxa <= crescimento_perpetuo:
        return indisponivel("taxa de desconto ≤ crescimento perpétuo: valor terminal infinito ou negativo")
    return ok(fluxo_ultimo_ano * (1 + crescimento_perpetuo) / (taxa - crescimento_perpetuo))


def valor_presente(fluxos: Sequence[float], taxa: float) -> float:
    return sum(fc / (1 + taxa) ** (i + 1) for i, fc in enumerate(fluxos))


@dataclass(frozen=True)
class ResultadoDCF:
    valor_operacional: float
    vp_fluxos: float
    vp_terminal: float
    valor_terminal: float
    valor_equity: float
    valor_por_acao: float | None
    peso_terminal: float


def avaliar(fluxos: Sequence[float], taxa: Numero, crescimento_perpetuo: Numero, divida_liquida: Numero = 0.0,
            acoes: Numero = None) -> Resultado:
    """Valor = VP dos fluxos + VP do valor terminal; equity = valor − dívida líquida.

    Para FCFE, passe `divida_liquida=0` e a taxa = custo do capital próprio.
    """
    if not fluxos:
        return indisponivel("nenhum fluxo projetado")
    if f := faltando(taxa=taxa, crescimento_perpetuo=crescimento_perpetuo, divida_liquida=divida_liquida):
        return f
    if taxa <= -1:
        return indisponivel("taxa de desconto inválida")
    vt = valor_terminal(fluxos[-1], taxa, crescimento_perpetuo)
    if not vt.disponivel:
        return vt
    vp_fluxos = valor_presente(fluxos, taxa)
    vp_terminal = vt.valor / (1 + taxa) ** len(fluxos)
    operacional = vp_fluxos + vp_terminal
    equity = operacional - divida_liquida
    por_acao = equity / acoes if acoes and acoes > 0 else None
    r = ResultadoDCF(operacional, vp_fluxos, vp_terminal, vt.valor, equity, por_acao,
                     vp_terminal / operacional if operacional else 0.0)
    return ok(por_acao if por_acao is not None else equity, **r.__dict__)


def tabela_sensibilidade(fluxos: Sequence[float], taxas: Sequence[float], crescimentos: Sequence[float],
                         divida_liquida: float = 0.0, acoes: Numero = None) -> list[list[float | None]]:
    """Matriz [taxa][crescimento] do valor por ação (ou do equity); None onde r ≤ g."""
    return [[avaliar(fluxos, r, g, divida_liquida, acoes).valor for g in crescimentos] for r in taxas]
