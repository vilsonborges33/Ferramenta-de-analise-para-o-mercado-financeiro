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
