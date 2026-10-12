import httpx

from app.ingestao import yahoo
from app.jobs import diagnostico
from tests.ingestao.test_conectores import carregar_companhias
from tests.ingestao.test_yahoo import RESPOSTA


def test_diagnostico_resume_e_testa_yahoo(sessao, monkeypatch):
    carregar_companhias(sessao)
    transporte = httpx.MockTransport(lambda r: httpx.Response(200, json=RESPOSTA))
    monkeypatch.setattr(diagnostico, "cliente_http", lambda: httpx.Client(transport=transporte))
    texto = diagnostico.executar("EXMP3")
    assert "fonte de mercado: yahoo" in texto
    assert "CVM_CADASTRO: concluido" in texto and "YAHOO_FINANCE: nunca executado" in texto
    assert "última cotação: nenhuma" in texto and "basico.lpa: não calculado" in texto
    assert "HTTP 200" in texto and "2 pregões" in texto
    assert "ticker não cadastrado" in diagnostico.executar("NADA3")
    assert yahoo.simbolo("EXMP3") in texto


def test_diagnostico_testa_organizacao_dos_balancos(sessao, monkeypatch):
    import io
    import zipfile

    from app.ingestao import cvm_demonstracoes
    from app.ingestao.base import lote
    from tests import amostras
    carregar_companhias(sessao)
    with zipfile.ZipFile(io.BytesIO(amostras.zip_dfp(2024, 8000, 1000))) as z, lote(sessao, "CVM_DFP") as ctx:
        cvm_demonstracoes.processar_zip(ctx, z, "DFP", 2024)
    transporte = httpx.MockTransport(lambda r: httpx.Response(200, json=RESPOSTA))
    monkeypatch.setattr(diagnostico, "cliente_http", lambda: httpx.Client(transport=transporte))
    texto = diagnostico.executar("EXMP3")
    assert "organização dos balanços (teste agora): ok" in texto and "2024-A" in texto

    import app.ingestao.padronizacao as pad

    def quebra(*a, **k):
        raise ValueError("leiaute estranho")

    monkeypatch.setattr(pad, "padronizar", quebra)
    assert "ValueError: leiaute estranho" in diagnostico.executar("EXMP3")
