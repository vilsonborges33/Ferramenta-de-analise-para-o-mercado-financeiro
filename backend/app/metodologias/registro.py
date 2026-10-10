"""Registro único das métricas (DECISOES.md D-006).

Alimenta a página "Como é calculado", a validação de parâmetros da API e o job de recálculo.
"""

from dataclasses import asdict, dataclass, field

DAMODARAN = "Valuation — Aswath Damodaran"
GRAHAM = "O Investidor Inteligente — Benjamin Graham"

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
    versao: str = "1"

    def como_dict(self) -> dict:
        return asdict(self)


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
            "Proventos brutos por ação com data-com nos últimos 12 meses ÷ cotação", GRAHAM,
            aplica_a=("ACAO", "FII"),
            limitacoes=("Depende da ingestão de proventos (plano pago da brapi).",)),
    Metrica("basico.payout", "Payout", "Valuation", "%", "Proventos por ação (12 m) ÷ LPA (12 m)", GRAHAM,
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
            "Média do volume financeiro dos pregões dos últimos 2 meses", GRAHAM, aplica_a=("ACAO", "FII")),
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

POR_ID: dict[str, Metrica] = {m.id: m for m in METRICAS}
