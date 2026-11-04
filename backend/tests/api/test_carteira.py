"""Fase 6: carteira (lançamentos, importação B3, resumo, rentabilidade, proventos, otimizador) e diário."""

import io
import math
from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import select

from app.db.modelos import Ativo, CotacaoDiaria, Provento, SerieEconomica
from app.ingestao.base import lote
from app.main import app
from tests.api.test_ponta_a_ponta import cliente as cliente_base  # noqa: F401  (fixture)

INICIO = date(2025, 2, 3)


def pregoes(n):
    d, saida = INICIO, []
    while len(saida) < n:
        if d.weekday() < 5:
            saida.append(d)
        d += timedelta(days=1)
    return saida


DIAS = pregoes(90)


def preco(ticker, i):  # séries determinísticas e pouco correlacionadas
    return 10 + i * 0.05 + math.sin(i / 3) if ticker == "EXMP3" else 12 + math.cos(i / 5) * 2 - i * 0.01


@pytest.fixture
def cliente(cliente_base, sessao):  # noqa: F811
    ativos = {a.ticker: a for a in sessao.scalars(select(Ativo).where(Ativo.ticker.in_(["EXMP3", "EXMP4"])))}
    with lote(sessao, "YAHOO_FINANCE") as ctx:
        for t, a in ativos.items():
            for i, d in enumerate(DIAS):
                sessao.add(CotacaoDiaria(ativo_id=a.id, data=d, fechamento=Decimal(str(round(preco(t, i), 4))),
                                         **ctx.procedencia(d)))
        sessao.add(Provento(ativo_id=ativos["EXMP3"].id, tipo="JCP", valor_por_cota=Decimal("1"), data_com=DIAS[10],
                            data_ex=DIAS[11], **ctx.procedencia(DIAS[10])))
        for i, d in enumerate(DIAS):
            sessao.add(SerieEconomica(codigo="IBOV", data=d, valor=Decimal(100000 + i * 100), **ctx.procedencia(d)))
    with lote(sessao, "BCB_SGS") as ctx:
        for d in DIAS:
            sessao.add(SerieEconomica(codigo="CDI", data=d, valor=Decimal("0.05"), **ctx.procedencia(d)))
    sessao.commit()
    cliente_base.post("/auth/registrar", json={"email": "cart@exemplo.com", "senha": "senha-forte-1"})
    return cliente_base


def criar(cliente, compras=(("EXMP3", 100, 10.0), ("EXMP4", 50, 12.0))):
    cid = cliente.post("/carteiras", json={"nome": "Principal"}).json()["id"]
    for t, q, p in compras:
        r = cliente.post(f"/carteiras/{cid}/lancamentos", json={"ticker": t, "tipo": "COMPRA",
                                                                "data": DIAS[0].isoformat(), "quantidade": q,
                                                                "preco": p})
        assert r.status_code == 201
    return cid


def test_exige_login_e_isola_usuarios(cliente_base, sessao):  # noqa: F811
    assert cliente_base.get("/carteiras").status_code == 401
    cliente_base.post("/auth/registrar", json={"email": "a@exemplo.com", "senha": "senha-forte-1"})
    cid = cliente_base.post("/carteiras", json={"nome": "A"}).json()["id"]
    outro = TestClient(app)
    outro.post("/auth/registrar", json={"email": "b@exemplo.com", "senha": "senha-forte-1"})
    assert outro.get(f"/carteiras/{cid}/resumo").status_code == 404 and outro.get("/carteiras").json() == []


def test_lancamentos_resumo_e_validacao(cliente):
    cid = criar(cliente)
    venda = {"ticker": "EXMP3", "tipo": "VENDA", "data": DIAS[5].isoformat(), "quantidade": 500, "preco": 11}
    assert "acima da posição" in cliente.post(f"/carteiras/{cid}/lancamentos", json=venda).json()["detail"]
    assert cliente.post(f"/carteiras/{cid}/lancamentos", json={**venda, "ticker": "XXXX3"}).status_code == 422
    r = cliente.get(f"/carteiras/{cid}/resumo").json()
    pos = {p["ticker"]: p for p in r["posicoes"]}
    ultimo3, ultimo4 = round(preco("EXMP3", 89), 4), round(preco("EXMP4", 89), 4)
    assert pos["EXMP3"]["preco_medio"] == pytest.approx(10) and pos["EXMP3"]["valor"] == pytest.approx(100 * ultimo3)
    assert r["total_valor"] == pytest.approx(100 * ultimo3 + 50 * ultimo4)
    assert r["total_custo"] == pytest.approx(1600)
    assert sum(p["peso"] for p in r["posicoes"]) == pytest.approx(1)
    assert pos["EXMP3"]["proventos_recebidos"] == pytest.approx(85)  # JCP de R$ 1 com 15% de IR × 100
    # preço médio informado à mão
    cliente.put(f"/carteiras/{cid}/preco-medio/EXMP3", json={"preco_medio": 8, "motivo": "posição antiga"})
    pos = {p["ticker"]: p for p in cliente.get(f"/carteiras/{cid}/resumo").json()["posicoes"]}
    assert pos["EXMP3"]["preco_medio"] == 8 and pos["EXMP3"]["preco_medio_ajustado"]
    # apagar a compra que sustenta uma venda posterior é recusado
    cliente.post(f"/carteiras/{cid}/lancamentos", json={**venda, "quantidade": 100})
    compra = next(lan for lan in cliente.get(f"/carteiras/{cid}/lancamentos").json()
                  if lan["ticker"] == "EXMP3" and lan["tipo"] == "COMPRA")
    assert cliente.delete(f"/carteiras/{cid}/lancamentos/{compra['id']}").status_code == 422


def test_rentabilidade_proventos_e_indices(cliente):
    cid = criar(cliente, compras=(("EXMP3", 100, 10.0),))
    r = cliente.get(f"/carteiras/{cid}/rentabilidade").json()
    assert len(r["dias"]) == 90
    v0, vf = 100 * round(preco("EXMP3", 0), 4), 100 * round(preco("EXMP3", 89), 4)
    # sem aportes depois do início: retorno = (valor final + proventos) ÷ valor inicial, encadeado no dia do crédito
    v10, v11 = 100 * round(preco("EXMP3", 10), 4), 100 * round(preco("EXMP3", 11), 4)
    esperado = (v10 / v0) * ((v11 + 85) / v10) * (vf / v11) - 1
    assert r["carteira"][-1] == pytest.approx(esperado)
    assert r["indices"]["CDI"][-1] == pytest.approx(1.0005 ** 89 - 1)
    assert r["indices"]["IBOV"][-1] == pytest.approx((100000 + 8900) / 100000 - 1)
    assert r["periodos"]["Desde o início"]["carteira"] == pytest.approx(esperado)
    p = cliente.get(f"/carteiras/{cid}/proventos").json()
    assert p["total"] == pytest.approx(85) and p["itens"][0]["quantidade"] == 100


def test_otimizador(cliente):
    cid = criar(cliente)
    r = cliente.get(f"/carteiras/{cid}/otimizador", params={"anos": 1}).json()
    assert "Não constitui recomendação" in r["aviso"] or "não constitui recomendação" in r["aviso"]
    nomes = [c["nome"] for c in r["carteiras"]]
    assert nomes[0] == "Atual" and "Mínima variância" in nomes and "Paridade de risco" in nomes
    for c in r["carteiras"]:
        assert sum(c["pesos"].values()) == pytest.approx(1, abs=1e-4)
    assert len(r["correlacao"]) == 2 and r["correlacao"][0][0] == pytest.approx(1)
    minima = next(c for c in r["carteiras"] if c["nome"] == "Mínima variância")
    assert minima["volatilidade"] <= r["carteiras"][0]["volatilidade"] + 1e-9
    so_um = cliente.post("/carteiras", json={"nome": "Uma"}).json()["id"]
    assert "ao menos 2" in cliente.get(f"/carteiras/{so_um}/otimizador").json()["motivo"]


def planilha_negociacao():
    livro = Workbook()
    f = livro.active
    f.append(["Data do Negócio", "Tipo de Movimentação", "Mercado", "Prazo/Vencimento", "Instituição",
              "Código de Negociação", "Quantidade", "Preço", "Valor"])
    f.append([DIAS[0].strftime("%d/%m/%Y"), "Compra", "Mercado à Vista", "-", "X", "EXMP3", 10, 10.5, 105])
    f.append([DIAS[3].strftime("%d/%m/%Y"), "Compra", "Mercado Fracionário", "-", "X", "EXMP4F", 3, 12.0, 36])
    f.append([DIAS[4].strftime("%d/%m/%Y"), "Compra", "Mercado à Vista", "-", "X", "ZZZZ3", 1, 1.0, 1])
    saida = io.BytesIO()
    livro.save(saida)
    return saida.getvalue()


def test_importacao_b3(cliente):
    cid = cliente.post("/carteiras", json={"nome": "Importada"}).json()["id"]
    r = cliente.post(f"/carteiras/{cid}/importar", params={"nome_arquivo": "negociacao.xlsx"},
                     content=planilha_negociacao()).json()
    assert r["tipo_arquivo"] == "NEGOCIACAO" and r["importados"] == 2 and "ZZZZ3" in r["erros"][0]
    de_novo = cliente.post(f"/carteiras/{cid}/importar", content=planilha_negociacao()).json()
    assert de_novo["importados"] == 0 and de_novo["repetidos"] == 2
    origens = {lan["origem"] for lan in cliente.get(f"/carteiras/{cid}/lancamentos").json()}
    assert origens == {"b3"}
    assert cliente.post(f"/carteiras/{cid}/importar", content=b"nada").status_code == 422


def test_diario_de_decisoes(cliente):
    novo = cliente.post("/diario", json={"ticker": "exmp3", "data": "2025-01-10", "decisao": "Compra",
                                         "tese": "Desconto de 30% sobre o valor de Graham.",
                                         "premissas": {"crescimento": "5% a.a."},
                                         "data_revisao_prevista": "2025-07-10"}).json()
    assert novo["ticker"] == "EXMP3" and novo["revisao_pendente"]  # data de revisão já passou
    revisado = cliente.put(f"/diario/{novo['id']}", json={**{k: novo[k] for k in ("data", "decisao", "tese",
                                                                                 "premissas")},
                                                          "ticker": "EXMP3", "revisao": "Tese mantida."}).json()
    assert not revisado["revisao_pendente"] and revisado["revisao"] == "Tese mantida."
    assert len(cliente.get("/diario").json()) == 1
    assert cliente.delete(f"/diario/{novo['id']}").status_code == 204 and cliente.get("/diario").json() == []
