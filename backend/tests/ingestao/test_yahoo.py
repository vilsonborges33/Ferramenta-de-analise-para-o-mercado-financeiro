"""Yahoo Finance: resposta simulada no formato do endpoint /v8/finance/chart."""

from datetime import date
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import select

from app.config import obter_configuracao
from app.db.modelos import Ativo, CotacaoDiaria, LoteIngestao, Provento
from app.ingestao import cvm_fii, yahoo
from app.ingestao.base import EsquemaInesperado, lote
from app.servicos.indicadores import Calculadora

# 02/01/2025 e 03/01/2025, 13:00 UTC (abertura do pregão); dividendo com data-ex em 20/12/2024
RESPOSTA = {"chart": {"error": None, "result": [{
    "meta": {"currency": "BRL", "symbol": "EXMP3.SA", "gmtoffset": -10800, "exchangeTimezoneName": "America/Sao_Paulo"},
    "timestamp": [1735822800, 1735909200, 1735995600],
    "events": {"dividends": {"1734696000": {"amount": 0.5, "date": 1734696000},
                             "1700000000": {"amount": 0, "date": 1700000000}}},
    "indicators": {"quote": [{"open": [10.0, 10.2, None], "high": [10.5, 10.6, None], "low": [9.9, 10.0, None],
                              "close": [10.4, 10.5, None], "volume": [1000, 2000, None]}],
                   "adjclose": [{"adjclose": [10.1, 10.2, None]}]},
}]}}


def test_parse():
    dados = yahoo.parse(RESPOSTA)
    assert [c["data"] for c in dados["cotacoes"]] == [date(2025, 1, 2), date(2025, 1, 3)]  # pregão sem preço sai
    primeira = dados["cotacoes"][0]
    assert primeira["fechamento"] == Decimal("10.4") and primeira["volume_financeiro"] == Decimal("10400.0")
    assert dados["dividendos"] == [{"tipo": "DIVIDENDO", "valor_por_cota": Decimal("0.5"),
                                    "data_ex": date(2024, 12, 20), "data_com": date(2024, 12, 19),
                                    "data_pagamento": None, "data_aprovacao": None}]
    assert yahoo.parse(RESPOSTA, "FII")["dividendos"][0]["tipo"] == "RENDIMENTO_FII"
    with pytest.raises(EsquemaInesperado, match="Not Found"):
        yahoo.parse({"chart": {"result": None, "error": {"code": "Not Found", "description": "No data found"}}})
    with pytest.raises(EsquemaInesperado):
        yahoo.parse({"chart": {"result": []}})


def test_dia_util_anterior():
    assert yahoo.dia_util_anterior(date(2025, 1, 6)) == date(2025, 1, 3)  # segunda → sexta
    assert yahoo.simbolo("petr4") == "PETR4.SA"


def test_ingerir_com_ticker_inexistente_e_falha(sessao):
    sessao.add_all([Ativo(ticker="EXMP3", classe="ACAO"), Ativo(ticker="NADA3", classe="ACAO"),
                    Ativo(ticker="ERRO3", classe="ACAO"), Ativo(ticker="HGLG11", classe="FII")])
    sessao.commit()

    def responder(request):
        url = str(request.url)
        assert "Mozilla" in request.headers["user-agent"]
        if "NADA3" in url:
            return httpx.Response(404, json={"chart": {"result": None, "error": {"code": "Not Found"}}})
        if "ERRO3" in url:
            return httpx.Response(500)
        return httpx.Response(200, json=RESPOSTA)

    total = yahoo.ingerir(sessao, intervalo="6y", cliente=httpx.Client(transport=httpx.MockTransport(responder)),
                          pausa=0)
    assert total == 6  # 2 cotações + 1 dividendo, para EXMP3 e HGLG11
    assert sessao.query(CotacaoDiaria).count() == 4
    tipos = {p.tipo for p in sessao.scalars(select(Provento))}
    assert tipos == {"DIVIDENDO", "RENDIMENTO_FII"}
    ultimo = sessao.scalars(select(LoteIngestao).order_by(LoteIngestao.id.desc())).first()
    assert ultimo.status == "concluido" and "NADA3" in ultimo.erro and "ERRO3" in ultimo.erro
    # reprocessar não duplica
    yahoo.ingerir(sessao, ["EXMP3"], cliente=httpx.Client(transport=httpx.MockTransport(responder)), pausa=0)
    assert sessao.query(Provento).count() == 2


def test_429_tenta_de_novo(sessao):
    sessao.add(Ativo(ticker="EXMP3", classe="ACAO"))
    sessao.commit()
    respostas = [httpx.Response(429), httpx.Response(200, json=RESPOSTA)]
    cliente = httpx.Client(transport=httpx.MockTransport(lambda r: respostas.pop(0)))
    resposta = yahoo._consultar(cliente, "EXMP3", "5d", espera=0)
    assert resposta.status_code == 200


def test_fii_ganha_ticker_pelo_isin(sessao):
    assert cvm_fii.ticker_pelo_isin("BRHGLGCTF004") == "HGLG11"
    assert cvm_fii.ticker_pelo_isin("BRPETRACNOR9") is None and cvm_fii.ticker_pelo_isin(None) is None
    fundos = [{"cnpj": "11.728.688/0001-47", "nome": "FII", "isin": "BRHGLGCTF004", "segmento": None,
               "mandato": None, "tipo_gestao": None, "administrador": None, "publico_alvo": None,
               "data_inicio": None, "data_referencia": date(2025, 1, 1)}]
    with lote(sessao, "CVM_FII_MENSAL") as ctx:
        cvm_fii.gravar(ctx, fundos, [])
    ativo = sessao.scalar(select(Ativo).where(Ativo.ticker == "HGLG11"))
    assert ativo.classe == "FII" and ativo.isin == "BRHGLGCTF004"
    from app.db.modelos import Fii
    assert sessao.scalar(select(Fii.ativo_id)) == ativo.id


def test_dy_com_yahoo_usa_data_ex_e_ignora_outras_fontes(sessao):
    assert obter_configuracao().fonte_mercado == "yahoo"
    sessao.add(Ativo(ticker="EXMP3", classe="ACAO"))
    sessao.commit()
    ativo_id = sessao.scalar(select(Ativo.id))
    ref = date(2025, 1, 3)
    with lote(sessao, "YAHOO_FINANCE") as ctx:
        sessao.add(Provento(ativo_id=ativo_id, tipo="DIVIDENDO", valor_por_cota=Decimal("0.5"),
                            data_ex=date(2024, 12, 20), data_com=date(2024, 12, 19), **ctx.procedencia(ref)))
        ctx.lote.linhas_gravadas = 1
    with lote(sessao, "B3_PROVENTOS") as ctx:  # mesmo provento vindo de outra fonte: não pode somar duas vezes
        sessao.add(Provento(ativo_id=ativo_id, tipo="DIVIDENDO", valor_por_cota=Decimal("0.5"), data_ex=None,
                            data_com=date(2024, 12, 20), data_pagamento=date(2024, 12, 30), **ctx.procedencia(ref)))
    soma, lista, motivo = Calculadora(sessao).proventos_12m(ativo_id, ref)
    assert motivo is None and soma == pytest.approx(0.5) and len(lista) == 1


def test_isin_em_coluna_com_outro_nome():
    assert cvm_fii._isin({"Codigo_ISIN_Classe": "brtrxfctf001"}) == "BRTRXFCTF001"
    assert cvm_fii._isin({"ISIN": "  "}) is None and cvm_fii._isin({"Nome": "BRTRXFCTF001"}) is None
