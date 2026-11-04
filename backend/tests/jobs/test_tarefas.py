import io
import zipfile

from app.ingestao import cvm_demonstracoes
from app.ingestao.base import lote
from app.jobs import tarefas
from tests import amostras
from tests.ingestao.test_conectores import carregar_companhias


def test_precisa_carga_inicial(sessao):
    assert tarefas.precisa_carga_inicial(sessao)
    carregar_companhias(sessao)
    with zipfile.ZipFile(io.BytesIO(amostras.zip_dfp(2024, 8000, 1000))) as z, lote(sessao, "CVM_DFP") as ctx:
        cvm_demonstracoes.processar_zip(ctx, z, "DFP", 2024)
    assert not tarefas.precisa_carga_inicial(sessao)


def test_carga_inicial_so_roda_com_banco_vazio(sessao, monkeypatch):
    chamadas = []
    monkeypatch.setattr(tarefas, "carga_inicial", lambda de, ate: chamadas.append((de, ate)))
    tarefas.carga_inicial_se_vazio()
    assert len(chamadas) == 1 and chamadas[0][1] - chamadas[0][0] == tarefas.ANOS_CARGA_INICIAL
    carregar_companhias(sessao)
    with zipfile.ZipFile(io.BytesIO(amostras.zip_dfp(2024, 8000, 1000))) as z, lote(sessao, "CVM_DFP") as ctx:
        cvm_demonstracoes.processar_zip(ctx, z, "DFP", 2024)
    tarefas.carga_inicial_se_vazio()
    assert len(chamadas) == 1


def test_completa_carga_parcial_sem_cotacoes(sessao, monkeypatch):
    carregar_companhias(sessao)
    with zipfile.ZipFile(io.BytesIO(amostras.zip_dfp(2024, 8000, 1000))) as z, lote(sessao, "CVM_DFP") as ctx:
        cvm_demonstracoes.processar_zip(ctx, z, "DFP", 2024)
    chamadas = []
    monkeypatch.setattr(tarefas, "cotacoes_historicas", lambda anos: chamadas.append(("cotacoes", tuple(anos))))
    monkeypatch.setattr(tarefas, "proventos", lambda dias_fnet: chamadas.append(("proventos", dias_fnet)))
    monkeypatch.setattr(tarefas, "indicadores", lambda: chamadas.append(("indicadores",)))
    monkeypatch.setattr(tarefas, "_carga_inicial", lambda de, ate: chamadas.append(("completa",)))
    tarefas.carga_inicial_se_vazio()
    # Yahoo (padrão): o histórico de cotações já traz os dividendos; não refaz a carga completa
    assert [c[0] for c in chamadas] == ["cotacoes", "indicadores"]


def test_completar_organiza_balancos_pendentes_e_registra_no_status(sessao, monkeypatch):
    from sqlalchemy import select

    from app.db.modelos import DemonstracaoPadronizada, Fonte, LoteIngestao
    from app.ingestao.padronizacao_db import empresas_sem_padronizacao

    carregar_companhias(sessao)
    with zipfile.ZipFile(io.BytesIO(amostras.zip_dfp(2024, 8000, 1000))) as z, lote(sessao, "CVM_DFP") as ctx:
        cvm_demonstracoes.processar_zip(ctx, z, "DFP", 2024)
    assert empresas_sem_padronizacao(sessao) == 1
    monkeypatch.setattr(tarefas, "cotacoes_historicas", lambda anos: None)
    monkeypatch.setattr(tarefas, "indicadores", lambda: None)
    tarefas.completar_carga()
    sessao.expire_all()
    assert empresas_sem_padronizacao(sessao) == 0
    assert sessao.query(DemonstracaoPadronizada).count() > 0
    registro = sessao.scalars(select(LoteIngestao).join(Fonte).where(Fonte.codigo == "PROCESSAMENTO_CVM")).first()
    assert registro.status == "concluido" and "1 empresas organizadas" in registro.erro


def test_faltam_cotacoes_quando_menos_da_metade_tem_preco(sessao):
    from datetime import date
    from decimal import Decimal

    from sqlalchemy import select

    from app.db.modelos import Ativo, CotacaoDiaria
    carregar_companhias(sessao)  # 3 ações
    assert tarefas.faltam_cotacoes(sessao)
    ids = list(sessao.scalars(select(Ativo.id)))
    with lote(sessao, "BRAPI") as ctx:
        sessao.add(CotacaoDiaria(ativo_id=ids[0], data=date(2025, 1, 2), fechamento=Decimal(1),
                                 **ctx.procedencia(date(2025, 1, 2))))
    assert tarefas.faltam_cotacoes(sessao)  # 1 de 3: como as poucas cotações da brapi gratuita
    with lote(sessao, "BRAPI") as ctx:
        sessao.add(CotacaoDiaria(ativo_id=ids[1], data=date(2025, 1, 2), fechamento=Decimal(1),
                                 **ctx.procedencia(date(2025, 1, 2))))
    assert not tarefas.faltam_cotacoes(sessao)


def test_falha_num_passo_nao_impede_os_seguintes(sessao, monkeypatch):
    chamadas = []

    def quebra(*a):
        raise RuntimeError("falha simulada")

    monkeypatch.setattr(tarefas, "_criar_tickers_fii", quebra)
    monkeypatch.setattr(tarefas, "cotacoes_historicas", lambda anos: chamadas.append("cotacoes"))
    monkeypatch.setattr(tarefas, "indicadores", lambda: chamadas.append("indicadores"))
    carregar_companhias(sessao)
    tarefas.completar_carga(forcar=True)
    assert chamadas == ["cotacoes", "indicadores"]


def test_tickers_sem_cotacao_e_fiis_sem_ticker(sessao):
    from datetime import date

    from app.db.modelos import Fii
    carregar_companhias(sessao)
    assert sorted(tarefas.tickers_sem_cotacao(sessao)) == ["BEXM3", "EXMP3", "EXMP4"]
    assert not tarefas.fiis_sem_ticker(sessao)  # nenhum FII cadastrado
    with lote(sessao, "CVM_FII_MENSAL") as ctx:
        sessao.add(Fii(cnpj="1", nome="F", isin="BRABCDCTF000", **ctx.procedencia(date(2025, 1, 1))))
    assert tarefas.fiis_sem_ticker(sessao)


def test_intervalo_yahoo_cobre_os_dias_parados():
    assert tarefas.intervalo_yahoo(1) == "5d"
    assert tarefas.intervalo_yahoo(10) == "1mo"
    assert tarefas.intervalo_yahoo(60) == "3mo"
    assert tarefas.intervalo_yahoo(300) == "1y"
    assert tarefas.intervalo_yahoo(800) == "3y"


def test_ultimo_dia_util():
    from datetime import date
    assert tarefas.ultimo_dia_util(date(2026, 11, 3)) == date(2026, 11, 2)  # terça → segunda
    assert tarefas.ultimo_dia_util(date(2026, 11, 2)) == date(2026, 10, 30)  # segunda → sexta


def test_por_em_dia_busca_so_o_que_esta_atrasado(sessao, monkeypatch):
    from datetime import UTC, date, datetime, timedelta
    from decimal import Decimal

    from sqlalchemy import select

    from app.db.modelos import Ativo, CotacaoDiaria
    carregar_companhias(sessao)
    ativo = sessao.scalars(select(Ativo).where(Ativo.classe == "ACAO")).first()
    with lote(sessao, "YAHOO_FINANCE") as ctx:
        sessao.add(CotacaoDiaria(ativo_id=ativo.id, data=date(2026, 10, 20), fechamento=Decimal(1),
                                 **ctx.procedencia(date(2026, 10, 20))))
    with lote(sessao, "BCB_SGS"), lote(sessao, "CVM_DFP"), lote(sessao, "CVM_FII_MENSAL"):
        pass
    from app.db.modelos import Fonte, LoteIngestao
    for registro in sessao.scalars(select(LoteIngestao).join(Fonte, Fonte.id == LoteIngestao.fonte_id)
                                   .where(Fonte.codigo == "YAHOO_FINANCE")):  # rodada do Yahoo de ontem
        registro.concluido_em = datetime.now(UTC) - timedelta(days=1)
    sessao.commit()
    chamadas = []
    monkeypatch.setattr(tarefas.yahoo, "ingerir", lambda s, t, intervalo: chamadas.append(("yahoo", intervalo)))
    monkeypatch.setattr(tarefas, "macro", lambda: chamadas.append(("macro",)))
    monkeypatch.setattr(tarefas, "companhias", lambda: chamadas.append(("cvm",)))
    monkeypatch.setattr(tarefas, "indicadores", lambda: chamadas.append(("indicadores",)))
    agora = datetime.now(UTC)
    # cotações paradas há 14 dias; macro e CVM atualizados agora
    assert tarefas.por_em_dia(date(2026, 11, 3), agora) == ["cotacoes"]
    assert chamadas == [("yahoo", "1mo"), ("indicadores",)]
    # dados em dia: nada a fazer
    chamadas.clear()
    assert tarefas.por_em_dia(date(2026, 10, 21), agora) == [] and chamadas == []


def test_ultima_cotacao_e_a_mediana_e_nao_o_maximo(sessao):
    from datetime import date
    from decimal import Decimal

    from sqlalchemy import select

    from app.db.modelos import Ativo, CotacaoDiaria
    carregar_companhias(sessao)  # 3 ações
    ids = list(sessao.scalars(select(Ativo.id).where(Ativo.classe == "ACAO")))
    datas = [date(2026, 10, 9), date(2026, 10, 9), date(2026, 11, 3)]  # só uma ação em dia
    with lote(sessao, "YAHOO_FINANCE") as ctx:
        for ativo_id, dia in zip(ids, datas, strict=True):
            sessao.add(CotacaoDiaria(ativo_id=ativo_id, data=dia, fechamento=Decimal(1), **ctx.procedencia(dia)))
    assert tarefas.ultima_cotacao(sessao) == date(2026, 10, 9)


def test_dia_esperado_considera_o_fechamento_das_19h():
    from datetime import UTC, date, datetime
    terca = date(2026, 11, 3)
    assert tarefas.dia_esperado(terca, datetime(2026, 11, 3, 23, 0, tzinfo=UTC)) == terca  # 20h em Brasília
    assert tarefas.dia_esperado(terca, datetime(2026, 11, 3, 15, 0, tzinfo=UTC)) == date(2026, 11, 2)  # 12h
    sabado = date(2026, 11, 7)
    assert tarefas.dia_esperado(sabado, datetime(2026, 11, 7, 23, 0, tzinfo=UTC)) == date(2026, 11, 6)


def test_feriado_nao_refaz_a_busca_a_cada_hora(sessao, monkeypatch):
    from datetime import UTC, date, datetime, timedelta
    from decimal import Decimal

    from sqlalchemy import select

    from app.db.modelos import Ativo, CotacaoDiaria
    carregar_companhias(sessao)
    ativo = sessao.scalars(select(Ativo).where(Ativo.classe == "ACAO")).first()
    with lote(sessao, "YAHOO_FINANCE") as ctx:  # rodada de agora há pouco
        sessao.add(CotacaoDiaria(ativo_id=ativo.id, data=date(2026, 10, 30), fechamento=Decimal(1),
                                 **ctx.procedencia(date(2026, 10, 30))))
    with lote(sessao, "BCB_SGS"), lote(sessao, "CVM_DFP"), lote(sessao, "CVM_FII_MENSAL"):
        pass
    sessao.commit()
    chamadas = []
    monkeypatch.setattr(tarefas.yahoo, "ingerir", lambda *a: chamadas.append(a))
    agora = datetime.now(UTC)
    assert tarefas.por_em_dia(date(2026, 11, 3), agora) == [] and chamadas == []
    assert tarefas.por_em_dia(date(2026, 11, 3), agora + timedelta(hours=4)) != []
