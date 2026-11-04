"""Ferramentas financeiras gerais (Fase 8): juros compostos, taxas equivalentes e plano de aposentadoria.

Matemática financeira clássica (capitalização composta), sem livro específico; o plano de aposentadoria
usa a ideia de "viver de renda" com o dividend yield informado pelo usuário (Bazin/Siegel), sem consumir o
principal. Convenções:

- Juros compostos: M_t = M_{t−1} × (1 + i) + A, aporte A no fim de cada período.
- Taxa equivalente: (1 + i_destino) = (1 + i_origem)^(n_destino / n_origem), com n = períodos por ano
  (dia útil = 252, mês = 12, ano = 1).
- Aposentadoria: renda mensal = patrimônio × DY anual ÷ 12; patrimônio necessário = meta × 12 ÷ DY;
  aporte necessário = PMT que leva o patrimônio de hoje à meta no prazo.
"""

import math

from app.metodologias.tipos import Numero, Resultado, faltando, indisponivel, ok

PERIODOS_POR_ANO = {"dia_util": 252, "dia_corrido": 365, "mes": 12, "trimestre": 4, "semestre": 2, "ano": 1}


def juros_compostos(inicial: Numero, aporte: Numero, taxa: Numero, periodos: int) -> Resultado:
    """Montante após `periodos` com aporte no fim de cada período. `detalhes['serie']` traz período a período
    (montante, total investido e juros acumulados)."""
    if f := faltando(inicial=inicial, aporte=aporte, taxa=taxa):
        return f
    if periodos <= 0:
        return indisponivel("número de períodos deve ser positivo")
    if taxa <= -1:
        return indisponivel("taxa ≤ −100% por período")
    if inicial < 0 or aporte < 0:
        return indisponivel("valores negativos não são aceitos")
    montante, investido = float(inicial), float(inicial)
    serie = [{"periodo": 0, "montante": montante, "investido": investido, "juros": 0.0}]
    for t in range(1, periodos + 1):
        montante = montante * (1 + taxa) + aporte
        investido += aporte
        serie.append({"periodo": t, "montante": montante, "investido": investido, "juros": montante - investido})
    return ok(montante, investido=investido, juros=montante - investido, serie=serie)


def taxa_equivalente(taxa: Numero, origem: str, destino: str) -> Resultado:
    """(1 + i_destino) = (1 + i_origem)^(n_origem / n_destino), n = períodos por ano."""
    if f := faltando(taxa=taxa):
        return f
    if origem not in PERIODOS_POR_ANO or destino not in PERIODOS_POR_ANO:
        return indisponivel(f"período deve ser um de {', '.join(PERIODOS_POR_ANO)}")
    if taxa <= -1:
        return indisponivel("taxa ≤ −100%")
    expoente = PERIODOS_POR_ANO[origem] / PERIODOS_POR_ANO[destino]
    todas = {p: (1 + taxa) ** (PERIODOS_POR_ANO[origem] / n) - 1 for p, n in PERIODOS_POR_ANO.items()}
    return ok((1 + taxa) ** expoente - 1, todas=todas)


def taxa_real(nominal: Numero, inflacao: Numero) -> Resultado:
    """Fisher: (1 + nominal) ÷ (1 + inflação) − 1."""
    if f := faltando(nominal=nominal, inflacao=inflacao):
        return f
    if inflacao <= -1:
        return indisponivel("inflação ≤ −100%")
    return ok((1 + nominal) / (1 + inflacao) - 1)


def aporte_necessario(inicial: float, meta: float, taxa: float, periodos: int) -> float:
    """PMT tal que inicial × (1+i)^n + PMT × [(1+i)^n − 1] ÷ i = meta (aporte no fim do período)."""
    if taxa == 0:
        return max(0.0, (meta - inicial) / periodos)
    fator = (1 + taxa) ** periodos
    return max(0.0, (meta - inicial * fator) * taxa / (fator - 1))


def periodos_ate(inicial: float, aporte: float, taxa: float, meta: float, limite: int = 1200) -> int | None:
    """Menor n com montante ≥ meta (None se não atingir em `limite` períodos)."""
    if inicial >= meta:
        return 0
    if taxa > 0 and (inicial > 0 or aporte > 0):
        # Fechada: n = ln[(meta·i + A) ÷ (inicial·i + A)] ÷ ln(1 + i)
        n = math.log((meta * taxa + aporte) / (inicial * taxa + aporte)) / math.log(1 + taxa)
        n = math.ceil(n - 1e-9)
        return n if n <= limite else None
    if taxa == 0 and aporte > 0:
        n = math.ceil((meta - inicial) / aporte)
        return n if n <= limite else None
    return None


def plano_aposentadoria(inicial: Numero, aporte_mensal: Numero, retorno_anual: Numero, anos: int,
                        dividend_yield_anual: Numero, meta_renda_mensal: Numero) -> Resultado:
    """Patrimônio no fim do prazo, renda mensal que ele gera pelo DY, patrimônio e aporte necessários para a meta.

    Valor = patrimônio final. O retorno anual é convertido para mensal pela taxa equivalente.
    """
    if f := faltando(inicial=inicial, aporte_mensal=aporte_mensal, retorno_anual=retorno_anual,
                     dividend_yield_anual=dividend_yield_anual, meta_renda_mensal=meta_renda_mensal):
        return f
    if anos <= 0:
        return indisponivel("horizonte deve ser positivo")
    if dividend_yield_anual <= 0:
        return indisponivel("dividend yield esperado deve ser positivo")
    if retorno_anual <= -1:
        return indisponivel("retorno ≤ −100% ao ano")
    mensal = (1 + retorno_anual) ** (1 / 12) - 1
    meses = anos * 12
    acumulo = juros_compostos(inicial, aporte_mensal, mensal, meses)
    if not acumulo.disponivel:
        return acumulo
    final = acumulo.valor
    necessario = meta_renda_mensal * 12 / dividend_yield_anual
    anual = [p for p in acumulo.detalhes["serie"] if p["periodo"] % 12 == 0]
    serie = [{"ano": p["periodo"] // 12, "patrimonio": p["montante"], "investido": p["investido"],
              "renda_mensal": p["montante"] * dividend_yield_anual / 12} for p in anual]
    meses_meta = periodos_ate(inicial, aporte_mensal, mensal, necessario)
    return ok(final,
              taxa_mensal=mensal,
              investido=acumulo.detalhes["investido"],
              renda_mensal=final * dividend_yield_anual / 12,
              renda_anual=final * dividend_yield_anual,
              patrimonio_necessario=necessario,
              aporte_necessario=aporte_necessario(inicial, necessario, mensal, meses),
              meses_ate_meta=meses_meta,
              atinge_meta=final >= necessario,
              serie=serie)
