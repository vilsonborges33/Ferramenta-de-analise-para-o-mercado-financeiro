"""Proventos: B3 (ações) e FNET (rendimentos de FII). Respostas simuladas no formato das fontes."""

import base64
import json
from datetime import date, timedelta
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import select

from app.db.modelos import Ativo, Fii, FiiDocumento, IndicadorCalculado, LoteIngestao, Provento
from app.ingestao import b3_proventos, fnet_rendimentos
from app.ingestao.base import EsquemaInesperado, lote
from app.servicos.indicadores import recalcular

RESPOSTA_B3 = [{
    "stockCapital": "1000000",
    "cashDividends": [
        {"assetIssued": "BREXMPACNOR0", "paymentDate": "15/01/2025", "rate": "0,50000000000", "relatedTo": "",
         "approvedOn": "10/12/2024", "isinCode": "BREXMPACNOR0", "label": "DIVIDENDO", "lastDatePrior": "20/12/2024"},
        {"assetIssued": "BREXMPACNOR0", "paymentDate": "", "rate": "0,2", "isinCode": "BREXMPACNOR0",
         "label": "JRS CAP PROPRIO", "lastDatePrior": "20/06/2025", "approvedOn": "01/06/2025"},
        {"assetIssued": "BREXMPACNPR0", "paymentDate": "15/01/2025", "rate": "0,55", "isinCode": "BREXMPACNPR0",
         "label": "DIVIDENDO", "lastDatePrior": "20/12/2024"},
        {"isinCode": "BREXMPACNOR0", "rate": "1,0", "label": "BONIFICACAO", "lastDatePrior": "01/01/2024"},
        {"isinCode": "BRDESCONHEC0", "rate": "1,0", "label": "DIVIDENDO", "lastDatePrior": "01/01/2024"},
    ],
    "stockDividends": [],
}]


def test_b3_parse():
    registros = b3_proventos.parse(RESPOSTA_B3)
    assert len(registros) == 4  # bonificação em ações fica de fora
    div = registros[0]
    assert div == {"isin": "BREXMPACNOR0", "tipo": "DIVIDENDO", "valor_por_cota": Decimal("0.5"),
                   "data_com": date(2024, 12, 20), "data_aprovacao": date(2024, 12, 10),
                   "data_pagamento": date(2025, 1, 15)}
    assert registros[1]["tipo"] == "JCP" and registros[1]["data_pagamento"] is None
    assert b3_proventos.parse([]) == [] and b3_proventos.parse(None) == []
    with pytest.raises(EsquemaInesperado):
        b3_proventos.parse(["texto"])
    assert b3_proventos.tipo_provento("RENDIMENTO") == "RENDIMENTO_FII"
    assert b3_proventos.tipo_provento("AMORTIZAÇÃO") == "AMORTIZACAO"


def test_b3_url_codifica_parametro():
    url = b3_proventos.url_empresa("PETR")
    param = url.rsplit("/", 1)[-1]
    assert json.loads(base64.b64decode(param)) == {"issuingCompany": "PETR", "language": "pt-br"}


def _ativos(sessao):
    sessao.add_all([Ativo(ticker="EXMP3", classe="ACAO", especie="ON", isin="BREXMPACNOR0"),
                    Ativo(ticker="EXMP4", classe="ACAO", especie="PN", isin="BREXMPACNPR0"),
                    Ativo(ticker="ZZZZ3", classe="ACAO", especie="ON", isin="BRZZZZACNOR0")])
    sessao.commit()


def test_b3_ingerir_com_falha_isolada(sessao):
    _ativos(sessao)

    def responder(request):
        if "ZZZZ" in base64.b64decode(str(request.url).rsplit("/", 1)[-1]).decode():
            return httpx.Response(500)
        return httpx.Response(200, json=RESPOSTA_B3)

    total = b3_proventos.ingerir(sessao, cliente=httpx.Client(transport=httpx.MockTransport(responder)), pausa=0)
    assert total == 3  # EXMP3 (2) + EXMP4 (1); ISIN desconhecido ignorado
    lote_b3 = sessao.scalars(select(LoteIngestao).order_by(LoteIngestao.id.desc())).first()
    assert lote_b3.status == "concluido" and "ZZZZ" in lote_b3.erro
    # reprocessar com a data de pagamento divulgada atualiza o registro, sem duplicar
    atualizado = json.loads(json.dumps(RESPOSTA_B3))
    atualizado[0]["cashDividends"][1]["paymentDate"] = "10/07/2025"
    b3_proventos.ingerir(sessao, ["EXMP"], cliente=httpx.Client(transport=httpx.MockTransport(
        lambda r: httpx.Response(200, json=atualizado))), pausa=0)
    jcp = sessao.scalar(select(Provento).where(Provento.tipo == "JCP"))
    assert jcp.data_pagamento == date(2025, 7, 10) and sessao.query(Provento).count() == 3


def test_b3_todas_falham_registra_erro(sessao):
    _ativos(sessao)
    with pytest.raises(RuntimeError):
        b3_proventos.ingerir(sessao, cliente=httpx.Client(transport=httpx.MockTransport(
            lambda r: httpx.Response(503))), pausa=0)
    assert sessao.scalars(select(LoteIngestao).order_by(LoteIngestao.id.desc())).first().status == "erro"


XML_FNET = """<?xml version="1.0" encoding="UTF-8"?>
<DadosEconomicoFinanceiros xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <DadosGerais>
    <NomeFundo>FII EXEMPLO</NomeFundo><CNPJFundo>11728688000147</CNPJFundo>
    <CodigoISIN>BRHGLGCTF004</CodigoISIN><CodNegociacao>HGLG11</CodNegociacao>
  </DadosGerais>
  <InformeRendimentos>
    <Rendimento>
      <DataAprovacao>2025-01-31</DataAprovacao><DataBase>2025-01-31</DataBase>
      <DataPagamento>2025-02-14</DataPagamento><ValorProventoCota>1.10</ValorProventoCota>
    </Rendimento>
    <Amortizacao><DataBase>2025-01-31</DataBase><DataPagamento>2025-02-14</DataPagamento>
      <ValorProventoCota>0</ValorProventoCota></Amortizacao>
  </InformeRendimentos>
</DadosEconomicoFinanceiros>"""


def test_fnet_parse_e_decodificacao():
    assert fnet_rendimentos.decodificar(XML_FNET.encode()).startswith(b"<?xml")
    codificado = b'"' + base64.b64encode(XML_FNET.encode()) + b'"'
    doc = fnet_rendimentos.parse_documento(fnet_rendimentos.decodificar(codificado))
    assert doc["cnpj"] == "11728688000147" and doc["ticker"] == "HGLG11"
    assert doc["eventos"] == [{"tipo": "RENDIMENTO_FII", "valor_por_cota": Decimal("1.10"),
                               "data_com": date(2025, 1, 31), "data_pagamento": date(2025, 2, 14),
                               "data_aprovacao": date(2025, 1, 31)}]  # amortização zero ignorada
    with pytest.raises(EsquemaInesperado):
        fnet_rendimentos.parse_documento(b"<nao fecha")


def _cliente_fnet(total_docs=2, falhar_id=None):
    def responder(request):
        if "pesquisarGerenciadorDocumentosDados" in str(request.url):
            inicio = int(request.url.params["s"])
            dados = [{"id": 1000 + i, "dataEntrega": "05/02/2025 18:00"} for i in range(total_docs)][inicio:inicio + 1]
            return httpx.Response(200, json={"recordsTotal": total_docs, "data": dados})
        if falhar_id and str(falhar_id) in str(request.url):
            return httpx.Response(500)
        return httpx.Response(200, content=base64.b64encode(XML_FNET.encode()))
    return httpx.Client(transport=httpx.MockTransport(responder))


def test_fnet_ingerir(sessao, monkeypatch):
    monkeypatch.setattr(fnet_rendimentos, "POR_PAGINA", 1)  # força a paginação
    sessao.add(Ativo(ticker="HGLG11", classe="FII", isin="BRHGLGCTF004"))
    sessao.flush()
    with lote(sessao, "CVM_FII_MENSAL") as ctx:
        sessao.add(Fii(cnpj="11.728.688/0001-47", nome="FII EXEMPLO", isin="BRHGLGCTF004",
                       ativo_id=sessao.scalar(select(Ativo.id)), **ctx.procedencia(date(2025, 1, 1))))
    total = fnet_rendimentos.ingerir(sessao, cliente=_cliente_fnet(total_docs=2, falhar_id=1001), pausa=0)
    assert total == 1 and sessao.query(Provento).count() == 1
    assert sessao.scalar(select(FiiDocumento.id_fnet)) == "1000"
    # nova execução: o documento 1000 não é baixado de novo; o 1001 é tentado outra vez
    total2 = fnet_rendimentos.ingerir(sessao, cliente=_cliente_fnet(total_docs=2), pausa=0)
    assert total2 == 1 and sessao.query(FiiDocumento).count() == 2
    assert sessao.query(Provento).count() == 1  # mesmo evento nos dois documentos: sem duplicar


def test_dy_zero_quando_fonte_carregou_e_nao_ha_provento(sessao):
    _ativos(sessao)
    hoje = date.today()
    with lote(sessao, "B3_COTAHIST") as ctx:
        from app.db.modelos import CotacaoDiaria
        for a in sessao.scalars(select(Ativo)):
            sessao.add(CotacaoDiaria(ativo_id=a.id, data=hoje, fechamento=Decimal("10"), **ctx.procedencia(hoje)))
    with lote(sessao, "B3_PROVENTOS") as ctx:
        sessao.add(Provento(ativo_id=sessao.scalar(select(Ativo.id).where(Ativo.ticker == "EXMP3")), tipo="DIVIDENDO",
                            valor_por_cota=Decimal("0.8"), data_com=hoje - timedelta(days=40),
                            data_pagamento=hoje - timedelta(days=10), **ctx.procedencia(hoje)))
        ctx.lote.linhas_gravadas = 1
    from app.servicos.indicadores import Calculadora
    calc = Calculadora(sessao)
    soma, lista, motivo = calc.proventos_12m(sessao.scalar(select(Ativo.id).where(Ativo.ticker == "ZZZZ3")), hoje)
    assert motivo is None and soma == 0  # fonte carregada, nenhum provento → DY 0
    soma3, _, _ = calc.proventos_12m(sessao.scalar(select(Ativo.id).where(Ativo.ticker == "EXMP3")), hoje)
    assert soma3 == pytest.approx(0.8)
    _, _, motivo_fii = calc.proventos_12m(sessao.scalar(select(Ativo.id).where(Ativo.ticker == "EXMP4")), hoje, "FII")
    assert motivo_fii and "FNET" in motivo_fii  # FNET ainda não carregou
    assert recalcular(sessao) >= 0
    assert sessao.query(IndicadorCalculado).count() == 0  # ativos sem empresa: nada a materializar
