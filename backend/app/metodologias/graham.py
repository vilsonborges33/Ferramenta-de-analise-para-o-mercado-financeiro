"""Benjamin Graham, *O Investidor Inteligente*.

- Valor intrínseco: √(fator × LPA × VPA), fator padrão 22,5 (= P/L 15 × P/VP 1,5).
- Fórmula revisada: V = LPA × (8,5 + 2g) × 4,4 ÷ Y, com g e Y em pontos percentuais.
  No Brasil, Y = Selic meta (DECISOES.md D-020).
- Margem de segurança e checklist do investidor defensivo com pontuação.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass

from app.metodologias.tipos import Numero, Resultado, faltando, indisponivel, ok

FATOR_GRAHAM = 22.5
PL_BASE_SEM_CRESCIMENTO = 8.5
RENDIMENTO_AAA_ORIGINAL = 4.4


def valor_intrinseco(lpa: Numero, vpa: Numero, fator: float = FATOR_GRAHAM) -> Resultado:
    """V = √(fator × LPA × VPA). Indisponível com LPA ou VPA ≤ 0 (raiz de número negativo)."""
    if f := faltando(lpa=lpa, vpa=vpa):
        return f
    if lpa <= 0:
        return indisponivel("LPA não positivo: fórmula de Graham não se aplica a empresas com prejuízo")
    if vpa <= 0:
        return indisponivel("VPA não positivo: patrimônio líquido negativo")
    return ok(math.sqrt(fator * lpa * vpa))


def valor_revisado(lpa: Numero, crescimento: Numero, taxa_y: Numero) -> Resultado:
    """V = LPA × (8,5 + 2g) × 4,4 ÷ Y.

    `crescimento` e `taxa_y` em fração (0,10 = 10%); a fórmula usa pontos percentuais, então
    g = 100 × crescimento e Y = 100 × taxa_y.
    """
    if f := faltando(lpa=lpa, crescimento=crescimento, taxa_y=taxa_y):
        return f
    if lpa <= 0:
        return indisponivel("LPA não positivo: fórmula revisada não se aplica")
    if taxa_y <= 0:
        return indisponivel("taxa Y não positiva")
    multiplicador = PL_BASE_SEM_CRESCIMENTO + 2 * crescimento * 100
    if multiplicador <= 0:
        return indisponivel("crescimento negativo demais: múltiplo implícito não positivo")
    return ok(lpa * multiplicador * RENDIMENTO_AAA_ORIGINAL / (taxa_y * 100), multiplo_implicito=multiplicador)


def margem_seguranca(valor_justo: Numero, preco: Numero) -> Resultado:
    """Margem de segurança = (valor justo − preço) ÷ valor justo. Negativa = preço acima do valor."""
    if f := faltando(valor_justo=valor_justo, preco=preco):
        return f
    if valor_justo <= 0:
        return indisponivel("valor justo não positivo")
    return ok((valor_justo - preco) / valor_justo)


# ------------------------------------------------------- investidor defensivo


@dataclass(frozen=True)
class ParametrosDefensivo:
    receita_minima: float = 2_000_000_000.0  # porte: receita anual mínima (R$)
    liquidez_corrente_minima: float = 2.0
    anos_lucro_positivo: int = 10
    anos_dividendos: int = 20
    crescimento_lpa_minimo: float = 0.33  # em 10 anos, médias de 3 anos nas pontas
    pl_maximo: float = 15.0  # sobre o LPA médio de 3 anos
    pvp_maximo: float = 1.5
    produto_pl_pvp_maximo: float = 22.5


@dataclass(frozen=True)
class DadosDefensivo:
    receita_anual: Numero
    ativo_circulante: Numero
    passivo_circulante: Numero
    divida_longo_prazo: Numero
    lucros_anuais: Sequence[Numero]  # do mais antigo para o mais recente
    anos_com_dividendos: int | None  # anos consecutivos recentes com pagamento
    lpa_anuais: Sequence[Numero]  # do mais antigo para o mais recente
    preco: Numero
    vpa: Numero


@dataclass(frozen=True)
class Criterio:
    nome: str
    atendido: bool | None  # None = dado indisponível
    detalhe: str


def checklist_defensivo(d: DadosDefensivo, p: ParametrosDefensivo = ParametrosDefensivo()) -> Resultado:
    """Sete critérios do investidor defensivo; valor = nº de critérios atendidos (0 a 7).

    Critério indisponível não conta como atendido; a lista completa vai em `detalhes`.
    """
    criterios: list[Criterio] = []

    def add(nome: str, atendido: bool | None, detalhe: str) -> None:
        criterios.append(Criterio(nome, atendido, detalhe))

    # 1. Porte
    if d.receita_anual is None:
        add("Porte adequado", None, "receita indisponível")
    else:
        add("Porte adequado", d.receita_anual >= p.receita_minima, f"receita ≥ {p.receita_minima:,.0f}")

    # 2. Condição financeira: liquidez corrente e dívida de LP ≤ capital de giro
    if None in (d.ativo_circulante, d.passivo_circulante) or not d.passivo_circulante:
        add("Condição financeira sólida", None, "circulante indisponível")
    else:
        lc = d.ativo_circulante / d.passivo_circulante
        capital_giro = d.ativo_circulante - d.passivo_circulante
        divida_ok = d.divida_longo_prazo is not None and d.divida_longo_prazo <= capital_giro
        add("Condição financeira sólida", lc >= p.liquidez_corrente_minima and divida_ok,
            f"liquidez corrente {lc:.2f} (mín. {p.liquidez_corrente_minima}); dívida LP ≤ capital de giro")

    # 3. Estabilidade dos lucros
    lucros = list(d.lucros_anuais)[-p.anos_lucro_positivo:]
    if len(lucros) < p.anos_lucro_positivo or any(x is None for x in lucros):
        add("Lucros positivos", None, f"menos de {p.anos_lucro_positivo} anos de lucro disponíveis")
    else:
        add("Lucros positivos", all(x > 0 for x in lucros), f"lucro positivo nos últimos {p.anos_lucro_positivo} anos")

    # 4. Histórico de dividendos
    if d.anos_com_dividendos is None:
        add("Dividendos ininterruptos", None, "histórico de proventos indisponível")
    else:
        add("Dividendos ininterruptos", d.anos_com_dividendos >= p.anos_dividendos,
            f"{d.anos_com_dividendos} anos seguidos (mín. {p.anos_dividendos})")

    # 5. Crescimento do LPA: média dos 3 últimos vs. média dos 3 primeiros de 10 anos
    lpas = list(d.lpa_anuais)[-10:]
    if len(lpas) < 10 or any(x is None for x in lpas):
        add("Crescimento do LPA", None, "menos de 10 anos de LPA")
    else:
        inicio, fim = sum(lpas[:3]) / 3, sum(lpas[-3:]) / 3
        if inicio <= 0:
            add("Crescimento do LPA", fim > 0 and fim > inicio, "LPA médio inicial não positivo")
        else:
            add("Crescimento do LPA", fim / inicio - 1 >= p.crescimento_lpa_minimo,
                f"crescimento {fim / inicio - 1:.0%} (mín. {p.crescimento_lpa_minimo:.0%})")

    # 6 e 7. Preço moderado: P/L sobre LPA médio de 3 anos; P/VP (ou produto ≤ 22,5)
    lpa_medio = (sum(lpas[-3:]) / 3) if len(lpas) >= 3 and all(x is not None for x in lpas[-3:]) else None
    if d.preco is None or lpa_medio is None:
        add("P/L moderado", None, "preço ou LPA médio indisponível")
        pl = None
    elif lpa_medio <= 0:
        add("P/L moderado", False, "LPA médio de 3 anos não positivo")
        pl = None
    else:
        pl = d.preco / lpa_medio
        add("P/L moderado", pl <= p.pl_maximo, f"P/L (LPA médio 3 anos) {pl:.1f} (máx. {p.pl_maximo})")
    if d.preco is None or d.vpa is None or d.vpa <= 0:
        add("P/VP moderado", None, "preço ou VPA indisponível/não positivo")
    else:
        pvp = d.preco / d.vpa
        atende = pvp <= p.pvp_maximo or (pl is not None and pl * pvp <= p.produto_pl_pvp_maximo)
        add("P/VP moderado", atende, f"P/VP {pvp:.2f} (máx. {p.pvp_maximo} ou P/L × P/VP ≤ {p.produto_pl_pvp_maximo})")

    pontos = sum(1 for c in criterios if c.atendido)
    return ok(pontos, criterios=[c.__dict__ for c in criterios],
              indisponiveis=sum(1 for c in criterios if c.atendido is None))
