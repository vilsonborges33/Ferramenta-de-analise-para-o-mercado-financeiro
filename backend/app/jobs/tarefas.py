"""Tarefas de ingestão e recálculo, usadas pelo agendador e pela linha de comando."""

import logging
from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select

from app.config import obter_configuracao
from app.db.modelos import (
    Ativo,
    CotacaoDiaria,
    DemonstracaoLinha,
    Fii,
    FiiImovel,
    Fonte,
    LoteIngestao,
    Provento,
    SerieEconomica,
)
from app.db.sessao import FabricaSessao, motor
from app.ingestao import (
    b3_proventos,
    bcb_sgs,
    brapi,
    cotahist,
    cvm_companhias,
    cvm_demonstracoes,
    cvm_fii,
    cvm_fii_trimestral,
    damodaran,
    fnet_rendimentos,
    sec_edgar,
    tesouro,
    us_treasury,
    yahoo,
)
from app.ingestao.base import garantir_fontes
from app.ingestao.padronizacao_db import empresas_sem_padronizacao, padronizar_todas
from app.servicos.indicadores import recalcular

log = logging.getLogger(__name__)


def _executar(nome: str, funcao, *args):
    with FabricaSessao() as sessao:
        try:
            resultado = funcao(sessao, *args)
            log.info("%s: %s", nome, resultado)
            return resultado
        except Exception:
            log.exception("%s falhou", nome)
            return None


def preparar() -> None:
    with FabricaSessao() as sessao:
        garantir_fontes(sessao)
        sessao.commit()


def companhias(ano: int | None = None) -> None:
    ano = ano or date.today().year
    _executar("cadastro CVM", cvm_companhias.ingerir_cadastro)
    _executar(f"FCA {ano}", cvm_companhias.ingerir_valores_mobiliarios, ano)


def demonstracoes(anos: list[int]) -> None:
    for ano in anos:
        _executar(f"DFP {ano}", cvm_demonstracoes.ingerir, "DFP", ano)
        _executar(f"ITR {ano}", cvm_demonstracoes.ingerir, "ITR", ano)
    _executar("padronização", padronizar_todas)


ANOS_HISTORICO_LONGO = 15  # DFP desde ~2011: 10 anos de lucro e LPA (checklist de Graham, Lynch, Siegel)


def anos_sem_dfp(sessao, anos: list[int]) -> list[int]:
    """Anos da lista sem nenhuma DFP baixada com sucesso."""
    urls = set(sessao.scalars(select(LoteIngestao.arquivo_origem).join(Fonte, Fonte.id == LoteIngestao.fonte_id)
                              .where(Fonte.codigo == "CVM_DFP", LoteIngestao.status == "concluido")))
    return [a for a in anos if not any(f"dfp_cia_aberta_{a}.zip" in (u or "") for u in urls)]


def historico_longo() -> None:
    """Só as DFP (anuais) dos anos antigos que ainda faltam; os trimestres antigos não são usados."""
    hoje = date.today().year
    with FabricaSessao() as sessao:
        faltam = anos_sem_dfp(sessao, list(range(hoje - ANOS_HISTORICO_LONGO, hoje - ANOS_CARGA_INICIAL)))
    for ano in faltam:
        _executar(f"DFP {ano} (histórico longo)", cvm_demonstracoes.ingerir, "DFP", ano)
    if faltam:
        _executar("padronização", padronizar_todas)


def fiis(anos: list[int]) -> None:
    for ano in anos:
        _executar(f"FII mensal {ano}", cvm_fii.ingerir, ano)
        _executar(f"FII trimestral {ano}", cvm_fii_trimestral.ingerir, ano)


def usa_yahoo() -> bool:
    return obter_configuracao().fonte_mercado == "yahoo"


def cotacoes_historicas(anos: list[int], somente_acompanhados: bool = False) -> None:
    """Histórico de cotações (e, no Yahoo, também dos dividendos) cobrindo os anos pedidos."""
    tickers = set(obter_configuracao().lista_tickers) if somente_acompanhados else None
    if usa_yahoo():
        anos_atras = date.today().year - min(anos) + 1
        _executar("Yahoo Finance (histórico)", yahoo.ingerir, sorted(tickers) if tickers else None, f"{anos_atras}y")
        return
    for ano in anos:
        _executar(f"COTAHIST {ano}", cotahist.ingerir_ano, ano, tickers)


def indices(intervalo: str = "5d") -> None:
    _executar(f"índices Ibovespa e IFIX ({intervalo})", yahoo.ingerir_indices, intervalo)


def cotacoes_do_dia(dia: date | None = None) -> None:
    indices()
    if usa_yahoo():
        # B3 primeiro: as milhares de empresas dos EUA (D-044) não atrasam os números daqui.
        _executar("Yahoo Finance (últimos dias)", yahoo.ingerir, None, "5d", None, 0.4, "B3")
        _executar("Yahoo Finance (EUA, últimos dias)", yahoo.ingerir, None, "5d", None, 0.2, "US")
        return
    dia = dia or date.today()
    _executar(f"COTAHIST {dia}", cotahist.ingerir_dia, dia)
    _executar("brapi", brapi.ingerir, obter_configuracao().lista_tickers)


def proventos(dias_fnet: int = 10) -> None:
    """Proventos. No Yahoo vêm junto com as cotações (último ano); senão, B3 (ações) e FNET (FIIs)."""
    if usa_yahoo():
        _executar("Yahoo Finance (dividendos)", yahoo.ingerir, None, "2y")
        return
    _executar("B3 proventos", b3_proventos.ingerir)
    _executar("FNET rendimentos", fnet_rendimentos.ingerir, dias_fnet)


def macro() -> None:
    _executar("Treasury 10 anos (EUA)", us_treasury.ingerir)
    _executar("BCB SGS", bcb_sgs.ingerir_todas)
    _executar("Tesouro", tesouro.ingerir, date.today() - timedelta(days=3650))
    _executar("Damodaran (prêmios de risco)", damodaran.ingerir)


def eua() -> None:
    """Fundamentos das empresas e REITs dos EUA (SEC) e cadastro dos ETFs da lista do .env."""
    _executar("SEC EDGAR (EUA)", sec_edgar.ingerir)


def indicadores(tickers: list[str] | None = None) -> None:
    _executar("recálculo de indicadores", recalcular, tickers)
    alertas()


def alertas() -> None:
    """Avalia os alertas dos usuários com os indicadores recém-calculados (Fase 8)."""
    from app.servicos import alertas as servico_alertas
    _executar("verificação de alertas", servico_alertas.verificar)


def precisa_carga_inicial(sessao) -> bool:
    """Verdadeiro enquanto nenhuma demonstração da CVM foi gravada (instalação nova ou carga interrompida)."""
    return sessao.scalar(select(func.count()).select_from(DemonstracaoLinha)) == 0


ANOS_CARGA_INICIAL = 6  # 6 anos de DFP permitem o CAGR de 5 anos


def faltam_cotacoes(sessao) -> bool:
    """Menos da metade das ações ativas tem cotação (ex.: só as poucas que a brapi gratuita libera)."""
    acoes = sessao.scalar(select(func.count()).select_from(Ativo).where(Ativo.classe == "ACAO", Ativo.ativo.is_(True)))
    com_cotacao = sessao.scalar(select(func.count(func.distinct(CotacaoDiaria.ativo_id)))
                                .join(Ativo, Ativo.id == CotacaoDiaria.ativo_id).where(Ativo.classe == "ACAO"))
    return acoes > 0 and com_cotacao < acoes / 2


def fiis_sem_ticker(sessao) -> bool:
    """Mais da metade dos fundos do informe mensal ainda sem ticker ligado."""
    total = sessao.scalar(select(func.count()).select_from(Fii))
    ligados = sessao.scalar(select(func.count()).select_from(Fii).where(Fii.ativo_id.is_not(None)))
    return total > 0 and ligados < total / 2


def tickers_sem_cotacao(sessao, mercado: str = "B3") -> list[str]:
    classes = ("STOCK", "REIT", "ETF") if mercado == "US" else ("ACAO", "UNIT", "FII")
    com_cotacao = select(CotacaoDiaria.ativo_id).distinct()
    return list(sessao.scalars(select(Ativo.ticker).where(
        Ativo.ativo.is_(True), Ativo.classe.in_(classes), Ativo.id.not_in(com_cotacao))))


def faltam_proventos(sessao) -> bool:
    return sessao.scalar(select(func.count()).select_from(Provento)) == 0


def _passo(nome: str, funcao, *args) -> None:
    """Executa um passo do complemento sem deixar uma falha interromper os seguintes."""
    try:
        funcao(*args)
    except Exception:
        log.exception("%s falhou", nome)


def _criar_tickers_fii() -> None:
    with FabricaSessao() as sessao:  # FIIs ganham ticker pelo ISIN (antes vinha do COTAHIST)
        cvm_fii.criar_ativos_pelo_isin(sessao)
        cotahist.ligar_fiis_por_isin(sessao)
        sessao.commit()


def completar_carga(forcar: bool = False) -> None:
    """Instalação com carga parcial: organiza balanços pendentes, busca cotações/dividendos que faltam
    e recalcula. Com `forcar`, refaz cotações e dividendos mesmo que pareçam completos."""
    with trava_exclusiva() as obtida:
        if not obtida:
            log.warning("já existe uma carga em andamento; complemento ignorado")
            return
        with FabricaSessao() as sessao:
            sem_padronizacao = empresas_sem_padronizacao(sessao)
            sem_cotacoes = forcar or faltam_cotacoes(sessao)
            sem_proventos = forcar or faltam_proventos(sessao)
            sem_ticker_fii = fiis_sem_ticker(sessao)
            sem_imoveis = sessao.scalar(select(func.count()).select_from(FiiImovel)) == 0
            # Menos de ~1 ano de Ibovespa: o histórico nunca foi baixado (beta, rentabilidade da carteira).
            sem_indices = (sessao.scalar(select(func.count()).select_from(SerieEconomica)
                                         .where(SerieEconomica.codigo == "IBOV")) or 0) < 200
            hoje = date.today().year
            antigos = list(range(hoje - ANOS_HISTORICO_LONGO, hoje - ANOS_CARGA_INICIAL))
            sem_historico = bool(anos_sem_dfp(sessao, antigos))
        if not (sem_padronizacao or sem_cotacoes or sem_proventos or sem_ticker_fii or sem_imoveis or sem_indices
                or sem_historico):
            return
        ano = date.today().year
        if sem_indices:  # Ibovespa e IFIX para comparar a rentabilidade da carteira (Fase 6)
            _passo("índices", indices, f"{ANOS_CARGA_INICIAL + 1}y")
        if sem_imoveis and not sem_ticker_fii:  # imóveis e vacância (informe trimestral, Fase 5)
            for a in (ano - 1, ano):
                _passo("informe trimestral de FII", _executar, f"FII trimestral {a}", cvm_fii_trimestral.ingerir, a)
        if sem_ticker_fii:  # reprocessa os informes (leitura do ISIN mais tolerante) para criar os tickers
            _passo("informes de FII", fiis, [ano - 1, ano])
        _passo("tickers de FII", _criar_tickers_fii)
        if sem_padronizacao:
            log.info("%s empresa(s) com balanço sem períodos organizados: reorganizando", sem_padronizacao)
            _passo("padronização", _executar, "padronização", padronizar_todas)
        if sem_historico:  # DFP antigas (10 anos de lucro e LPA para Graham, Lynch e Siegel)
            _passo("histórico longo", historico_longo)
        if sem_cotacoes:
            log.info("faltam cotações: baixando de %s a %s", ano - ANOS_CARGA_INICIAL, ano)
            _passo("cotações", cotacoes_historicas, list(range(ano - ANOS_CARGA_INICIAL, ano + 1)))
        elif usa_yahoo():  # ativos novos (ex.: FIIs que acabaram de ganhar ticker) ainda sem nenhum preço
            with FabricaSessao() as sessao:
                pendentes = tickers_sem_cotacao(sessao)
            if pendentes:
                log.info("%s ativo(s) sem nenhuma cotação: buscando no Yahoo", len(pendentes))
                _passo("cotações pendentes", _executar, "Yahoo Finance (pendentes)", yahoo.ingerir, pendentes,
                       f"{ANOS_CARGA_INICIAL + 1}y")
        if sem_proventos and not (usa_yahoo() and sem_cotacoes):  # no Yahoo, o histórico já trouxe os dividendos
            _passo("proventos", proventos, 400)
        _passo("indicadores", indicadores)


def ultima_cotacao(sessao) -> date | None:
    """Data em que as cotações das ações estão em dia: a mediana da última cotação de cada ação ativa.
    (O máximo enganava: uma única ação atualizada escondia todas as outras paradas.)"""
    ultimas = (select(func.max(CotacaoDiaria.data).label("data")).join(Ativo, Ativo.id == CotacaoDiaria.ativo_id)
               .where(Ativo.classe == "ACAO", Ativo.ativo.is_(True)).group_by(CotacaoDiaria.ativo_id).subquery())
    datas = sorted(sessao.scalars(select(ultimas.c.data)))
    return datas[(len(datas) - 1) // 2] if datas else None


def ultima_atualizacao(sessao, *codigos: str) -> datetime | None:
    """Fim do último lote concluído das fontes indicadas (o mais recente entre elas)."""
    return sessao.scalar(select(func.max(LoteIngestao.concluido_em)).join(Fonte, Fonte.id == LoteIngestao.fonte_id)
                         .where(Fonte.codigo.in_(codigos), LoteIngestao.status == "concluido"))


def ultimo_dia_util(hoje: date) -> date:
    dia = hoje - timedelta(days=1)
    while dia.weekday() >= 5:
        dia -= timedelta(days=1)
    return dia


FUSO = ZoneInfo("America/Sao_Paulo")
HORA_FECHAMENTO = 19  # depois das 19h (Brasília) o fechamento do dia já está disponível


def dia_esperado(hoje: date, agora: datetime | None = None) -> date:
    """Pregão mais recente que já deveria estar no banco: hoje depois das 19h em dia útil; senão o anterior."""
    local = agora.astimezone(FUSO) if agora else None
    if local and local.date() == hoje and hoje.weekday() < 5 and local.hour >= HORA_FECHAMENTO:
        return hoje
    return ultimo_dia_util(hoje)


def intervalo_yahoo(dias: int) -> str:
    """Menor janela do Yahoo que cobre `dias` corridos sem cotação (com folga para feriados)."""
    for limite, janela in ((4, "5d"), (25, "1mo"), (80, "3mo"), (170, "6mo"), (350, "1y")):
        if dias <= limite:
            return janela
    return f"{dias // 365 + 1}y"


def _desatualizada(momento: datetime | None, agora: datetime, horas: int = 20) -> bool:
    return momento is None or agora - momento > timedelta(hours=horas)


def por_em_dia(hoje: date | None = None, agora: datetime | None = None) -> list[str]:
    """Ao ligar a aplicação: busca o que ficou para trás enquanto o computador estava desligado.
    Só baixa o que está desatualizado; devolve os passos executados."""
    agora = agora or datetime.now(UTC)
    hoje = hoje or agora.astimezone(FUSO).date()
    with FabricaSessao() as sessao:
        cotacao = ultima_cotacao(sessao)
        yahoo_em = ultima_atualizacao(sessao, "YAHOO_FINANCE", "B3_COTAHIST")
        macro_em = ultima_atualizacao(sessao, "BCB_SGS", "TESOURO_TD")
        cvm_em = ultima_atualizacao(sessao, "CVM_DFP", "CVM_ITR")
        sec_em = ultima_atualizacao(sessao, "SEC_EDGAR")
        fii_em = ultima_atualizacao(sessao, "CVM_FII_MENSAL")
        proventos_em = ultima_atualizacao(sessao, "B3_PROVENTOS", "FNET_RENDIMENTOS")
    feitos: list[str] = []
    # Feriado: o pregão esperado nunca chega; uma tentativa a cada 3 h basta (não refaz a cada hora).
    if (cotacao is None or cotacao < dia_esperado(hoje, agora)) and _desatualizada(yahoo_em, agora, horas=3):
        dias = (hoje - cotacao).days if cotacao else 365 * ANOS_CARGA_INICIAL
        log.info("cotações paradas desde %s: buscando os dias que faltam", cotacao)
        _passo("índices", indices, intervalo_yahoo(dias))
        if usa_yahoo():
            _passo("cotações atrasadas", _executar, "Yahoo Finance (atrasadas)", yahoo.ingerir, None,
                   intervalo_yahoo(dias))
        else:
            for n in range(min(dias, 60), -1, -1):  # COTAHIST diário; dias sem pregão são pulados
                _passo("cotações atrasadas", cotacoes_do_dia, hoje - timedelta(days=n))
        feitos.append("cotacoes")
    if not usa_yahoo() and _desatualizada(proventos_em, agora):
        _passo("proventos", proventos, max(10, (agora - proventos_em).days + 3) if proventos_em else 400)
        feitos.append("proventos")
    if _desatualizada(macro_em, agora):
        _passo("macro", macro)
        feitos.append("macro")
    if feitos:  # números novos na tela antes dos downloads demorados da CVM
        _passo("indicadores", indicadores)
    if _desatualizada(sec_em, agora):  # EUA: balanços na SEC e histórico de cotações de quem ainda não tem
        _passo("SEC EDGAR", eua)
        if usa_yahoo():
            with FabricaSessao() as sessao:
                novos = tickers_sem_cotacao(sessao, mercado="US")
            if novos:
                _passo("cotações EUA", _executar, "Yahoo Finance (EUA, histórico)", yahoo.ingerir, novos,
                       f"{ANOS_CARGA_INICIAL + 1}y")
        _passo("indicadores", indicadores)
        feitos.append("eua")
    if _desatualizada(cvm_em, agora) or _desatualizada(fii_em, agora):
        _passo("cadastro CVM", companhias)
        _passo("balanços", demonstracoes, [hoje.year])
        _passo("informes de FII", fiis, [hoje.year])
        _passo("indicadores", indicadores)
        feitos.append("cvm")
    return feitos


def verificar_periodicamente() -> None:
    """A cada hora, com a aplicação ligada: põe em dia o que estiver atrasado (computador que dormiu,
    tarefa das 19h perdida, CVM com documento novo). Se outra carga estiver rodando, espera a próxima hora."""
    with trava_exclusiva() as obtida:
        if not obtida:
            return
        feitos = por_em_dia()
    if feitos:
        log.info("verificação periódica: %s", ", ".join(feitos))


def atualizar_ao_iniciar() -> None:
    """Primeira subida: carga inicial. Depois: completa o que faltar e põe os dados em dia."""
    with FabricaSessao() as sessao:
        vazio = precisa_carga_inicial(sessao)
    if not vazio:
        # Primeiro o que muda todo dia (cotações), depois o complemento, que pode ser demorado.
        with trava_exclusiva() as obtida:
            if not obtida:
                log.warning("já existe uma carga em andamento; atualização da inicialização ignorada")
                return
            feitos = por_em_dia()
        log.info("atualização da inicialização: %s", ", ".join(feitos) or "dados já estavam em dia")
        completar_carga()
        return
    carga_inicial_se_vazio()


def carga_inicial_se_vazio() -> None:
    with FabricaSessao() as sessao:
        parcial = not precisa_carga_inicial(sessao)
    if parcial:
        completar_carga()
        return
    ano = date.today().year
    log.info("banco sem dados: iniciando a carga inicial (%s–%s); pode levar bastante tempo",
             ano - ANOS_CARGA_INICIAL, ano)
    carga_inicial(ano - ANOS_CARGA_INICIAL, ano)


CHAVE_TRAVA_CARGA = 7_214_001  # trava consultiva do PostgreSQL (um número qualquer, fixo)


@contextmanager
def trava_exclusiva(chave: int = CHAVE_TRAVA_CARGA):
    """Garante uma carga por vez entre processos (worker e linha de comando). Devolve False se já há outra."""
    with motor.connect() as conexao:
        obtida = conexao.execute(select(func.pg_try_advisory_lock(chave))).scalar()
        try:
            yield bool(obtida)
        finally:
            if obtida:
                conexao.execute(select(func.pg_advisory_unlock(chave)))


def carga_inicial(ano_inicial: int, ano_final: int) -> None:
    with trava_exclusiva() as obtida:
        if not obtida:
            log.warning("já existe uma carga em andamento (worker ou outro terminal); esta foi ignorada")
            return
        _carga_inicial(ano_inicial, ano_final)


def _carga_inicial(ano_inicial: int, ano_final: int) -> None:
    anos = list(range(ano_inicial, ano_final + 1))
    preparar()
    companhias(ano_final)
    demonstracoes(anos)
    fiis(anos)
    cotacoes_historicas(anos)
    if not usa_yahoo():  # no Yahoo, o histórico de cotações já traz os dividendos
        proventos(dias_fnet=400)  # 13 meses: cobre a janela de 12 meses do DY por data de pagamento
    macro()
    cotacoes_do_dia()
    indicadores()
