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
