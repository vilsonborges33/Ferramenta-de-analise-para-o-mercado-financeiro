"""Registro único das métricas (DECISOES.md D-006).

Alimenta a página "Como é calculado", a validação de parâmetros da API e o job de recálculo.
"""

from dataclasses import asdict, dataclass, field

DAMODARAN = "Valuation — Aswath Damodaran"
GRAHAM = "O Investidor Inteligente — Benjamin Graham"
SIEGEL = "Investindo em Ações no Longo Prazo — Jeremy Siegel"
LO_FOERSTER = "Em Busca do Portfólio Perfeito — Andrew Lo e Stephen Foerster"
BOGLE = "O Investidor de Bom Senso — John Bogle"
GREENBLATT = "A Fórmula Mágica — Joel Greenblatt"
BAZIN = "Faça Fortuna com Ações — Décio Bazin"
LYNCH = "Batendo o Mercado — Peter Lynch"
MCKINSEY = "Valuation: Guia Fundamental e Modelagem em Excel"
DALIO = "Princípios — Ray Dalio"

LIMITACAO_TTM = "Usa os últimos 12 meses (soma dos 4 últimos trimestres divulgados à CVM)."
LIMITACAO_PRECO = "Cotação de fechamento mais recente disponível; o dado contábil pode ter meses de defasagem."
LIMITACAO_FINANCEIRAS = "Não se aplica a bancos e seguradoras (plano de contas próprio)."


@dataclass(frozen=True)
class Parametro:
    chave: str
    descricao: str
    padrao: float
    minimo: float
    maximo: float


@dataclass(frozen=True)
class Metrica:
    id: str
    nome: str
    grupo: str
    unidade: str  # "x" (múltiplo), "%", "R$", "R$/ação", "un"
    formula: str
    referencia: str
    aplica_a: tuple[str, ...] = ("ACAO",)
    limitacoes: tuple[str, ...] = ()
    parametros: tuple[Parametro, ...] = field(default_factory=tuple)
    premissas: tuple[str, ...] = ()
    # False = método calculado sob demanda (screening, valuation, carteira), sem card na página do ativo.
    exibir_no_ativo: bool = True
    versao: str = "1"

    def como_dict(self) -> dict:
        return asdict(self)


_ALIQUOTA_JCP = Parametro("aliquota_jcp", "IR retido na fonte sobre JCP", 0.15, 0.0, 0.5)
_ALIQUOTA = Parametro("aliquota_ir", "Alíquota de IR/CSLL sobre o EBIT", 0.34, 0.0, 0.5)

METRICAS: tuple[Metrica, ...] = (
    # base
    Metrica("basico.valor_mercado", "Valor de mercado", "Base", "R$",
            "Σ (ações em circulação da classe × cotação da classe)", DAMODARAN,
            limitacoes=(LIMITACAO_PRECO,)),
    Metrica("basico.divida_bruta", "Dívida bruta", "Base", "R$",
            "Empréstimos e financiamentos de curto prazo + longo prazo", DAMODARAN,
            limitacoes=("Não inclui arrendamentos (IFRS 16).", LIMITACAO_FINANCEIRAS)),
    Metrica("basico.divida_liquida", "Dívida líquida", "Base", "R$",
            "Dívida bruta − caixa e equivalentes − aplicações financeiras de curto prazo", DAMODARAN,
            limitacoes=(LIMITACAO_FINANCEIRAS,)),
    Metrica("basico.ev", "Valor da firma (EV)", "Base", "R$",
            "Valor de mercado + dívida líquida", DAMODARAN,
            limitacoes=("Não soma participação de não controladores.", LIMITACAO_FINANCEIRAS)),
    Metrica("basico.lpa", "LPA", "Valuation", "R$/ação",
            "Lucro líquido dos controladores (12 m) ÷ ações em circulação", GRAHAM, limitacoes=(LIMITACAO_TTM,)),
    Metrica("basico.vpa", "VPA", "Valuation", "R$/ação",
            "Patrimônio líquido dos controladores ÷ ações em circulação", GRAHAM),
    # múltiplos
    Metrica("basico.p_l", "P/L", "Valuation", "x", "Valor de mercado ÷ lucro líquido dos controladores (12 m)",
            GRAHAM, limitacoes=(LIMITACAO_TTM, LIMITACAO_PRECO)),
    Metrica("basico.p_vp", "P/VP", "Valuation", "x", "Valor de mercado ÷ patrimônio líquido dos controladores",
            GRAHAM, limitacoes=(LIMITACAO_PRECO,)),
    Metrica("basico.p_receita", "P/Receita (PSR)", "Valuation", "x",
            "Valor de mercado ÷ receita líquida (12 m)", DAMODARAN, limitacoes=(LIMITACAO_TTM,)),
    Metrica("basico.p_ebit", "P/EBIT", "Valuation", "x", "Valor de mercado ÷ EBIT (12 m)", DAMODARAN,
            limitacoes=(LIMITACAO_TTM, LIMITACAO_FINANCEIRAS)),
    Metrica("basico.p_ebitda", "P/EBITDA", "Valuation", "x", "Valor de mercado ÷ EBITDA (12 m)", DAMODARAN,
            limitacoes=(LIMITACAO_TTM, LIMITACAO_FINANCEIRAS)),
    Metrica("basico.ev_ebit", "EV/EBIT", "Valuation", "x", "EV ÷ EBIT (12 m)", DAMODARAN,
            limitacoes=(LIMITACAO_TTM, LIMITACAO_FINANCEIRAS)),
    Metrica("basico.ev_ebitda", "EV/EBITDA", "Valuation", "x", "EV ÷ EBITDA (12 m)", DAMODARAN,
            limitacoes=(LIMITACAO_TTM, LIMITACAO_FINANCEIRAS)),
    Metrica("basico.p_ativo", "P/Ativo", "Valuation", "x", "Valor de mercado ÷ ativo total", DAMODARAN),
    Metrica("basico.p_capital_giro", "P/Capital de giro", "Valuation", "x",
            "Valor de mercado ÷ (ativo circulante − passivo circulante)", GRAHAM,
            limitacoes=(LIMITACAO_FINANCEIRAS,)),
    Metrica("basico.p_ativo_circ_liq", "P/Ativo circulante líquido", "Valuation", "x",
            "Valor de mercado ÷ (ativo circulante − passivo total)", GRAHAM, limitacoes=(LIMITACAO_FINANCEIRAS,)),
    Metrica("basico.dy", "Dividend yield (12 m)", "Valuation", "%",
            "Proventos líquidos por ação pagos nos últimos 12 meses ÷ cotação (JCP × (1 − IR))", GRAHAM,
            aplica_a=("ACAO", "FII"), parametros=(_ALIQUOTA_JCP,),
            limitacoes=("Depende da ingestão de proventos (plano pago da brapi).",
                        "JCP pelo valor líquido de IR na fonte; dividendos pelo valor declarado.",
                        "Janela pela data de pagamento: proventos anunciados e ainda não pagos não entram.",
                        "Com o Yahoo Finance como fonte: janela pela data-ex e valor bruto (o Yahoo não informa "
                        "data de pagamento nem separa JCP de dividendo).")),
    Metrica("basico.payout", "Payout", "Valuation", "%",
            "Proventos líquidos por ação pagos em 12 m ÷ LPA (12 m)", GRAHAM,
            parametros=(_ALIQUOTA_JCP,),
            limitacoes=("Depende da ingestão de proventos (plano pago da brapi).",)),
    # rentabilidade
    Metrica("basico.roe", "ROE", "Rentabilidade", "%",
            "Lucro líquido dos controladores (12 m) ÷ patrimônio líquido dos controladores", DAMODARAN,
            limitacoes=("Usa o PL do fim do período, não a média.",)),
    Metrica("basico.roa", "ROA", "Rentabilidade", "%", "Lucro líquido (12 m) ÷ ativo total", DAMODARAN),
    Metrica("basico.roic", "ROIC", "Rentabilidade", "%",
            "EBIT (12 m) × (1 − alíquota) ÷ (patrimônio líquido + dívida líquida)", DAMODARAN,
            limitacoes=("Alíquota nominal, não a efetiva.", LIMITACAO_FINANCEIRAS), parametros=(_ALIQUOTA,)),
    Metrica("basico.margem_bruta", "Margem bruta", "Rentabilidade", "%", "Lucro bruto ÷ receita líquida (12 m)",
            DAMODARAN, limitacoes=(LIMITACAO_FINANCEIRAS,)),
    Metrica("basico.margem_ebit", "Margem EBIT", "Rentabilidade", "%", "EBIT ÷ receita líquida (12 m)", DAMODARAN,
            limitacoes=(LIMITACAO_FINANCEIRAS,)),
    Metrica("basico.margem_ebitda", "Margem EBITDA", "Rentabilidade", "%", "EBITDA ÷ receita líquida (12 m)",
            DAMODARAN, limitacoes=(LIMITACAO_FINANCEIRAS,)),
    Metrica("basico.margem_liquida", "Margem líquida", "Rentabilidade", "%",
            "Lucro líquido dos controladores ÷ receita líquida (12 m)", DAMODARAN),
    Metrica("basico.giro_ativos", "Giro dos ativos", "Rentabilidade", "x", "Receita líquida (12 m) ÷ ativo total",
            DAMODARAN),
    # endividamento
    Metrica("basico.dl_pl", "Dívida líquida/PL", "Endividamento", "x",
            "Dívida líquida ÷ patrimônio líquido dos controladores", GRAHAM, limitacoes=(LIMITACAO_FINANCEIRAS,)),
    Metrica("basico.dl_ebitda", "Dívida líquida/EBITDA", "Endividamento", "x", "Dívida líquida ÷ EBITDA (12 m)",
            DAMODARAN, limitacoes=(LIMITACAO_FINANCEIRAS,)),
    Metrica("basico.dl_ebit", "Dívida líquida/EBIT", "Endividamento", "x", "Dívida líquida ÷ EBIT (12 m)",
            DAMODARAN, limitacoes=(LIMITACAO_FINANCEIRAS,)),
    Metrica("basico.pl_ativos", "PL/Ativos", "Endividamento", "%", "Patrimônio líquido ÷ ativo total", GRAHAM),
    Metrica("basico.passivos_ativos", "Passivos/Ativos", "Endividamento", "%", "Passivo total ÷ ativo total",
            GRAHAM),
    Metrica("basico.liquidez_corrente", "Liquidez corrente", "Endividamento", "x",
            "Ativo circulante ÷ passivo circulante", GRAHAM, limitacoes=(LIMITACAO_FINANCEIRAS,)),
    # crescimento
    Metrica("basico.cagr_receita_5a", "CAGR receita (5 anos)", "Crescimento", "%",
            "(Receita do último ano ÷ receita de 5 anos antes)^(1/5) − 1", GRAHAM,
            limitacoes=("Usa demonstrações anuais (DFP). Indisponível se algum extremo for ≤ 0.",)),
    Metrica("basico.cagr_lucro_5a", "CAGR lucro (5 anos)", "Crescimento", "%",
            "(Lucro do último ano ÷ lucro de 5 anos antes)^(1/5) − 1", GRAHAM,
            limitacoes=("Usa demonstrações anuais (DFP). Indisponível se algum extremo for ≤ 0.",)),
    # mercado
    Metrica("basico.liquidez_diaria", "Liquidez média diária (2 meses)", "Mercado", "R$",
            "Média do volume financeiro dos pregões dos últimos 2 meses", GRAHAM, aplica_a=("ACAO", "FII"),
            limitacoes=("Com o Yahoo Finance como fonte, o volume financeiro é estimado como fechamento × "
                        "quantidade negociada.",)),
    # FII
    Metrica("fii.p_vp", "P/VP", "Valuation", "x", "Cotação ÷ valor patrimonial por cota (informe mensal CVM)",
            GRAHAM, aplica_a=("FII",), limitacoes=("VP/cota do último informe mensal entregue à CVM.",)),
    Metrica("fii.vp_cota", "Valor patrimonial por cota", "Valuation", "R$/ação",
            "Patrimônio líquido ÷ cotas emitidas (informado no informe mensal)", GRAHAM, aplica_a=("FII",)),
    Metrica("fii.patrimonio_liquido", "Patrimônio líquido", "Base", "R$", "Informado no informe mensal CVM",
            GRAHAM, aplica_a=("FII",)),
    Metrica("fii.numero_cotistas", "Número de cotistas", "Base", "un", "Informado no informe mensal CVM",
            GRAHAM, aplica_a=("FII",)),
    Metrica("fii.rentab_patrimonial_12m", "Rentabilidade patrimonial (12 m, informada)", "Rentabilidade", "%",
            "Composição dos percentuais mensais informados à CVM: Π(1 + r_mês) − 1", GRAHAM, aplica_a=("FII",),
            limitacoes=("Percentual calculado e informado pelo administrador do fundo.",)),
    Metrica("fii.dy_informado_12m", "Dividend yield informado (12 m)", "Valuation", "%",
            "Soma dos percentuais mensais de dividend yield informados à CVM", GRAHAM, aplica_a=("FII",),
            limitacoes=("Percentual calculado pelo administrador; a base (cota patrimonial ou de mercado) "
                        "não é padronizada entre fundos. Não substitui o DY por proventos.",)),
)


def _metodo(id_: str, nome: str, grupo: str, unidade: str, formula: str, referencia: str, *,
            premissas: tuple[str, ...] = (), limitacoes: tuple[str, ...] = (),
            parametros: tuple[Parametro, ...] = (), aplica_a: tuple[str, ...] = ("ACAO",)) -> Metrica:
    return Metrica(id_, nome, grupo, unidade, formula, referencia, aplica_a, limitacoes, parametros, premissas,
                   exibir_no_ativo=id_ in NA_PAGINA_DO_ATIVO)


# Métodos já materializados por ativo (com parâmetros padrão) e exibidos na página do ativo.
NA_PAGINA_DO_ATIVO = {"graham.valor_intrinseco", "graham.margem_seguranca", "bazin.preco_teto", "lynch.peg",
                      "lynch.preco_justo", "greenblatt.earnings_yield", "greenblatt.retorno_capital"}


_YIELD_BAZIN = Parametro("yield_minimo", "Yield mínimo exigido (Taxa Bazin)", 0.06, 0.01, 0.30)
_FATOR_GRAHAM = Parametro("fator_graham", "Fator de Graham (Taxa Graham = P/L máx. × P/VP máx.)", 22.5, 1, 100)
_LIMITE_LYNCH = Parametro("limite_crescimento_atipico", "Crescimento acima do qual há aviso", 0.25, 0.05, 2.0)
_FATOR_LYNCH = Parametro("fator_lynch", "Multiplicador do P/L justo (Taxa Peter Lynch)", 1.0, 0.1, 5.0)
_RF = Parametro("taxa_livre_risco", "Taxa livre de risco anual", 0.10, 0.0, 0.5)

METODOS: tuple[Metrica, ...] = (
    # 6 — Graham
    _metodo("graham.valor_intrinseco", "Valor intrínseco de Graham", "Graham", "R$/ação", "√(fator × LPA × VPA)",
            GRAHAM, parametros=(_FATOR_GRAHAM,),
            premissas=("Fator 22,5 = P/L máximo de 15 × P/VP máximo de 1,5 aceitos pelo investidor defensivo.",
                       "LPA dos últimos 12 meses e VPA do último balanço."),
            limitacoes=("Indisponível com prejuízo ou patrimônio negativo.",
                        "Não considera crescimento nem qualidade dos lucros.")),
    _metodo("graham.valor_revisado", "Fórmula revisada de Graham", "Graham", "R$/ação",
            "LPA × (8,5 + 2g) × 4,4 ÷ Y (g e Y em pontos percentuais)", GRAHAM,
            premissas=("8,5 = P/L de uma empresa sem crescimento; 4,4 = rendimento dos títulos AAA na época do autor.",
                       "Y = Selic meta vigente (Banco Central), editável.",
                       "g = crescimento anual esperado do lucro (padrão: CAGR de 5 anos)."),
            limitacoes=("Muito sensível a g: crescimentos altos geram valores irreais.",)),
    _metodo("graham.margem_seguranca", "Margem de segurança", "Graham", "%", "(valor justo − preço) ÷ valor justo",
            GRAHAM, premissas=("Negativa quando a cotação está acima do valor justo calculado.",)),
    _metodo("graham.checklist_defensivo", "Checklist do investidor defensivo", "Graham", "un",
            "Número de critérios atendidos entre 7", GRAHAM,
            premissas=("Porte: receita anual ≥ R$ 2 bi.", "Liquidez corrente ≥ 2 e dívida de LP ≤ capital de giro.",
                       "Lucro positivo nos últimos 10 anos.", "Dividendos em todos os últimos 20 anos.",
                       "LPA (média de 3 anos) cresceu ≥ 33% em 10 anos.", "P/L sobre LPA médio de 3 anos ≤ 15.",
                       "P/VP ≤ 1,5, ou P/L × P/VP ≤ 22,5."),
            limitacoes=("Critério sem dados suficientes conta como não atendido e é marcado como indisponível.",)),
    # 5 — Bazin
    _metodo("bazin.preco_teto", "Preço teto de Bazin", "Bazin", "R$/ação", "Dividendo por ação ÷ yield mínimo",
            BAZIN, parametros=(_YIELD_BAZIN,),
            premissas=("Dividendo = proventos líquidos pagos nos últimos 12 meses (padrão) ou média anual de N anos.",
                       "JCP pelo valor líquido de IR; janela pela data de pagamento."),
            limitacoes=("Indisponível para empresas sem proventos.", "Proventos extraordinários inflam o teto.")),
    _metodo("bazin.criterios", "Critérios de Bazin", "Bazin", "un",
            "Endividamento baixo (DL/PL ≤ 1) e proventos em todos os últimos 5 anos", BAZIN,
            premissas=("Ambos os limites são parâmetros editáveis.",)),
    _metodo("bazin.preco_teto_projetivo", "Preço teto projetivo", "Bazin", "R$/ação",
            "(lucro projetado × payout ÷ ações) ÷ yield mínimo", BAZIN, parametros=(_YIELD_BAZIN,),
            premissas=("Lucro projetado e payout informados pelo usuário.",),
            limitacoes=("Resultado depende inteiramente das projeções do usuário.",)),
    # 7 — Lynch
    _metodo("lynch.peg", "PEG", "Lynch", "x", "P/L ÷ crescimento do lucro (em p.p.)", LYNCH,
            premissas=("PEG ≈ 1 indica preço compatível com o crescimento, pela regra prática do autor.",),
            limitacoes=("Indisponível com P/L ou crescimento não positivos.",)),
    _metodo("lynch.indice", "Índice de Lynch", "Lynch", "x", "(crescimento + dividend yield) ÷ P/L, em p.p.", LYNCH,
            premissas=("≥ 2: atraente; ≤ 1: pouco atraente (regra prática do autor).",)),
    _metodo("lynch.preco_justo", "Preço justo de Lynch", "Lynch", "R$/ação",
            "LPA × fator × crescimento (p.p.) — P/L justo igual ao crescimento", LYNCH,
            parametros=(_FATOR_LYNCH, _LIMITE_LYNCH),
            premissas=("Sem teto para o crescimento.",
                       "Aviso de crescimento atípico acima de 25% a.a. ou com lucro-base < 20% do atual ou negativo."),
            limitacoes=("Crescimento passado não garante crescimento futuro.",)),
    _metodo("lynch.categoria", "Categoria de Lynch", "Lynch", "un", "Uma das seis categorias, por regras explícitas",
            LYNCH,
            premissas=("1. Recuperação: último lucro ≤ 0 ou prejuízo em algum dos 3 anos anteriores.",
                       "2. Cíclica: setor cíclico ou lucros voláteis (coeficiente de variação > 0,5).",
                       "3. Ativos ocultos: P/VP < 1.", "4. Crescimento rápido: lucro cresce ≥ 20% a.a.",
                       "5. Robusta: crescimento entre 10% e 20% a.a.", "6. Crescimento lento: < 10% a.a."),
            limitacoes=("Regras objetivas simplificam o julgamento qualitativo do autor.",)),
    # 4 — Greenblatt
    _metodo("greenblatt.earnings_yield", "Earnings yield", "Greenblatt", "%", "EBIT ÷ EV", GREENBLATT,
            limitacoes=("Indisponível com EV ≤ 0.", LIMITACAO_FINANCEIRAS)),
    _metodo("greenblatt.retorno_capital", "Retorno sobre capital", "Greenblatt", "%",
            "EBIT ÷ (capital de giro líquido + imobilizado líquido)", GREENBLATT,
            premissas=("Capital de giro = (AC − caixa) − (PC − empréstimos de CP); negativo conta como zero.",),
            limitacoes=(LIMITACAO_FINANCEIRAS,)),
    _metodo("greenblatt.ranking", "Ranking da Fórmula Mágica", "Greenblatt", "un",
            "Soma das posições em earnings yield e retorno sobre capital (menor = melhor)", GREENBLATT,
            premissas=("Exclui financeiras e utilities por padrão; liquidez mínima configurável.",)),
    # 8 — DCF
    _metodo("dcf.fcff", "Fluxo de caixa livre da firma (FCFF)", "Fluxo de caixa descontado", "R$",
            "EBIT × (1 − t) + D&A − capex − Δ capital de giro", MCKINSEY,
            premissas=("Projeção de receita, margem, capex, D&A e capital de giro informada pelo usuário.",)),
    _metodo("dcf.fcfe", "Fluxo de caixa livre do acionista (FCFE)", "Fluxo de caixa descontado", "R$",
            "FCFF − juros × (1 − t) + nova dívida líquida", MCKINSEY),
    _metodo("dcf.wacc", "Custo médio ponderado de capital (WACC)", "Fluxo de caixa descontado", "%",
            "E/(D+E) × Ke + D/(D+E) × Kd × (1 − t)", MCKINSEY, premissas=("Pesos a valor de mercado.",)),
    _metodo("dcf.valor", "Valor por DCF", "Fluxo de caixa descontado", "R$/ação",
            "Σ FC_t ÷ (1+r)^t + [FC_n × (1+g) ÷ (r − g)] ÷ (1+r)^n − dívida líquida, ÷ ações", MCKINSEY,
            premissas=("Fluxos no fim de cada ano.", "FCFF descontado pelo WACC; FCFE pelo custo do capital próprio."),
            limitacoes=("Exige r > g.", "O valor terminal costuma responder pela maior parte do resultado.")),
    # 9 — Damodaran
    _metodo("damodaran.custo_capital_proprio", "Custo do capital próprio", "Damodaran", "%",
            "rf + β × ERP + λ × prêmio de risco país", DAMODARAN,
            premissas=("ERP, risco país e betas setoriais dos datasets públicos do Damodaran, com data de referência.",
                       "Conversão US$ → R$ pelo diferencial de inflação."),
            limitacoes=("Beta setorial dos EUA/emergentes, realavancado pela estrutura de capital da empresa.",)),
    _metodo("damodaran.gordon", "Modelo de Gordon (dividendos)", "Damodaran", "R$/ação", "D0 × (1 + g) ÷ (Ke − g)",
            DAMODARAN, limitacoes=("Exige Ke > g e dividendos positivos.",)),
    _metodo("damodaran.ddm_dois_estagios", "Desconto de dividendos em dois estágios", "Damodaran", "R$/ação",
            "Σ D0(1+g1)^t ÷ (1+Ke)^t + [D_n(1+g2) ÷ (Ke − g2)] ÷ (1+Ke)^n", DAMODARAN),
    _metodo("damodaran.multiplos_setor", "Valuation relativa (múltiplos do setor)", "Damodaran", "R$/ação",
            "Mediana do múltiplo dos pares × métrica por ação da empresa", DAMODARAN,
            premissas=("Mínimo de 3 pares com múltiplo positivo.",),
            limitacoes=("Supõe que o setor, em média, está corretamente precificado.",)),
    _metodo("damodaran.narrativa", "Narrativa → números", "Damodaran", "un",
            "Cada premissa numérica exige uma justificativa escrita", DAMODARAN),
    # 1 — Siegel
    _metodo("siegel.retorno_real", "Retorno real", "Siegel", "%", "(1 + nominal) ÷ (1 + inflação) − 1", SIEGEL,
            aplica_a=("ACAO", "FII", "CARTEIRA")),
    _metodo("siegel.retorno_total", "Retorno com dividendos reinvestidos", "Siegel", "x",
            "I_t = I_{t−1} × (P_t + D_t) ÷ P_{t−1}", SIEGEL, aplica_a=("ACAO", "FII")),
    _metodo("siegel.cape", "CAPE (P/L de Shiller)", "Siegel", "x", "Preço ÷ média do LPA real dos últimos 10 anos",
            SIEGEL, premissas=("LPA corrigido pelo IPCA para a moeda de hoje.",),
            limitacoes=("Exige 10 anos de lucros.",)),
    _metodo("siegel.reversao_media", "Reversão à média do P/L", "Siegel", "x",
            "(P/L atual − média histórica) ÷ desvio-padrão", SIEGEL),
    _metodo("siegel.premio_risco", "Prêmio de risco das ações", "Siegel", "%", "1 ÷ CAPE − juro real", SIEGEL,
            premissas=("Juro real de referência: NTN-B (Tesouro IPCA+) longa.",)),
    # 3 — Bogle
    _metodo("bogle.impacto_custos", "Impacto dos custos", "Bogle", "%",
            "1 − patrimônio final com custos ÷ patrimônio final sem custos", BOGLE,
            premissas=("Retorno líquido anual = (1 + r) × (1 − custo) − 1; aportes no fim de cada ano.",),
            aplica_a=("FII", "ETF", "CARTEIRA")),
    _metodo("bogle.decomposicao", "Decomposição do retorno esperado", "Bogle", "%",
            "Dividend yield + crescimento do lucro + variação anual do P/L", BOGLE),
    # 2 — Lo & Foerster
    _metodo("portfolio.sharpe", "Índice de Sharpe", "Portfólio", "x", "(retorno − rf) ÷ volatilidade", LO_FOERSTER,
            parametros=(_RF,), aplica_a=("CARTEIRA",)),
    _metodo("portfolio.beta", "Beta (CAPM)", "Portfólio", "x", "cov(ativo, mercado) ÷ var(mercado)", LO_FOERSTER,
            premissas=("Retornos diários alinhados com o índice de mercado.",)),
    _metodo("portfolio.fronteira", "Fronteira eficiente de Markowitz", "Portfólio", "un",
            "Mínima variância para cada retorno-alvo, pesos ≥ 0 somando 100%", LO_FOERSTER, aplica_a=("CARTEIRA",),
            limitacoes=("Muito sensível às médias históricas estimadas.",)),
    _metodo("portfolio.fatores", "Fatores (valor, tamanho, momento)", "Portfólio", "%",
            "Percentil de earnings yield, valor de mercado e retorno de 12−1 meses", LO_FOERSTER),
    # 10 — Dalio
    _metodo("dalio.correlacao", "Matriz de correlação", "Dalio", "x", "Correlação de Pearson dos retornos",
            DALIO, aplica_a=("CARTEIRA",)),
    _metodo("dalio.paridade_risco", "Paridade de risco", "Dalio", "%",
            "Pesos com contribuições de risco iguais: w_i × (Σw)_i ÷ wᵀΣw = 1/n", DALIO, aplica_a=("CARTEIRA",)),
    _metodo("dalio.all_weather", "Alocação All Weather", "Dalio", "%",
            "30% ações, 40% títulos longos, 15% intermediários, 7,5% ouro, 7,5% commodities", DALIO,
            aplica_a=("CARTEIRA",), premissas=("Pesos de referência editáveis.",)),
    # FII — Gordon ajustado
    _metodo("fii.gordon_ajustado", "Preço teto por Gordon ajustado", "Valuation", "R$/ação",
            "D12m × (1 + g) ÷ (taxa do Tesouro × (1 − IR) + prêmio − g)", DAMODARAN, aplica_a=("FII",),
            premissas=("Rendimentos de FII são isentos para a pessoa física; o Tesouro paga IR (15% acima de 2 anos).",
                       "Opção de usar a taxa bruta do Tesouro."),
            limitacoes=("Exige taxa exigida > crescimento.",)),
)

TODAS: tuple[Metrica, ...] = METRICAS + METODOS
POR_ID: dict[str, Metrica] = {m.id: m for m in TODAS}
