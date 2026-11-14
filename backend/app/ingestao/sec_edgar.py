"""SEC EDGAR (EUA): fundamentos de empresas americanas e REITs pelos dados XBRL ("companyfacts").

Fontes (governo dos EUA, sem chave; limite de 10 requisições/s e User-Agent com contato obrigatório):
- https://www.sec.gov/files/company_tickers.json — ticker → CIK
- https://data.sec.gov/submissions/CIK##########.json — nome, código SIC (setor) e bolsa
- https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json — valores reportados em 10-K e 10-Q

Os conceitos US-GAAP são levados para os mesmos campos padronizados usados com a CVM, para que os
indicadores e métodos dos livros funcionem sem mudança. Anual = fatos de ~12 meses do 10-K; 12 meses (TTM) =
último anual + acumulado do ano corrente − acumulado do mesmo período do ano anterior (10-Q).
"""

import json
import logging
import time
import zipfile
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

import httpx
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert

from app.config import obter_configuracao
from app.db.modelos import Ativo, ComposicaoCapital, DemonstracaoPadronizada, Empresa
from app.ingestao.base import Contexto, EsquemaInesperado, lote

log = logging.getLogger(__name__)

URL_TICKERS = "https://www.sec.gov/files/company_tickers.json"
URL_SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik}.json"
URL_FACTS = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
# Universo completo (D-044): tickers por bolsa, pacote diário com os companyfacts de todos os emissores e índice
# diário de documentos arquivados (para recarregar só quem entregou 10-K/10-Q novo).
URL_TICKERS_BOLSA = "https://www.sec.gov/files/company_tickers_exchange.json"
URL_FACTS_ZIP = "https://www.sec.gov/Archives/edgar/daily-index/xbrl/companyfacts.zip"
URL_INDICE_DIARIO = "https://www.sec.gov/Archives/edgar/daily-index/{ano}/QTR{tri}/form.{dia:%Y%m%d}.idx"
BOLSAS = {"NYSE", "Nasdaq", "CBOE"}  # fora: balcão (OTC) e emissores sem bolsa
FORMULARIOS_BALANCO = {"10-K", "10-K/A", "10-Q", "10-Q/A", "10-KT", "10-KT/A"}
# Emissores estrangeiros (ADRs): o balanço e as "ações" do 20-F/40-F não têm a mesma base do papel negociado
# nos EUA (ADS com razão própria), então ficam sem indicadores em vez de mostrar P/L errado.
FORMULARIOS_ESTRANGEIROS = {"20-F", "20-F/A", "40-F", "40-F/A", "6-K"}
TENTATIVAS_DOWNLOAD = 3
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
        if fim is None or f.get("val") is None or f.get("form", "") in FORMULARIOS_ESTRANGEIROS:
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


def padronizar(companyfacts: dict, anos: int = 11) -> list[Periodo]:
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
    """Cabeçalhos das requisições à SEC. O contato vem de CONTATO_SEC (só a SEC o recebe); por compatibilidade,
    aceita o CONTATO_USER_AGENT de instalações antigas quando ele já tem um e-mail."""
    cfg = obter_configuracao()
    contato = next((c for c in (cfg.contato_sec, cfg.contato_user_agent) if "@" in c and "exemplo.com" not in c), "")
    if not contato:  # vazio ou ainda o texto de exemplo do .env.example
        raise EsquemaInesperado("a SEC exige um contato: defina CONTATO_SEC no arquivo .env, por exemplo "
                                "\"analise-mercado seu-email@exemplo.com\"")
    return {"User-Agent": contato, "Accept-Encoding": "gzip, deflate"}


def _empresa(ctx: Contexto, cik: str, nome: str, submissions: dict | None) -> tuple[int, str]:
    """Grava/atualiza o emissor e devolve (id, classe do ativo). Sem `submissions`, mantém setor e tipo já gravados."""
    sessao = ctx.sessao
    existente = sessao.scalar(select(Empresa).where(Empresa.cik == cik))
    if submissions is None and existente is not None:
        classe = sessao.scalar(select(Ativo.classe).where(Ativo.empresa_id == existente.id).limit(1)) or "STOCK"
        return existente.id, classe
    classe, plano = classificar((submissions or {}).get("sic"))
    valores = {"nome": ((submissions or {}).get("name") or nome)[:300], "cik": cik, "pais": "US",
               "setor": (submissions or {}).get("sicDescription") or None, "tipo_plano_contas": plano,
               **ctx.procedencia(date.today())}
    stmt = insert(Empresa).values(**valores)
    sessao.execute(stmt.on_conflict_do_update(index_elements=["cik"],
                                              set_={k: stmt.excluded[k] for k in valores if k != "cik"}))
    return sessao.scalar(select(Empresa.id).where(Empresa.cik == cik)), classe


def gravar(ctx: Contexto, ticker: str, cik: str, submissions: dict | None, companyfacts: dict) -> int:
    sessao = ctx.sessao
    empresa_id, classe = _empresa(ctx, cik, companyfacts.get("entityName") or ticker, submissions)
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


def universo(dados: dict) -> dict[str, tuple[str, str]]:
    """CIK → (ticker, nome) das empresas listadas em bolsa, a partir de `company_tickers_exchange.json`.

    Um ticker por empresa (o primeiro que a SEC lista): classes com preços muito diferentes (BRK-A × BRK-B)
    dariam valor de mercado errado com a soma das ações da capa.
    """
    campos = dados.get("fields") or []
    if not {"cik", "ticker", "exchange"} <= set(campos):
        raise EsquemaInesperado(f"company_tickers_exchange.json mudou de formato: {campos}")
    i = {c: campos.index(c) for c in campos}
    saida: dict[str, tuple[str, str]] = {}
    for linha in dados.get("data", []):
        ticker, bolsa = linha[i["ticker"]], linha[i["exchange"]]
        if not ticker or bolsa not in BOLSAS:
            continue
        cik = str(linha[i["cik"]]).zfill(10)
        saida.setdefault(cik, (str(ticker).upper().replace(".", "-"), str(linha[i.get("name", 1)] or ticker)))
    return saida


def ciks_do_indice(texto: str) -> set[str]:
    """CIKs com 10-K/10-Q no índice diário (`form.AAAAMMDD.idx`): colunas tipo, empresa, CIK, data, arquivo."""
    ciks = set()
    for linha in texto.splitlines():
        partes = linha.split()
        if len(partes) >= 5 and partes[0] in FORMULARIOS_BALANCO and partes[-3].isdigit():
            ciks.add(partes[-3].zfill(10))
    return ciks


def _baixar_sec(cliente, url: str, cab: dict) -> Path:
    """Baixa um arquivo da SEC para `dados_brutos/SEC_EDGAR/<data>/` (com o contato no cabeçalho)."""
    destino = obter_configuracao().diretorio_dados_brutos / "SEC_EDGAR" / date.today().isoformat()
    destino.mkdir(parents=True, exist_ok=True)
    arquivo = destino / url.rsplit("/", 1)[-1]
    if arquivo.exists() and arquivo.stat().st_size > 0:  # já baixado hoje (ex.: carga retomada)
        return arquivo
    parcial = arquivo.with_suffix(arquivo.suffix + ".parcial")  # interrompido no meio não passa por completo
    for tentativa in range(1, TENTATIVAS_DOWNLOAD + 1):
        ja = parcial.stat().st_size if parcial.exists() else 0
        log.info("baixando %s (a partir de %s bytes, tentativa %s)", url, ja, tentativa)
        try:
            # Arquivo grande (~1,3 GB): uma queda no meio continua de onde parou (Range), em vez de recomeçar.
            with cliente.stream("GET", url, headers={**cab, **({"Range": f"bytes={ja}-"} if ja else {})}) as resposta:
                if resposta.status_code == 416:  # já estava completo
                    break
                resposta.raise_for_status()
                modo = "ab" if ja and resposta.status_code == 206 else "wb"
                with parcial.open(modo) as saida:
                    for bloco in resposta.iter_bytes():
                        saida.write(bloco)
            break
        except httpx.TransportError:
            if tentativa == TENTATIVAS_DOWNLOAD:
                raise
            time.sleep(5 * tentativa)
    parcial.replace(arquivo)
    return arquivo


def _completar_setores(ctx: Contexto, cliente, cab: dict, pausa: float, limite: int | None = None) -> int:
    """Setor (SIC) e tipo de cada emissor novo: um pedido de `submissions` por empresa, só na primeira vez."""
    sessao = ctx.sessao
    pendentes = list(sessao.execute(select(Empresa.cik, Ativo.ticker).join(Ativo, Ativo.empresa_id == Empresa.id)
                                    .where(Empresa.pais == "US", Empresa.setor.is_(None), Ativo.ativo.is_(True))
                                    .limit(limite)))
    feitos = 0
    for cik, ticker in pendentes:
        try:
            time.sleep(pausa)
            sub = cliente.get(URL_SUBMISSIONS.format(cik=cik), headers=cab)
            sub.raise_for_status()
            dados = sub.json()
            classe, _ = classificar(dados.get("sic"))
            _empresa(ctx, cik, ticker, dados)
            sessao.execute(Ativo.__table__.update().where(Ativo.ticker == ticker).values(classe=classe))
            feitos += 1
            if feitos % 200 == 0:
                sessao.commit()
        except Exception as erro:  # noqa: BLE001 — sem setor a empresa segue como ação comum
            log.warning("setor de %s indisponível: %r", ticker, erro)
    sessao.commit()
    return feitos


def _registrar_universo(ctx: Contexto, emissores: dict[str, tuple[str, str]]) -> None:
    """Cria emissor e ativo de cada empresa listada (as cotações não esperam o balanço); desativa quem saiu da bolsa."""
    sessao = ctx.sessao
    hoje = date.today()
    ja = {cik for (cik,) in sessao.execute(select(Empresa.cik).where(Empresa.pais == "US"))}
    novos = [{"nome": nome[:300], "cik": cik, "pais": "US", "tipo_plano_contas": "geral", **ctx.procedencia(hoje)}
             for cik, (_, nome) in emissores.items() if cik not in ja]
    for i in range(0, len(novos), 500):
        sessao.execute(insert(Empresa).on_conflict_do_nothing(), novos[i:i + 500])
    ids = dict(sessao.execute(select(Empresa.cik, Empresa.id).where(Empresa.pais == "US")).all())
    existentes = {t: a for t, a in sessao.execute(select(Ativo.ticker, Ativo).where(Ativo.mercado == "US")).all()}
    outros = set(sessao.scalars(select(Ativo.ticker).where(Ativo.mercado != "US")))  # tickers da B3: não colidem
    listados = set()
    for cik, (ticker, _) in emissores.items():
        listados.add(ticker)
        ativo = existentes.get(ticker)
        if ticker in outros:
            continue
        if ativo is None:
            sessao.add(Ativo(ticker=ticker, empresa_id=ids[cik], classe="STOCK", especie="ON", mercado="US",
                             moeda="USD"))
        elif ativo.classe != "ETF":
            ativo.empresa_id, ativo.ativo = ids[cik], True
    for ticker, ativo in existentes.items():
        if ativo.classe in ("STOCK", "REIT") and ticker not in listados:
            ativo.ativo = False
    sessao.commit()


def _zip_integro(caminho: Path) -> bool:
    """Confere o CRC de todos os arquivos do zip (alguns segundos para ~1 GB)."""
    try:
        with zipfile.ZipFile(caminho) as z:
            return z.testzip() is None
    except (zipfile.BadZipFile, OSError):
        return False


def _fundamentos_em_lote(ctx: Contexto, cliente, cab: dict, emissores: dict[str, tuple[str, str]],
                         falhas: list[str]) -> int:
    """Primeira carga: todos os companyfacts num só arquivo (~1 GB) em vez de milhares de pedidos."""
    total = 0
    caminho = _baixar_sec(cliente, URL_FACTS_ZIP, cab)
    if not _zip_integro(caminho):  # download retomado que corrompeu o arquivo: baixa de novo do zero
        log.warning("pacote da SEC corrompido; baixando de novo")
        caminho.unlink()
        caminho = _baixar_sec(cliente, URL_FACTS_ZIP, cab)
        if not _zip_integro(caminho):
            caminho.unlink()
            raise EsquemaInesperado("pacote companyfacts.zip da SEC corrompido duas vezes; tenta na próxima rodada")
    with zipfile.ZipFile(caminho) as z:
        nomes = set(z.namelist())
        for n, (cik, (ticker, _)) in enumerate(emissores.items(), start=1):
            nome = f"CIK{cik}.json"
            if nome not in nomes:
                continue
            try:
                with ctx.sessao.begin_nested():
                    total += gravar(ctx, ticker, cik, None, json.loads(z.read(nome)))
            except zipfile.BadZipFile:
                raise
            except Exception as erro:  # noqa: BLE001
                falhas.append(f"{ticker}: {erro!r}"[:150])
            if n % 200 == 0:
                ctx.sessao.commit()
                log.info("SEC em lote: %s de %s empresas", n, len(emissores))
    ctx.sessao.commit()
    return total


def _ciks_recentes(cliente, cab: dict, desde: date, ate: date, pausa: float) -> set[str]:
    ciks: set[str] = set()
    dia = desde
    while dia <= ate:
        if dia.weekday() < 5:
            time.sleep(pausa)
            r = cliente.get(URL_INDICE_DIARIO.format(ano=dia.year, tri=(dia.month - 1) // 3 + 1, dia=dia), headers=cab)
            if r.status_code == 200:
                ciks |= ciks_do_indice(r.text)
            elif r.status_code not in (403, 404):  # feriado/dia ainda não publicado: segue
                r.raise_for_status()
        dia += timedelta(days=1)
    return ciks


FRACAO_MAXIMA_SEM_BALANCO = 0.4


def _fracao_sem_balanco(sessao) -> float:
    total = sessao.scalar(select(func.count()).select_from(Empresa).where(Empresa.pais == "US")) or 0
    com = sessao.scalar(select(func.count(func.distinct(DemonstracaoPadronizada.empresa_id)))
                        .join(Empresa, Empresa.id == DemonstracaoPadronizada.empresa_id)
                        .where(Empresa.pais == "US")) or 0
    return 1 - com / total if total else 0.0


def _ultima_carga(sessao) -> date | None:
    from app.db.modelos import Fonte, LoteIngestao
    momento = sessao.scalar(select(func.max(LoteIngestao.concluido_em)).join(Fonte, Fonte.id == LoteIngestao.fonte_id)
                            .where(Fonte.codigo == "SEC_EDGAR", LoteIngestao.status == "concluido",
                                   LoteIngestao.linhas_gravadas > 0))
    return momento.date() if momento else None


def ingerir_todas(sessao, cliente=None, pausa: float = 0.12, completo: bool = False) -> int:
    """Todas as empresas listadas nos EUA (D-044).

    Primeira vez (ou `completo`): pacote em lote com os balanços de todas. Depois: só as empresas com 10-K/10-Q
    arquivado desde a última carga, pelo índice diário da SEC. Em seguida, o setor (SIC) dos emissores novos.
    """
    from app.ingestao.base import cliente_http

    cfg = obter_configuracao()
    garantir_etfs(sessao, cfg.lista_etfs_eua)
    proprio = cliente is None
    cliente = cliente or cliente_http()
    total, falhas = 0, []
    try:
        with lote(sessao, "SEC_EDGAR", URL_TICKERS_BOLSA) as ctx:
            cab = cabecalhos()
            resposta = cliente.get(URL_TICKERS_BOLSA, headers=cab)
            resposta.raise_for_status()
            emissores = universo(resposta.json())
            _registrar_universo(ctx, emissores)
            ultima = None if completo else _ultima_carga(sessao)
            # Carga em lote incompleta (download corrompido, interrupção): refaz em vez de esperar cada empresa
            # arquivar um 10-K/10-Q novo. ~15% nunca terão balanço (emissores estrangeiros, sem US-GAAP).
            if ultima is not None and _fracao_sem_balanco(sessao) > FRACAO_MAXIMA_SEM_BALANCO:
                ultima = None
            if ultima is None:
                total = _fundamentos_em_lote(ctx, cliente, cab, emissores, falhas)
            else:
                recentes = _ciks_recentes(cliente, cab, ultima - timedelta(days=2), date.today(), pausa)
                for cik in sorted(recentes & set(emissores)):
                    ticker = emissores[cik][0]
                    try:
                        time.sleep(pausa)
                        fac = cliente.get(URL_FACTS.format(cik=cik), headers=cab)
                        fac.raise_for_status()
                        with sessao.begin_nested():
                            total += gravar(ctx, ticker, cik, None, fac.json())
                        sessao.commit()
                    except Exception as erro:  # noqa: BLE001 — uma empresa com problema não impede as outras
                        falhas.append(f"{ticker}: {erro!r}"[:150])
            setores = _completar_setores(ctx, cliente, cab, pausa)
            ctx.lote.linhas_gravadas = total
            partes = [f"{len(emissores)} empresas listadas", f"{setores} setores novos"]
            if falhas:
                partes.append(f"{len(falhas)} com falha (ex.: {'; '.join(falhas[:3])})")
            ctx.lote.erro = "; ".join(partes)
    finally:
        if proprio:
            cliente.close()
    log.info("SEC EDGAR (todas): %s períodos; %s falhas", total, len(falhas))
    return total


def ingerir(sessao, tickers: list[str] | None = None, cliente=None, pausa: float = 0.15) -> int:
    from app.ingestao.base import cliente_http

    cfg = obter_configuracao()
    if tickers is None and cfg.eua_todas:
        return ingerir_todas(sessao, cliente)
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
