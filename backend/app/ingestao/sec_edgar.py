"""SEC EDGAR (EUA): fundamentos de empresas americanas e REITs pelos dados XBRL ("companyfacts").

Fontes (governo dos EUA, sem chave; limite de 10 requisições/s e User-Agent com contato obrigatório):
- https://www.sec.gov/files/company_tickers.json — ticker → CIK
- https://data.sec.gov/submissions/CIK##########.json — nome, código SIC (setor) e bolsa
- https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json — valores reportados em 10-K e 10-Q

Os conceitos US-GAAP são levados para os mesmos campos padronizados usados com a CVM, para que os
indicadores e métodos dos livros funcionem sem mudança. Anual = fatos de ~12 meses do 10-K; 12 meses (TTM) =
último anual + acumulado do ano corrente − acumulado do mesmo período do ano anterior (10-Q).
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert

from app.config import obter_configuracao
from app.db.modelos import Ativo, ComposicaoCapital, DemonstracaoPadronizada, Empresa
from app.ingestao.base import Contexto, EsquemaInesperado, lote

log = logging.getLogger(__name__)

URL_TICKERS = "https://www.sec.gov/files/company_tickers.json"
URL_SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik}.json"
URL_FACTS = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
SIC_REIT = {"6798"}
SIC_BANCO = {"6021", "6022", "6029", "6035", "6036", "6111", "6141", "6153", "6159", "6162", "6172", "6199",
             "6200", "6211"}
SIC_SEGURADORA = {"6311", "6321", "6324", "6331", "6351", "6361", "6399", "6411"}

# campo padronizado → conceitos US-GAAP em ordem de preferência (o primeiro com valor no período vence)
FLUXO: dict[str, tuple[str, ...]] = {
    "receita_liquida": ("Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax",
                        "RevenueFromContractWithCustomerIncludingAssessedTax", "SalesRevenueNet",
                        "RevenuesNetOfInterestExpense", "OperatingLeasesIncomeStatementLeaseRevenue"),
    "lucro_bruto": ("GrossProfit",),
    "ebit": ("OperatingIncomeLoss",),
    "lucro_liquido": ("ProfitLoss", "NetIncomeLoss"),
    "lucro_liquido_controladores": ("NetIncomeLoss", "NetIncomeLossAvailableToCommonStockholdersBasic"),
    "depreciacao_amortizacao": ("DepreciationDepletionAndAmortization", "DepreciationAndAmortization",
                                "DepreciationAmortizationAndAccretionNet", "Depreciation"),
    "capex": ("PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets",
              "PaymentsToAcquireRealEstate", "PaymentsForCapitalImprovements"),
    "fco": ("NetCashProvidedByUsedInOperatingActivities",),
    "dividendos_pagos": ("PaymentsOfDividendsCommonStock", "PaymentsOfDividends"),
    "capex_manutencao": ("PaymentsForCapitalImprovements",),
    "ganho_venda_imoveis": ("GainLossOnSaleOfRealEstateInvestmentProperty", "GainsLossesOnSalesOfInvestmentRealEstate",
                            "GainLossOnDispositionOfAssets1", "GainLossOnSaleOfPropertyPlantEquipment"),
}
SALDO: dict[str, tuple[str, ...]] = {
    "ativo_total": ("Assets",),
    "ativo_circulante": ("AssetsCurrent",),
    "passivo_circulante": ("LiabilitiesCurrent",),
    "patrimonio_liquido": ("StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
                           "StockholdersEquity"),
    "patrimonio_liquido_controladores": ("StockholdersEquity",),
    "caixa_equivalentes": ("CashAndCashEquivalentsAtCarryingValue",
                           "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents", "Cash"),
    "aplicacoes_financeiras": ("ShortTermInvestments", "MarketableSecuritiesCurrent",
                               "AvailableForSaleSecuritiesDebtSecuritiesCurrent"),
    "emprestimos_cp": ("DebtCurrent", "LongTermDebtCurrent", "ShortTermBorrowings", "CommercialPaper"),
    "emprestimos_lp": ("LongTermDebtNoncurrent", "LongTermDebt", "SeniorNotes", "UnsecuredDebt", "NotesPayable"),
    "imobilizado": ("PropertyPlantAndEquipmentNet", "RealEstateInvestmentPropertyNet"),
    "participacao_nao_controladores": ("MinorityInterest",),
}
NEGATIVOS = {"capex", "dividendos_pagos", "capex_manutencao"}  # saídas de caixa: mesmo sinal da DFC da CVM


@dataclass
class Fato:
    inicio: date | None
    fim: date
    valor: float
    form: str
    arquivado: str
    accn: str

    @property
    def dias(self) -> int:
        return (self.fim - self.inicio).days if self.inicio else 0


@dataclass
class Periodo:
    periodo: str
    tipo: str  # ano | ttm
    inicio: date | None
    fim: date
    campos: dict[str, float] = field(default_factory=dict)
    insumos: dict[str, list[dict]] = field(default_factory=dict)


def _data(texto: str | None) -> date | None:
    return date.fromisoformat(texto) if texto else None


def fatos(companyfacts: dict, conceito: str, taxonomia: str = "us-gaap") -> list[Fato]:
    unidades = companyfacts.get("facts", {}).get(taxonomia, {}).get(conceito, {}).get("units", {})
    lista = unidades.get("USD") or unidades.get("shares") or next(iter(unidades.values()), [])
    saida = []
    for f in lista:
        fim = _data(f.get("end"))
        if fim is None or f.get("val") is None:
            continue
        saida.append(Fato(_data(f.get("start")), fim, float(f["val"]), f.get("form", ""), f.get("filed", ""),
                          f.get("accn", "")))
    return saida


def _ultimo_por_chave(lista: list[Fato]) -> dict[tuple, Fato]:
    """Para cada (início, fim), o fato arquivado por último (refaz reapresentações)."""
    saida: dict[tuple, Fato] = {}
    for f in sorted(lista, key=lambda f: f.arquivado):
        saida[(f.inicio, f.fim)] = f
    return saida


def _anual(lista: list[Fato]) -> dict[date, Fato]:
    return {k[1]: f for k, f in _ultimo_por_chave(lista).items() if f.inicio and 340 <= f.dias <= 390}


def _ytd(lista: list[Fato]) -> dict[tuple[date, date], Fato]:
    """Acumulados do ano (3, 6 ou 9 meses) dos 10-Q, por (início, fim)."""
    return {k: f for k, f in _ultimo_por_chave(lista).items() if f.inicio and 80 <= f.dias <= 290}


def _instantes(lista: list[Fato]) -> dict[date, Fato]:
    return {k[1]: f for k, f in _ultimo_por_chave(lista).items() if f.inicio is None}


def _origem(conceito: str, f: Fato, **extra) -> dict:
    return {"conceito": conceito, "form": f.form, "accn": f.accn, "inicio": f.inicio.isoformat() if f.inicio else None,
            "fim": f.fim.isoformat(), "valor": f.valor, **extra}


def padronizar(companyfacts: dict, anos: int = 7) -> list[Periodo]:
    """Períodos anuais (últimos `anos`) e um período de 12 meses (TTM) com os campos padronizados."""
    por_conceito = {c: fatos(companyfacts, c) for cs in (*FLUXO.values(), *SALDO.values()) for c in cs}
    fins_anuais = sorted({fim for cs in FLUXO.values() for c in cs for fim in _anual(por_conceito[c])})
    fins_anuais = [f for f in fins_anuais if any(f in _anual(por_conceito[c]) for c in FLUXO["receita_liquida"])
                   or any(f in _anual(por_conceito[c]) for c in FLUXO["lucro_liquido_controladores"])][-anos:]
    periodos: list[Periodo] = []

    def saldos(p: Periodo, fim: date) -> None:
        for campo, conceitos in SALDO.items():
            for c in conceitos:
                inst = _instantes(por_conceito[c])
                if fim in inst:
                    p.campos[campo] = inst[fim].valor
                    p.insumos[campo] = [_origem(c, inst[fim])]
                    break

    for fim in fins_anuais:
        p = Periodo(f"{fim.year}-A", "ano", None, fim)
        for campo, conceitos in FLUXO.items():
            for c in conceitos:
                anual = _anual(por_conceito[c])
                if fim in anual:
                    f = anual[fim]
                    p.inicio = p.inicio or f.inicio
                    p.campos[campo] = -abs(f.valor) if campo in NEGATIVOS else f.valor
                    p.insumos[campo] = [_origem(c, f)]
                    break
        saldos(p, fim)
        periodos.append(p)
    if not periodos:
        return []

    # 12 meses: último anual + acumulado do ano corrente − acumulado equivalente do ano anterior
    ultimo = periodos[-1]
    fim_ttm = ultimo.fim
    ytd_por_campo: dict[str, tuple[str, Fato, Fato]] = {}
    for campo, conceitos in FLUXO.items():
        for c in conceitos:
            ytd = _ytd(por_conceito[c])
            depois = [f for (ini, fim), f in ytd.items() if fim > ultimo.fim and ini >= ultimo.fim]
            if not depois:
                continue
            atual = max(depois, key=lambda f: f.fim)
            anterior = next((f for (ini, fim), f in ytd.items()
                             if abs((fim - atual.fim).days + 365) <= 7 and abs(f.dias - atual.dias) <= 7), None)
            if anterior is not None:
                ytd_por_campo[campo] = (c, atual, anterior)
                break
    if ytd_por_campo:
        fim_ttm = max(a.fim for _, a, _ in ytd_por_campo.values())
        ytd_por_campo = {k: v for k, v in ytd_por_campo.items() if v[1].fim == fim_ttm}
    ttm = Periodo(f"{fim_ttm.year}-T{(fim_ttm.month - 1) // 3 + 1}", "ttm", None, fim_ttm)
    for campo in FLUXO:
        if campo not in ultimo.campos:
            continue
        if campo in ytd_por_campo:
            c, atual, anterior = ytd_por_campo[campo]
            valor = ultimo.campos[campo] + (abs(atual.valor) - abs(anterior.valor) if campo in NEGATIVOS
                                            else atual.valor - anterior.valor) * (-1 if campo in NEGATIVOS else 1)
            ttm.campos[campo] = valor
            ttm.insumos[campo] = ultimo.insumos[campo] + [_origem(c, atual, soma=True),
                                                          _origem(c, anterior, subtraido=True)]
        elif fim_ttm == ultimo.fim:
            ttm.campos[campo] = ultimo.campos[campo]
            ttm.insumos[campo] = ultimo.insumos[campo]
    saldos(ttm, fim_ttm)
    if not any(k in ttm.campos for k in SALDO):  # balanço do 10-Q ausente: usa o do anual
        for k in SALDO:
            if k in ultimo.campos:
                ttm.campos[k], ttm.insumos[k] = ultimo.campos[k], ultimo.insumos[k]
    ttm.inicio = date(fim_ttm.year - 1, fim_ttm.month, 1)
    periodos.append(ttm)
    for p in periodos:
        if "lucro_liquido_controladores" not in p.campos and "lucro_liquido" in p.campos:
            p.campos["lucro_liquido_controladores"] = p.campos["lucro_liquido"]
        if "patrimonio_liquido_controladores" not in p.campos and "patrimonio_liquido" in p.campos:
            p.campos["patrimonio_liquido_controladores"] = p.campos["patrimonio_liquido"]
        if "ativo_total" in p.campos and "patrimonio_liquido" in p.campos:
            p.campos["passivo_total"] = p.campos["ativo_total"] - p.campos["patrimonio_liquido"]
    return periodos


def acoes_em_circulacao(companyfacts: dict) -> tuple[float, date, dict] | None:
    """Ações em circulação na capa do último relatório (soma das classes); senão, média diluída do último ano."""
    capa = fatos(companyfacts, "EntityCommonStockSharesOutstanding", "dei")
    if capa:
        recente = max(capa, key=lambda f: (f.arquivado, f.fim))
        mesmas = [f for f in capa if f.accn == recente.accn and f.fim == recente.fim]
        return sum(f.valor for f in mesmas), recente.fim, _origem("dei:EntityCommonStockSharesOutstanding", recente,
                                                                  classes=len(mesmas))
    diluidas = _anual(fatos(companyfacts, "WeightedAverageNumberOfDilutedSharesOutstanding"))
    if diluidas:
        fim = max(diluidas)
        return diluidas[fim].valor, fim, _origem("WeightedAverageNumberOfDilutedSharesOutstanding", diluidas[fim])
    return None


def classificar(sic: str | None) -> tuple[str, str]:
    """(classe do ativo, tipo do plano de contas) pelo código SIC."""
    sic = str(sic or "")
    if sic in SIC_REIT:
        return "REIT", "geral"
    if sic in SIC_BANCO:
        return "STOCK", "banco"
    if sic in SIC_SEGURADORA:
        return "STOCK", "seguradora"
    return "STOCK", "geral"


def cabecalhos() -> dict[str, str]:
    contato = obter_configuracao().contato_user_agent
    if "@" not in contato or "exemplo.com" in contato:  # vazio ou ainda o texto de exemplo do .env.example
        raise EsquemaInesperado("a SEC exige um contato: defina CONTATO_USER_AGENT no arquivo .env, por exemplo "
                                "\"analise-mercado seu-email@exemplo.com\"")
    return {"User-Agent": contato, "Accept-Encoding": "gzip, deflate"}


def gravar(ctx: Contexto, ticker: str, cik: str, submissions: dict, companyfacts: dict) -> int:
    sessao = ctx.sessao
    classe, plano = classificar(submissions.get("sic"))
    nome = submissions.get("name") or companyfacts.get("entityName") or ticker
    hoje = date.today()
    valores = {"nome": nome[:300], "cik": cik, "pais": "US", "setor": (submissions.get("sicDescription") or None),
               "tipo_plano_contas": plano, **ctx.procedencia(hoje)}
    stmt = insert(Empresa).values(**valores)
    sessao.execute(stmt.on_conflict_do_update(index_elements=["cik"],
                                              set_={k: stmt.excluded[k] for k in valores if k != "cik"}))
    empresa_id = sessao.scalar(select(Empresa.id).where(Empresa.cik == cik))
    ativo = sessao.scalar(select(Ativo).where(Ativo.ticker == ticker))
    if ativo is None:
        sessao.add(Ativo(ticker=ticker, empresa_id=empresa_id, classe=classe, especie="ON", mercado="US", moeda="USD"))
    else:
        ativo.empresa_id, ativo.classe, ativo.especie = empresa_id, classe, "ON"
        ativo.mercado, ativo.moeda = "US", "USD"
    periodos = padronizar(companyfacts)
    sessao.execute(delete(DemonstracaoPadronizada).where(DemonstracaoPadronizada.empresa_id == empresa_id))
    for p in periodos:
        sessao.add(DemonstracaoPadronizada(
            empresa_id=empresa_id, periodo=p.periodo, tipo_periodo=p.tipo, data_inicio=p.inicio, data_fim=p.fim,
            consolidado=True, versao_usada=1, campos=p.campos, insumos=p.insumos, **ctx.procedencia(p.fim)))
    acoes = acoes_em_circulacao(companyfacts)
    if acoes:
        quantidade, data_ref, _ = acoes
        valores = {"empresa_id": empresa_id, "acoes_ordinarias": quantidade, "acoes_preferenciais": 0,
                   "acoes_tesouraria_on": 0, "acoes_tesouraria_pn": 0, **ctx.procedencia(data_ref)}
        stmt = insert(ComposicaoCapital).values(**valores)
        sessao.execute(stmt.on_conflict_do_update(
            index_elements=["empresa_id", "data_referencia"],
            set_={k: stmt.excluded[k] for k in valores if k not in ("empresa_id", "data_referencia")}))
    return len(periodos)


def garantir_etfs(sessao, etfs: list[str]) -> int:
    """ETFs não têm balanço na SEC: entram só como ativos (cotação, dividendos e análise de custos de Bogle)."""
    novos = 0
    for t in etfs:
        if sessao.scalar(select(Ativo.id).where(Ativo.ticker == t)) is None:
            sessao.add(Ativo(ticker=t, classe="ETF", mercado="US", moeda="USD"))
            novos += 1
    sessao.commit()
    return novos


def ingerir(sessao, tickers: list[str] | None = None, cliente=None, pausa: float = 0.15) -> int:
    from app.ingestao.base import cliente_http

    cfg = obter_configuracao()
    tickers = [t.upper() for t in (tickers or cfg.lista_tickers_eua)]
    garantir_etfs(sessao, cfg.lista_etfs_eua)
    proprio = cliente is None
    cliente = cliente or cliente_http()
    total, falhas = 0, []
    try:
        with lote(sessao, "SEC_EDGAR", URL_FACTS.format(cik="*")) as ctx:
            cab = cabecalhos()
            resposta = cliente.get(URL_TICKERS, headers=cab)
            resposta.raise_for_status()
            mapa = {v["ticker"].upper(): str(v["cik_str"]).zfill(10) for v in resposta.json().values()}
            for ticker in tickers:
                cik = mapa.get(ticker) or mapa.get(ticker.replace("-", "."))
                if cik is None:
                    falhas.append(f"{ticker}: não encontrado na SEC")
                    continue
                try:
                    time.sleep(pausa)
                    sub = cliente.get(URL_SUBMISSIONS.format(cik=cik), headers=cab)
                    sub.raise_for_status()
                    time.sleep(pausa)
                    fac = cliente.get(URL_FACTS.format(cik=cik), headers=cab)
                    fac.raise_for_status()
                    with sessao.begin_nested():
                        total += gravar(ctx, ticker, cik, sub.json(), fac.json())
                    sessao.commit()
                except Exception as erro:  # uma empresa com problema não impede as outras
                    falhas.append(f"{ticker}: {erro!r}"[:150])
            ctx.lote.linhas_gravadas = total
            ctx.lote.erro = f"{len(falhas)} com falha (ex.: {'; '.join(falhas[:3])})" if falhas else None
    finally:
        if proprio:
            cliente.close()
    log.info("SEC EDGAR: %s períodos; %s falhas", total, len(falhas))
    return total
