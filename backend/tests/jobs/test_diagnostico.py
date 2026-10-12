import httpx

from app.ingestao import yahoo
from app.jobs import diagnostico
from tests.ingestao.test_conectores import carregar_companhias
from tests.ingestao.test_yahoo import RESPOSTA


def test_diagnostico_resume_e_testa_yahoo(sessao, monkeypatch):
    carregar_companhias(sessao)
    monkeypatch.setattr(diagnostico, "cliente_http",
                        lambda: httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=RESPOSTA))))
    texto = diagnostico.executar("EXMP3")
    assert "fonte de mercado: yahoo" in texto
    assert "CVM_CADASTRO: concluido" in texto and "YAHOO_FINANCE: nunca executado" in texto
    assert "última cotação: nenhuma" in texto and "basico.lpa: não calculado" in texto
    assert "HTTP 200" in texto and "2 pregões" in texto
    assert "ticker não cadastrado" in diagnostico.executar("NADA3")
    assert yahoo.simbolo("EXMP3") in texto
