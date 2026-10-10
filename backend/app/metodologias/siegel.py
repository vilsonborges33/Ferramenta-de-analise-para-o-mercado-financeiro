"""Jeremy Siegel, *Investindo em Ações no Longo Prazo*.

- Retorno real (Fisher): (1 + nominal) ÷ (1 + inflação) − 1.
- Retorno total com reinvestimento de dividendos (índice acumulado).
- Série acumulada real por classe de ativo.
- CAPE (P/L de Shiller): preço ÷ média do LPA real dos últimos 10 anos.
- Reversão à média do P/L: distância do P/L atual à média histórica em desvios-padrão.
- Prêmio de risco das ações: earnings yield do CAPE (1/CAPE, retorno real implícito) − juro real.
"""

from collections.abc import Sequence
from statistics import mean, pstdev

from app.metodologias.tipos import Numero, Resultado, faltando, indisponivel, ok


def retorno_real(retorno_nominal: Numero, inflacao: Numero) -> Resultado:
    """(1 + nominal) ÷ (1 + inflação) − 1."""
    if f := faltando(retorno_nominal=retorno_nominal, inflacao=inflacao):
        return f
    if inflacao <= -1:
        return indisponivel("inflação ≤ −100%")
    return ok((1 + retorno_nominal) / (1 + inflacao) - 1)


def indice_retorno_total(precos: Sequence[float], dividendos: Sequence[float], base: float = 100.0) -> Resultado:
    """Índice com reinvestimento: I_t = I_{t−1} × (P_t + D_t) ÷ P_{t−1}.

    `dividendos[t]` = dividendo por ação recebido no período t (0 se nenhum). Valor = índice final;
    `detalhes['serie']` = série completa.
    """
    if len(precos) < 2 or len(precos) != len(dividendos):
        return indisponivel("séries de preços e dividendos precisam ter o mesmo tamanho (≥ 2)")
    serie = [base]
    for t in range(1, len(precos)):
        if precos[t - 1] <= 0:
            return indisponivel("preço não positivo na série")
        serie.append(serie[-1] * (precos[t] + dividendos[t]) / precos[t - 1])
    return ok(serie[-1], serie=serie)


def acumulado_real(retornos_nominais: Sequence[float], inflacoes: Sequence[float], base: float = 1.0) -> Resultado:
    """Crescimento real acumulado de R$ 1 (ou `base`) período a período; `detalhes['serie']`."""
    if not retornos_nominais or len(retornos_nominais) != len(inflacoes):
        return indisponivel("séries de retorno e inflação precisam ter o mesmo tamanho")
    serie = [base]
    for r, i in zip(retornos_nominais, inflacoes, strict=True):
        serie.append(serie[-1] * (1 + r) / (1 + i))
    return ok(serie[-1], serie=serie)


def lpa_real(lpas_nominais: Sequence[float], indice_precos: Sequence[float]) -> list[float]:
    """Converte LPAs para moeda de hoje: LPA × (índice atual ÷ índice do período)."""
    atual = indice_precos[-1]
    return [lpa * atual / idx for lpa, idx in zip(lpas_nominais, indice_precos, strict=True)]


def cape(preco: Numero, lpas_reais_10_anos: Sequence[Numero], anos: int = 10) -> Resultado:
    """CAPE = preço ÷ média do LPA real dos últimos `anos` anos."""
    if f := faltando(preco=preco):
        return f
    lpas = list(lpas_reais_10_anos)[-anos:]
    if len(lpas) < anos or any(x is None for x in lpas):
        return indisponivel(f"dado indisponível: menos de {anos} anos de LPA")
    media = mean(lpas)
    if media <= 0:
        return indisponivel("LPA real médio não positivo")
    return ok(preco / media, lpa_medio=media)


def desvio_da_media(valor_atual: Numero, historico: Sequence[float]) -> Resultado:
    """Reversão à média: (atual − média) ÷ desvio-padrão do histórico (z-score)."""
    if valor_atual is None:
        return indisponivel("dado indisponível: valor atual")
    if len(historico) < 3:
        return indisponivel("histórico curto demais (mínimo 3 observações)")
    media, desvio = mean(historico), pstdev(historico)
    if desvio == 0:
        return indisponivel("histórico sem variação")
    return ok((valor_atual - media) / desvio, media=media, desvio=desvio)


def premio_risco_acoes(cape_: Numero, juro_real: Numero) -> Resultado:
    """Prêmio = 1/CAPE − juro real (ex.: NTN-B longa)."""
    if f := faltando(cape=cape_, juro_real=juro_real):
        return f
    if cape_ <= 0:
        return indisponivel("CAPE não positivo")
    return ok(1 / cape_ - juro_real, earnings_yield_real=1 / cape_)
