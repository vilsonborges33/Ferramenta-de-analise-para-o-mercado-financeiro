"""Regressões encontradas na primeira carga com dados reais (11/10/2026)."""

from datetime import date

import httpx
from sqlalchemy import select

from app.db.modelos import Ativo, Fii, LoteIngestao
from app.ingestao import bcb_sgs, brapi, cotahist
from app.ingestao.base import ArquivoIndisponivel, lote
from app.ingestao.padronizacao import padronizar
from app.jobs import tarefas
from tests.ingestao.test_conectores import carregar_companhias
from tests.ingestao.test_padronizacao import linha


def test_dois_dfp_no_mesmo_ano_geram_um_periodo():
    # empresa que mudou o encerramento do exercício: DFP em 30/09/2022 e em 31/12/2022
    linhas = [
        linha("DFP", "DRE", "3.01", "Receita", 66, date(2022, 9, 30), date(2022, 1, 1)),
        linha("DFP", "DRE", "3.01", "Receita", 82, date(2022, 12, 31), date(2022, 1, 1)),
    ]
    anuais = [p for p in padronizar(linhas) if p.tipo_periodo == "ano"]
    assert len(anuais) == 1 and anuais[0].campos["receita_liquida"] == 82


def test_fii_com_isin_repetido_liga_so_um(sessao):
    sessao.add(Ativo(ticker="ABCD11", classe="FII", isin="BRABCDCTF000"))
    with lote(sessao, "CVM_FII_MENSAL") as ctx:
        for cnpj, ref in (("11.111.111/0001-11", date(2024, 1, 1)), ("22.222.222/0001-22", date(2025, 1, 1))):
            sessao.add(Fii(cnpj=cnpj, nome="FUNDO", isin="BRABCDCTF000", **ctx.procedencia(ref)))
    cotahist.ligar_fiis_por_isin(sessao)  # antes: UniqueViolation em fii.ativo_id
    ligados = sessao.scalars(select(Fii).where(Fii.ativo_id.is_not(None))).all()
    assert [f.cnpj for f in ligados] == ["22.222.222/0001-22"]  # o cadastro mais recente
    cotahist.ligar_fiis_por_isin(sessao)  # repetir não quebra
    assert sessao.query(Fii).filter(Fii.ativo_id.is_not(None)).count() == 1


def test_arquivo_nao_publicado_vira_sem_arquivo(sessao):
    with lote(sessao, "B3_COTAHIST", "url") as _:
        raise ArquivoIndisponivel("arquivo não publicado (404): url")
    ultimo = sessao.scalars(select(LoteIngestao).order_by(LoteIngestao.id.desc())).first()
    assert ultimo.status == "sem_arquivo"
    assert cotahist.ingerir_dia(sessao, date(2026, 10, 11)) == 0  # domingo: nem tenta baixar


def _cliente(respostas):
    fila = list(respostas)

    def responder(request):
        status, corpo = fila.pop(0) if len(fila) > 1 else fila[0]
        return httpx.Response(status, content=corpo.encode())

    return httpx.Client(transport=httpx.MockTransport(responder))


def test_sgs_resposta_invalida_tenta_de_novo_e_nao_derruba():
    ok = '[{"data":"02/01/2025","valor":"0.05"}]'
    assert bcb_sgs.consultar(_cliente([(200, ""), (200, ok)]), 12, date(2025, 1, 1), date(2025, 1, 5),
                             espera=0) == [{"data": "02/01/2025", "valor": "0.05"}]
    assert bcb_sgs.consultar(_cliente([(200, "<html>")]), 12, date(2025, 1, 1), date(2025, 1, 5), espera=0) is None
    assert bcb_sgs.consultar(_cliente([(404, "")]), 12, date(2025, 1, 1), date(2025, 1, 5)) == []


def test_sgs_ingerir_registra_janela_falha(sessao):
    total = bcb_sgs.ingerir(sessao, "CDI", date(2025, 1, 1), date(2025, 1, 5), cliente=_cliente([(200, "")]))
    assert total == 0
    ultimo = sessao.scalars(select(LoteIngestao).order_by(LoteIngestao.id.desc())).first()
    assert ultimo.status == "concluido" and "sem resposta válida" in ultimo.erro


def test_brapi_pula_ticker_sem_permissao(sessao, monkeypatch):
    carregar_companhias(sessao)
    corpo = '{"results":[{"symbol":"EXMP3","regularMarketPrice":10.5,"regularMarketTime":"2025-01-03T20:00:00Z"}]}'

    def responder(request):
        if "EXMP4" in str(request.url):
            return httpx.Response(401, json={"error": True})
        return httpx.Response(200, content=corpo.encode())

    monkeypatch.setattr(brapi, "cliente_http", lambda: httpx.Client(transport=httpx.MockTransport(responder)))
    totais = brapi.ingerir(sessao, ["EXMP4", "EXMP3"])  # antes: o 401 abortava todos os tickers
    assert totais["cotacoes"] == 1
    ultimo = sessao.scalars(select(LoteIngestao).order_by(LoteIngestao.id.desc())).first()
    assert "EXMP4 (401)" in ultimo.erro


def test_trava_impede_duas_cargas_simultaneas(sessao):
    with tarefas.trava_exclusiva() as primeira:
        assert primeira is True
        with tarefas.trava_exclusiva() as segunda:
            assert segunda is False
    with tarefas.trava_exclusiva() as de_novo:
        assert de_novo is True


def test_carga_inicial_ignorada_se_ja_em_andamento(sessao, monkeypatch):
    chamadas = []
    monkeypatch.setattr(tarefas, "_carga_inicial", lambda de, ate: chamadas.append(1))
    with tarefas.trava_exclusiva():
        tarefas.carga_inicial(2020, 2026)
    assert chamadas == []
    tarefas.carga_inicial(2020, 2026)
    assert chamadas == [1]


