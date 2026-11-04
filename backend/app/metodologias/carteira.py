"""Consolidação da carteira (Fase 6): posições, preço médio, resultado, rentabilidade e proventos.

Convenções (as mesmas da Receita Federal para o preço médio):
- Compra: preço médio = (custo anterior + quantidade × preço + taxas) ÷ nova quantidade.
- Venda: não muda o preço médio; resultado realizado = quantidade × (preço − preço médio) − taxas.
- Desdobramento/bonificação: aumenta a quantidade sem custo (o preço médio cai na mesma proporção);
  grupamento: reduz a quantidade (o preço médio sobe).
- Rentabilidade pelo método das cotas (time-weighted): retorno do dia = (V_t + proventos_t − aportes_t) ÷ V_{t−1} − 1,
  o que neutraliza o efeito de aportes e resgates — como fazem os fundos de investimento.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date

from app.metodologias.tipos import Numero, Resultado, faltando, indisponivel, ok

TIPOS = ("COMPRA", "VENDA", "DESDOBRAMENTO", "BONIFICACAO", "GRUPAMENTO")


@dataclass(frozen=True)
class Movimento:
    data: date
    ativo: str
    tipo: str  # um de TIPOS
    quantidade: float
    preco: float = 0.0
    taxas: float = 0.0


@dataclass
class Posicao:
    ativo: str
    quantidade: float = 0.0
    custo: float = 0.0  # custo total da posição aberta (quantidade × preço médio)
    resultado_realizado: float = 0.0
    total_investido: float = 0.0
    primeira_compra: date | None = None
    historico: list[tuple[date, float]] = field(default_factory=list)  # (data, quantidade após o movimento)

    @property
    def preco_medio(self) -> float | None:
        return self.custo / self.quantidade if self.quantidade > 0 else None


class ErroCarteira(ValueError):
    pass


def consolidar(movimentos: Iterable[Movimento]) -> dict[str, Posicao]:
    """Aplica os movimentos em ordem de data (compras antes de vendas no mesmo dia)."""
    ordem = {"COMPRA": 0, "BONIFICACAO": 1, "DESDOBRAMENTO": 1, "GRUPAMENTO": 1, "VENDA": 2}
    posicoes: dict[str, Posicao] = {}
    for m in sorted(movimentos, key=lambda m: (m.data, ordem.get(m.tipo, 9))):
        if m.tipo not in TIPOS:
            raise ErroCarteira(f"tipo de lançamento desconhecido: {m.tipo}")
        if m.quantidade <= 0:
            raise ErroCarteira(f"{m.ativo} em {m.data:%d/%m/%Y}: quantidade precisa ser positiva")
        p = posicoes.setdefault(m.ativo, Posicao(m.ativo))
        if m.tipo == "COMPRA":
            p.custo += m.quantidade * m.preco + m.taxas
            p.quantidade += m.quantidade
            p.total_investido += m.quantidade * m.preco + m.taxas
            p.primeira_compra = p.primeira_compra or m.data
        elif m.tipo == "VENDA":
            if m.quantidade > p.quantidade + 1e-9:
                raise ErroCarteira(f"venda de {m.quantidade:g} {m.ativo} em {m.data:%d/%m/%Y} acima da posição "
                                   f"({p.quantidade:g})")
            pm = p.preco_medio or 0.0
            p.resultado_realizado += m.quantidade * (m.preco - pm) - m.taxas
            p.custo -= m.quantidade * pm
            p.quantidade -= m.quantidade
            if p.quantidade <= 1e-9:
                p.quantidade, p.custo = 0.0, 0.0
        elif m.tipo in ("DESDOBRAMENTO", "BONIFICACAO"):
            p.quantidade += m.quantidade  # custo inalterado: o preço médio cai
        else:  # GRUPAMENTO: quantidade informada é a que sai
            p.quantidade = max(0.0, p.quantidade - m.quantidade)
        p.historico.append((m.data, p.quantidade))
    return posicoes


def quantidade_em(posicao: Posicao, dia: date) -> float:
    """Quantidade detida ao fim do dia (usada para proventos pela data-com e para o valor diário)."""
    q = 0.0
    for d, qtd in posicao.historico:
        if d > dia:
            break
        q = qtd
    return q


def proventos_recebidos(posicao: Posicao, proventos: Sequence[tuple[date, float]]) -> list[tuple[date, float]]:
    """(data, valor) de cada provento: quantidade detida na data-com × valor líquido por cota."""
    saida = []
    for data_com, valor in proventos:
        q = quantidade_em(posicao, data_com)
        if q > 0:
            saida.append((data_com, q * valor))
    return saida


def yield_on_cost(proventos_12m_por_cota: Numero, preco_medio: Numero) -> Resultado:
    """Yield on cost = proventos por cota dos últimos 12 meses ÷ preço médio pago."""
    if f := faltando(proventos_12m=proventos_12m_por_cota, preco_medio=preco_medio):
        return f
    if preco_medio <= 0:
        return indisponivel("preço médio não positivo")
    return ok(proventos_12m_por_cota / preco_medio)


def rentabilidade_cotas(valores: Sequence[float], aportes: Sequence[float], proventos: Sequence[float]) -> Resultado:
    """Retorno acumulado pelo método das cotas. Listas alinhadas por dia; `aportes` > 0 entrada, < 0 resgate.

    Dias com valor anterior zero (carteira vazia) não geram retorno. `detalhes["acumulado"]` traz a série.
    """
    if not (len(valores) == len(aportes) == len(proventos)):
        raise ErroCarteira("séries de tamanhos diferentes")
    if len(valores) < 2:
        return indisponivel("histórico curto: menos de 2 dias")
    cota, serie = 1.0, [0.0]
    for t in range(1, len(valores)):
        anterior = valores[t - 1]
        if anterior > 0:
            cota *= (valores[t] + proventos[t] - aportes[t]) / anterior
        serie.append(cota - 1)
    return ok(cota - 1, acumulado=serie)


def alocacao(valores: dict[str, float]) -> dict[str, float]:
    total = sum(v for v in valores.values() if v > 0)
    return {k: v / total for k, v in valores.items() if v > 0} if total else {}
