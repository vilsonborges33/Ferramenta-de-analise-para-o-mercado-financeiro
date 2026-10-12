"""Indicadores fundamentalistas básicos (múltiplos, rentabilidade, endividamento, crescimento).

Funções puras: recebem números, devolvem `Resultado`. Valores monetários em unidades da moeda
(nada de "milhares"). Taxas e margens são devolvidas em fração (0,12 = 12%).

Referências gerais:
- Aswath Damodaran, *Valuation*: múltiplos de lucro, de valor patrimonial e de valor da firma
  (EV), ROIC e retorno sobre capital.
- Benjamin Graham, *O Investidor Inteligente*: P/L, P/VP, liquidez corrente e endividamento como
  critérios do investidor defensivo.
"""

from collections.abc import Iterable, Sequence

from app.metodologias.tipos import Numero, Resultado, faltando, indisponivel, ok

AVISO_LUCRO_NEGATIVO = "denominador negativo: múltiplo negativo não tem interpretação usual"


def _multiplo(numerador: Numero, denominador: Numero, nome_num: str, nome_den: str) -> Resultado:
    if f := faltando(**{nome_num: numerador, nome_den: denominador}):
        return f
    if denominador == 0:
        return indisponivel(f"{nome_den} igual a zero")
    valor = numerador / denominador
    if denominador < 0:
        return ok(valor, aviso=AVISO_LUCRO_NEGATIVO)
    return ok(valor)


def _razao(numerador: Numero, denominador: Numero, nome_num: str, nome_den: str) -> Resultado:
    """Razão simples (margens, retornos). Denominador ≤ 0 torna a razão sem sentido."""
    if f := faltando(**{nome_num: numerador, nome_den: denominador}):
        return f
    if denominador == 0:
        return indisponivel(f"{nome_den} igual a zero")
    if denominador < 0:
        return indisponivel(f"{nome_den} negativo: razão não interpretável")
    return ok(numerador / denominador)


# ------------------------------------------------------------- base de cálculo


def acoes_em_circulacao(total_emitidas: Numero, em_tesouraria: Numero) -> Resultado:
    """Ações em circulação = ações emitidas − ações em tesouraria.

    Fonte típica: arquivo "composição do capital" do DFP/ITR (CVM).
    """
    if f := faltando(total_emitidas=total_emitidas):
        return f
    circulacao = total_emitidas - (em_tesouraria or 0)
    if circulacao <= 0:
        return indisponivel("quantidade de ações em circulação não positiva")
    return ok(circulacao)


def fator_escala_acoes(total_acoes: Numero, preco: Numero, patrimonio_liquido: Numero,
                       receita_liquida: Numero) -> tuple[int, str | None]:
    """Detecta quantidade de ações informada em milhares no formulário da CVM (sem indicação no arquivo).

    Se o valor de mercado resultante for implausível (P/VP < 0,02, ou P/Receita < 0,005 quando não há PL
    positivo) e multiplicar por 1.000 o levar a uma faixa plausível, devolve (1000, aviso); senão (1, None).
    """
    if not total_acoes or not preco or total_acoes <= 0 or preco <= 0:
        return 1, None
    mercado = total_acoes * preco
    for base, minimo, maximo, nome in ((patrimonio_liquido, 0.02, 100.0, "P/VP"),
                                       (receita_liquida, 0.005, 100.0, "P/Receita")):
        if base is None or base <= 0:
            continue
        razao = mercado / base
        if razao < minimo and minimo <= razao * 1000 <= maximo:
            return 1000, (f"quantidade de ações informada em milhares no formulário da CVM; convertida "
                          f"(o {nome} sem conversão seria {razao:.4f})")
        return 1, None
    return 1, None


def valor_de_mercado(classes: Sequence[tuple[Numero, Numero]]) -> Resultado:
    """Valor de mercado = Σ (ações em circulação da classe × cotação da classe).

    Para empresas com ON e PN, cada classe é multiplicada pela própria cotação (Damodaran,
    *Valuation*: valor de mercado do patrimônio). `classes` = [(quantidade, preço), ...].
    """
    if not classes:
        return indisponivel("dado indisponível: nenhuma classe de ação com quantidade e cotação")
    total = 0.0
    for quantidade, preco in classes:
        if quantidade is None or preco is None:
            return indisponivel("dado indisponível: quantidade ou cotação de uma das classes")
        total += quantidade * preco
    if total <= 0:
        return indisponivel("valor de mercado não positivo")
    return ok(total)


def divida_bruta(emprestimos_cp: Numero, emprestimos_lp: Numero) -> Resultado:
    """Dívida bruta = empréstimos e financiamentos de curto prazo + de longo prazo.

    Limitação: não inclui passivos de arrendamento (IFRS 16) nem debêntures classificadas fora
    da conta de empréstimos e financiamentos.
    """
    if emprestimos_cp is None and emprestimos_lp is None:
        return indisponivel("dado indisponível: empréstimos e financiamentos")
    return ok((emprestimos_cp or 0) + (emprestimos_lp or 0))


def divida_liquida(divida_bruta_: Numero, caixa: Numero, aplicacoes_financeiras: Numero) -> Resultado:
    """Dívida líquida = dívida bruta − caixa e equivalentes − aplicações financeiras de curto prazo."""
    if f := faltando(divida_bruta=divida_bruta_, caixa=caixa):
        return f
    return ok(divida_bruta_ - caixa - (aplicacoes_financeiras or 0))


def valor_da_firma(valor_mercado: Numero, divida_liquida_: Numero) -> Resultado:
    """EV (enterprise value) = valor de mercado + dívida líquida (Damodaran, *Valuation*).

    Limitação: não soma participação de não controladores nem subtrai ativos não operacionais.
    """
    if f := faltando(valor_mercado=valor_mercado, divida_liquida=divida_liquida_):
        return f
    return ok(valor_mercado + divida_liquida_)


def ebitda(ebit: Numero, depreciacao_amortizacao: Numero) -> Resultado:
    """EBITDA = EBIT + depreciação e amortização (D&A obtida na DFC)."""
    if f := faltando(ebit=ebit, depreciacao_amortizacao=depreciacao_amortizacao):
        return f
    return ok(ebit + abs(depreciacao_amortizacao))


def por_acao(valor: Numero, acoes: Numero, nome: str) -> Resultado:
    """Valor por ação (LPA, VPA)."""
    if f := faltando(**{nome: valor, "acoes_em_circulacao": acoes}):
        return f
    if acoes <= 0:
        return indisponivel("quantidade de ações não positiva")
    return ok(valor / acoes)


def lpa(lucro_liquido: Numero, acoes: Numero) -> Resultado:
    """LPA = lucro líquido atribuído aos controladores (12 meses) ÷ ações em circulação."""
    return por_acao(lucro_liquido, acoes, "lucro_liquido")


def vpa(patrimonio_liquido: Numero, acoes: Numero) -> Resultado:
    """VPA = patrimônio líquido dos controladores ÷ ações em circulação."""
    return por_acao(patrimonio_liquido, acoes, "patrimonio_liquido")


# --------------------------------------------------------------------- múltiplos


def p_l(valor_mercado: Numero, lucro_liquido: Numero) -> Resultado:
    """P/L = valor de mercado ÷ lucro líquido dos controladores em 12 meses (Graham)."""
    return _multiplo(valor_mercado, lucro_liquido, "valor_mercado", "lucro_liquido")


def p_vp(valor_mercado: Numero, patrimonio_liquido: Numero) -> Resultado:
    """P/VP = valor de mercado ÷ patrimônio líquido dos controladores (Graham)."""
    return _multiplo(valor_mercado, patrimonio_liquido, "valor_mercado", "patrimonio_liquido")


def p_receita(valor_mercado: Numero, receita_liquida: Numero) -> Resultado:
    """P/Receita (PSR) = valor de mercado ÷ receita líquida em 12 meses (Damodaran)."""
    return _multiplo(valor_mercado, receita_liquida, "valor_mercado", "receita_liquida")


def p_ebit(valor_mercado: Numero, ebit_: Numero) -> Resultado:
    """P/EBIT = valor de mercado ÷ EBIT em 12 meses."""
    return _multiplo(valor_mercado, ebit_, "valor_mercado", "ebit")


def p_ebitda(valor_mercado: Numero, ebitda_: Numero) -> Resultado:
    """P/EBITDA = valor de mercado ÷ EBITDA em 12 meses."""
    return _multiplo(valor_mercado, ebitda_, "valor_mercado", "ebitda")


def ev_ebit(ev: Numero, ebit_: Numero) -> Resultado:
    """EV/EBIT = valor da firma ÷ EBIT em 12 meses (Damodaran)."""
    return _multiplo(ev, ebit_, "ev", "ebit")


def ev_ebitda(ev: Numero, ebitda_: Numero) -> Resultado:
    """EV/EBITDA = valor da firma ÷ EBITDA em 12 meses (Damodaran)."""
    return _multiplo(ev, ebitda_, "ev", "ebitda")


def p_ativo(valor_mercado: Numero, ativo_total: Numero) -> Resultado:
    """P/Ativo = valor de mercado ÷ ativo total."""
    return _multiplo(valor_mercado, ativo_total, "valor_mercado", "ativo_total")


def p_capital_giro(valor_mercado: Numero, ativo_circulante: Numero, passivo_circulante: Numero) -> Resultado:
    """P/Capital de giro = valor de mercado ÷ (ativo circulante − passivo circulante)."""
    if f := faltando(ativo_circulante=ativo_circulante, passivo_circulante=passivo_circulante):
        return f
    return _multiplo(valor_mercado, ativo_circulante - passivo_circulante, "valor_mercado", "capital_de_giro")


def p_ativo_circulante_liquido(
    valor_mercado: Numero, ativo_circulante: Numero, passivo_total: Numero
) -> Resultado:
    """P/Ativo circulante líquido = valor de mercado ÷ (ativo circulante − passivo total).

    O ativo circulante líquido é a medida de "net current assets" usada por Graham.
    """
    if f := faltando(ativo_circulante=ativo_circulante, passivo_total=passivo_total):
        return f
    return _multiplo(
        valor_mercado, ativo_circulante - passivo_total, "valor_mercado", "ativo_circulante_liquido"
    )


def provento_liquido(valor_bruto: Numero, tipo: str, aliquota_jcp: float = 0.15) -> Resultado:
    """Provento líquido por ação: JCP sofre IR retido na fonte (padrão 15%); dividendos e rendimentos
    de FII são isentos na fonte para a pessoa física (DECISOES.md D-019).
    """
    if f := faltando(valor_bruto=valor_bruto):
        return f
    if tipo == "JCP":
        return ok(valor_bruto * (1 - aliquota_jcp), bruto=valor_bruto)
    return ok(valor_bruto, bruto=valor_bruto)


def dividend_yield(proventos_por_acao_12m: Numero, preco: Numero) -> Resultado:
    """DY = soma dos proventos líquidos por ação pagos nos últimos 12 meses ÷ cotação.

    Critério (DECISOES.md D-019/D-020): janela pela data de pagamento; JCP pelo valor líquido de IR.
    """
    if f := faltando(proventos_12m=proventos_por_acao_12m, preco=preco):
        return f
    if preco <= 0:
        return indisponivel("cotação não positiva")
    return ok(proventos_por_acao_12m / preco)


def payout(proventos_por_acao_12m: Numero, lpa_: Numero) -> Resultado:
    """Payout = proventos por ação em 12 meses ÷ LPA em 12 meses."""
    if f := faltando(proventos_12m=proventos_por_acao_12m, lpa=lpa_):
        return f
    if lpa_ <= 0:
        return indisponivel("LPA não positivo: payout não interpretável")
    return ok(proventos_por_acao_12m / lpa_)


# -------------------------------------------------------------- rentabilidade


def roe(lucro_liquido: Numero, patrimonio_liquido: Numero) -> Resultado:
    """ROE = lucro líquido dos controladores (12 m) ÷ patrimônio líquido dos controladores.

    Limitação: usa o PL do fim do período, não a média.
    """
    return _razao(lucro_liquido, patrimonio_liquido, "lucro_liquido", "patrimonio_liquido")


def roa(lucro_liquido: Numero, ativo_total: Numero) -> Resultado:
    """ROA = lucro líquido (12 m) ÷ ativo total."""
    return _razao(lucro_liquido, ativo_total, "lucro_liquido", "ativo_total")


def roic(ebit_: Numero, patrimonio_liquido: Numero, divida_liquida_: Numero, aliquota: float = 0.34) -> Resultado:
    """ROIC = EBIT × (1 − alíquota) ÷ (patrimônio líquido + dívida líquida) (Damodaran).

    Parâmetro: alíquota de IR/CSLL, padrão 34% (alíquota nominal no Brasil).
    Limitação: capital investido do fim do período; alíquota nominal, não a efetiva.
    """
    if f := faltando(ebit=ebit_, patrimonio_liquido=patrimonio_liquido, divida_liquida=divida_liquida_):
        return f
    capital = patrimonio_liquido + divida_liquida_
    return _razao(ebit_ * (1 - aliquota), capital, "nopat", "capital_investido")


def margem(valor: Numero, receita_liquida: Numero, nome: str) -> Resultado:
    """Margem = resultado ÷ receita líquida (bruta, EBIT, EBITDA ou líquida)."""
    return _razao(valor, receita_liquida, nome, "receita_liquida")


def giro_ativos(receita_liquida: Numero, ativo_total: Numero) -> Resultado:
    """Giro dos ativos = receita líquida (12 m) ÷ ativo total."""
    return _razao(receita_liquida, ativo_total, "receita_liquida", "ativo_total")


# ---------------------------------------------------------------- endividamento


def divida_liquida_sobre(divida_liquida_: Numero, base: Numero, nome_base: str) -> Resultado:
    """Dívida líquida ÷ PL, EBITDA ou EBIT."""
    return _multiplo(divida_liquida_, base, "divida_liquida", nome_base)


def pl_sobre_ativos(patrimonio_liquido: Numero, ativo_total: Numero) -> Resultado:
    """PL ÷ ativos totais."""
    return _razao(patrimonio_liquido, ativo_total, "patrimonio_liquido", "ativo_total")


def passivos_sobre_ativos(passivo_total: Numero, ativo_total: Numero) -> Resultado:
    """Passivos ÷ ativos totais (endividamento geral)."""
    return _razao(passivo_total, ativo_total, "passivo_total", "ativo_total")


def liquidez_corrente(ativo_circulante: Numero, passivo_circulante: Numero) -> Resultado:
    """Liquidez corrente = ativo circulante ÷ passivo circulante (Graham: ≥ 2 para o defensivo)."""
    return _razao(ativo_circulante, passivo_circulante, "ativo_circulante", "passivo_circulante")


# ------------------------------------------------------------------- crescimento


def cagr(valor_inicial: Numero, valor_final: Numero, anos: float) -> Resultado:
    """CAGR = (valor final ÷ valor inicial)^(1/anos) − 1.

    Indisponível quando algum extremo é zero ou negativo (taxa composta não definida).
    """
    if f := faltando(valor_inicial=valor_inicial, valor_final=valor_final):
        return f
    if anos <= 0:
        return indisponivel("período em anos não positivo")
    if valor_inicial <= 0 or valor_final <= 0:
        return indisponivel("valor inicial ou final não positivo: CAGR não definido")
    return ok((valor_final / valor_inicial) ** (1 / anos) - 1)


# --------------------------------------------------------------------- mercado


def liquidez_media_diaria(volumes_financeiros: Iterable[Numero]) -> Resultado:
    """Liquidez média diária = média simples do volume financeiro negociado nos pregões da janela."""
    valores = [v for v in volumes_financeiros if v is not None]
    if not valores:
        return indisponivel("dado indisponível: sem pregões na janela")
    return ok(sum(valores) / len(valores), pregoes=len(valores))
