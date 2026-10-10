"""Décio Bazin, *Faça Fortuna com Ações*.

- Preço teto = dividendo médio por ação ÷ yield mínimo (padrão 6%).
- Base do dividendo: proventos pagos nos últimos 12 meses (padrão) ou média anual de N anos.
- Critérios complementares: endividamento baixo e regularidade de proventos.
- Preço teto projetivo: lucro projetado × payout ÷ ações ÷ yield mínimo.

Proventos líquidos (JCP após IR) e janela pela data de pagamento: DECISOES.md D-019/D-020.
"""

from collections.abc import Sequence

from app.metodologias.tipos import Numero, Resultado, faltando, indisponivel, ok

YIELD_MINIMO = 0.06


def dividendo_medio_anual(proventos_por_ano: Sequence[Numero], anos: int) -> Resultado:
    """Média simples dos proventos por ação dos `anos` anos mais recentes (ano sem provento = 0)."""
    valores = list(proventos_por_ano)[-anos:]
    if anos <= 0:
        return indisponivel("número de anos não positivo")
    if len(valores) < anos or any(v is None for v in valores):
        return indisponivel(f"dado indisponível: menos de {anos} anos de histórico de proventos")
    return ok(sum(valores) / anos, anos=anos)


def preco_teto(dividendo_por_acao: Numero, yield_minimo: float = YIELD_MINIMO) -> Resultado:
    """Preço teto = dividendo por ação ÷ yield mínimo."""
    if f := faltando(dividendo_por_acao=dividendo_por_acao):
        return f
    if yield_minimo <= 0:
        return indisponivel("yield mínimo não positivo")
    if dividendo_por_acao <= 0:
        return indisponivel("sem proventos no período: preço teto de Bazin não se aplica")
    return ok(dividendo_por_acao / yield_minimo)


def potencial(preco_teto_: Numero, preco: Numero) -> Resultado:
    """Distância até o teto = preço teto ÷ cotação − 1 (positivo = cotação abaixo do teto)."""
    if f := faltando(preco_teto=preco_teto_, preco=preco):
        return f
    if preco <= 0:
        return indisponivel("cotação não positiva")
    return ok(preco_teto_ / preco - 1)


def endividamento_baixo(divida_liquida: Numero, patrimonio_liquido: Numero, maximo: float = 1.0) -> Resultado:
    """Critério: dívida líquida ÷ PL ≤ máximo (padrão 1,0). Valor 1 = atende, 0 = não atende."""
    if f := faltando(divida_liquida=divida_liquida, patrimonio_liquido=patrimonio_liquido):
        return f
    if patrimonio_liquido <= 0:
        return ok(0, motivo="patrimônio líquido não positivo")
    razao = divida_liquida / patrimonio_liquido
    return ok(1 if razao <= maximo else 0, dl_pl=razao, maximo=maximo)


def regularidade_proventos(proventos_por_ano: Sequence[Numero], anos: int = 5) -> Resultado:
    """Critério: pagou proventos em todos os `anos` anos mais recentes. Valor 1 = atende, 0 = não."""
    valores = list(proventos_por_ano)[-anos:]
    if len(valores) < anos or any(v is None for v in valores):
        return indisponivel(f"dado indisponível: menos de {anos} anos de histórico de proventos")
    pagos = sum(1 for v in valores if v > 0)
    return ok(1 if pagos == anos else 0, anos_com_pagamento=pagos, anos=anos)


def preco_teto_projetivo(lucro_projetado: Numero, payout: Numero, acoes: Numero,
                         yield_minimo: float = YIELD_MINIMO) -> Resultado:
    """Preço teto projetivo = (lucro projetado × payout ÷ ações) ÷ yield mínimo.

    `detalhes` traz o dividendo projetado por ação.
    """
    if f := faltando(lucro_projetado=lucro_projetado, payout=payout, acoes=acoes):
        return f
    if acoes <= 0:
        return indisponivel("quantidade de ações não positiva")
    if not 0 <= payout <= 1.5:
        return indisponivel("payout fora do intervalo 0–150%")
    dividendo = lucro_projetado * payout / acoes
    teto = preco_teto(dividendo, yield_minimo)
    if not teto.disponivel:
        return indisponivel(teto.motivo_indisponivel, dividendo_projetado=dividendo)
    return ok(teto.valor, dividendo_projetado=dividendo)


def yield_projetivo(dividendo_projetado: Numero, preco: Numero) -> Resultado:
    """Yield projetivo = dividendo projetado por ação ÷ cotação."""
    if f := faltando(dividendo_projetado=dividendo_projetado, preco=preco):
        return f
    if preco <= 0:
        return indisponivel("cotação não positiva")
    return ok(dividendo_projetado / preco)
