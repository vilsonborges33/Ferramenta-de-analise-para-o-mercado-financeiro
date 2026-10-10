"""Peter Lynch, *Batendo o Mercado* (One Up on Wall Street).

- PEG = P/L ÷ crescimento do lucro (em pontos percentuais).
- Índice de Lynch = (crescimento + dividend yield) ÷ P/L (crescimento e DY em p.p.); ≥ 2 atraente,
  ≤ 1 pouco atraente, segundo a regra prática do autor.
- Preço justo: P/L justo = crescimento em p.p. (PEG = 1), sem teto (DECISOES.md D-019); aviso de
  crescimento atípico acima de 25% a.a. ou sobre lucro-base muito baixo/negativo.
- Classificação nas seis categorias com regras explícitas (ver `classificar`).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from statistics import mean, pstdev

from app.metodologias.tipos import Numero, Resultado, faltando, indisponivel, ok

LIMITE_CRESCIMENTO_ATIPICO = 0.25
AVISO_ATIPICO = "crescimento atípico: verifique a origem (efeito de base, evento não recorrente)"


def peg(p_l: Numero, crescimento: Numero) -> Resultado:
    """PEG = P/L ÷ (crescimento × 100). Indisponível com P/L ≤ 0 ou crescimento ≤ 0."""
    if f := faltando(p_l=p_l, crescimento=crescimento):
        return f
    if p_l <= 0:
        return indisponivel("P/L não positivo: PEG não se aplica")
    if crescimento <= 0:
        return indisponivel("crescimento não positivo: PEG não se aplica")
    return ok(p_l / (crescimento * 100))


def indice_lynch(crescimento: Numero, dividend_yield: Numero, p_l: Numero) -> Resultado:
    """(crescimento + DY) ÷ P/L, com crescimento e DY em pontos percentuais."""
    if f := faltando(crescimento=crescimento, dividend_yield=dividend_yield, p_l=p_l):
        return f
    if p_l <= 0:
        return indisponivel("P/L não positivo: índice de Lynch não se aplica")
    return ok((crescimento + dividend_yield) * 100 / p_l)


def crescimento_atipico(crescimento: Numero, lucro_base: Numero, lucro_atual: Numero,
                        limite: float = LIMITE_CRESCIMENTO_ATIPICO) -> str | None:
    """Devolve o texto do aviso quando o crescimento parece atípico; senão None.

    Lucro-base "muito baixo": menos de 20% do lucro atual (efeito de base).
    """
    if crescimento is not None and crescimento > limite:
        return AVISO_ATIPICO
    if lucro_base is not None and lucro_atual is not None:
        if lucro_base <= 0 or (lucro_atual > 0 and lucro_base < 0.2 * lucro_atual):
            return AVISO_ATIPICO
    return None


def preco_justo(lpa: Numero, crescimento: Numero, lucro_base: Numero = None, lucro_atual: Numero = None,
                fator: float = 1.0, limite_atipico: float = LIMITE_CRESCIMENTO_ATIPICO) -> Resultado:
    """Preço justo = LPA × P/L justo, com P/L justo = fator × crescimento em p.p. (padrão fator 1)."""
    if f := faltando(lpa=lpa, crescimento=crescimento):
        return f
    if lpa <= 0:
        return indisponivel("LPA não positivo")
    if crescimento <= 0:
        return indisponivel("crescimento não positivo: P/L justo seria ≤ 0")
    pl_justo = fator * crescimento * 100
    detalhes: dict = {"pl_justo": pl_justo}
    if aviso := crescimento_atipico(crescimento, lucro_base, lucro_atual, limite_atipico):
        detalhes["aviso"] = aviso
    return ok(lpa * pl_justo, **detalhes)


# -------------------------------------------------------------- categorias

CATEGORIAS = {
    "recuperacao": "Recuperação (turnaround)",
    "ciclica": "Cíclica",
    "ativos_ocultos": "Ativos ocultos",
    "crescimento_rapido": "Crescimento rápido",
    "robusta": "Robusta (stalwart)",
    "crescimento_lento": "Crescimento lento",
}

SETORES_CICLICOS = ("Siderurgia", "Metalurgia", "Mineração", "Petróleo", "Papel", "Celulose", "Química",
                    "Construção", "Automóveis", "Veículos", "Aviação", "Transporte Aéreo", "Agricultura")


@dataclass(frozen=True)
class ParametrosCategorias:
    crescimento_rapido: float = 0.20
    crescimento_robusta: float = 0.10
    cv_lucro_ciclica: float = 0.5  # coeficiente de variação dos lucros anuais
    pvp_ativos_ocultos: float = 1.0
    setores_ciclicos: tuple[str, ...] = SETORES_CICLICOS


def classificar(crescimento: Numero, lucros_anuais: Sequence[Numero], p_vp: Numero, setor: str | None,
                p: ParametrosCategorias = ParametrosCategorias()) -> Resultado:
    """Classifica a empresa numa das seis categorias. Regras na ordem de precedência:

    1. Recuperação: último lucro anual ≤ 0, ou lucro negativo em algum dos 3 anos anteriores.
    2. Cíclica: setor na lista de setores cíclicos, ou CV dos lucros anuais > 0,5.
    3. Ativos ocultos: P/VP < 1,0.
    4. Crescimento rápido: crescimento do lucro ≥ 20% a.a.
    5. Robusta: crescimento entre 10% e 20% a.a.
    6. Crescimento lento: crescimento < 10% a.a.

    `valor` = posição da categoria (1–6); `detalhes` traz o código, o nome e a regra aplicada.
    """
    lucros = [x for x in lucros_anuais if x is not None]

    def resultado(codigo: str, regra: str) -> Resultado:
        return ok(list(CATEGORIAS).index(codigo) + 1, categoria=codigo, nome=CATEGORIAS[codigo], regra=regra)

    if lucros:
        if lucros[-1] <= 0:
            return resultado("recuperacao", "último lucro anual ≤ 0")
        if any(x <= 0 for x in lucros[-4:-1]):
            return resultado("recuperacao", "prejuízo em algum dos 3 anos anteriores, lucro atual positivo")
    if setor and any(s.lower() in setor.lower() for s in p.setores_ciclicos):
        return resultado("ciclica", f"setor cíclico ({setor})")
    if len(lucros) >= 4 and mean(lucros) > 0 and pstdev(lucros) / mean(lucros) > p.cv_lucro_ciclica:
        return resultado("ciclica", f"lucros voláteis (CV > {p.cv_lucro_ciclica})")
    if p_vp is not None and 0 < p_vp < p.pvp_ativos_ocultos:
        return resultado("ativos_ocultos", f"P/VP < {p.pvp_ativos_ocultos}")
    if crescimento is None:
        return indisponivel("dado indisponível: crescimento do lucro")
    if crescimento >= p.crescimento_rapido:
        return resultado("crescimento_rapido", f"crescimento ≥ {p.crescimento_rapido:.0%} a.a.")
    if crescimento >= p.crescimento_robusta:
        return resultado("robusta", f"crescimento entre {p.crescimento_robusta:.0%} e {p.crescimento_rapido:.0%} a.a.")
    return resultado("crescimento_lento", f"crescimento < {p.crescimento_robusta:.0%} a.a.")
