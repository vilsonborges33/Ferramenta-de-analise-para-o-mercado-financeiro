"""Joel Greenblatt, *A Fórmula Mágica*.

- Earnings yield = EBIT ÷ EV.
- Retorno sobre capital = EBIT ÷ (capital de giro líquido + ativo fixo líquido).
- Ranking: posição em cada critério (1 = melhor) somadas; menor soma = melhor colocação.
- Exclusões configuráveis: financeiras, utilities (setor elétrico/saneamento), liquidez mínima.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field

from app.metodologias.tipos import Numero, Resultado, faltando, indisponivel, ok


def earnings_yield(ebit: Numero, ev: Numero) -> Resultado:
    """EBIT ÷ EV. Indisponível com EV ≤ 0 (caixa líquido maior que o valor de mercado)."""
    if f := faltando(ebit=ebit, ev=ev):
        return f
    if ev <= 0:
        return indisponivel("EV não positivo: earnings yield não interpretável")
    return ok(ebit / ev)


def capital_giro_liquido(ativo_circulante: Numero, caixa: Numero, passivo_circulante: Numero,
                         emprestimos_cp: Numero) -> Resultado:
    """(Ativo circulante − caixa e aplicações) − (passivo circulante − empréstimos de curto prazo).

    O caixa sai do numerador e a dívida financeira sai do passivo para medir só o capital de giro
    operacional, como no livro.
    """
    if f := faltando(ativo_circulante=ativo_circulante, passivo_circulante=passivo_circulante):
        return f
    return ok((ativo_circulante - (caixa or 0)) - (passivo_circulante - (emprestimos_cp or 0)))


def retorno_sobre_capital(ebit: Numero, capital_giro_liquido_: Numero, ativo_fixo_liquido: Numero) -> Resultado:
    """EBIT ÷ (max(capital de giro líquido, 0) + ativo fixo líquido).

    Capital de giro negativo é tratado como zero (não reduz o capital empregado).
    """
    if f := faltando(ebit=ebit, capital_giro_liquido=capital_giro_liquido_, ativo_fixo_liquido=ativo_fixo_liquido):
        return f
    capital = max(capital_giro_liquido_, 0) + ativo_fixo_liquido
    if capital <= 0:
        return indisponivel("capital empregado não positivo")
    return ok(ebit / capital, capital_empregado=capital)


@dataclass(frozen=True)
class Candidato:
    ticker: str
    earnings_yield: Numero
    retorno_capital: Numero
    tipo_plano_contas: str = "geral"
    setor: str | None = None
    liquidez_diaria: Numero = None


@dataclass(frozen=True)
class ParametrosGreenblatt:
    excluir_financeiras: bool = True
    excluir_utilities: bool = True
    liquidez_minima: float = 0.0
    setores_utilities: tuple[str, ...] = ("Energia Elétrica", "Saneamento", "Água")


@dataclass
class PosicaoRanking:
    ticker: str
    posicao: int
    soma: int
    posicao_ey: int
    posicao_roc: int


@dataclass
class ResultadoRanking:
    ranking: list[PosicaoRanking]
    excluidos: dict[str, str] = field(default_factory=dict)  # ticker → motivo


def ranking(candidatos: Sequence[Candidato], p: ParametrosGreenblatt = ParametrosGreenblatt()) -> ResultadoRanking:
    """Ordena por soma das posições em EY e ROC (empate: maior EY primeiro, depois ticker)."""
    validos: list[Candidato] = []
    excluidos: dict[str, str] = {}
    for c in candidatos:
        if p.excluir_financeiras and c.tipo_plano_contas != "geral":
            excluidos[c.ticker] = "financeira/seguradora"
        elif p.excluir_utilities and c.setor and any(s.lower() in c.setor.lower() for s in p.setores_utilities):
            excluidos[c.ticker] = "utility"
        elif p.liquidez_minima and (c.liquidez_diaria is None or c.liquidez_diaria < p.liquidez_minima):
            excluidos[c.ticker] = "liquidez abaixo do mínimo"
        elif c.earnings_yield is None or c.retorno_capital is None:
            excluidos[c.ticker] = "dados insuficientes (EY ou ROC indisponível)"
        else:
            validos.append(c)

    def posicoes(chave) -> dict[str, int]:
        ordenados = sorted(validos, key=lambda c: (-chave(c), c.ticker))
        return {c.ticker: i + 1 for i, c in enumerate(ordenados)}

    pos_ey = posicoes(lambda c: c.earnings_yield)
    pos_roc = posicoes(lambda c: c.retorno_capital)
    ordem = sorted(validos, key=lambda c: (pos_ey[c.ticker] + pos_roc[c.ticker], -c.earnings_yield, c.ticker))
    return ResultadoRanking(
        [PosicaoRanking(c.ticker, i + 1, pos_ey[c.ticker] + pos_roc[c.ticker], pos_ey[c.ticker], pos_roc[c.ticker])
         for i, c in enumerate(ordem)],
        excluidos,
    )
