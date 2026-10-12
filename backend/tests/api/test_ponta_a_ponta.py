"""Ingestão de amostras → padronização → indicadores → API, conferindo valores calculados à mão."""

import io
import zipfile

import pytest
from fastapi.testclient import TestClient

from app.db.sessao import obter_sessao
from app.ingestao import cotahist, cvm_demonstracoes
from app.ingestao.base import lote
from app.ingestao.padronizacao_db import padronizar_todas
from app.main import app
from app.servicos.indicadores import recalcular
from tests import amostras
from tests.ingestao.test_conectores import carregar_companhias

RECEITAS = {2019: 5000, 2020: 5500, 2021: 6000, 2022: 6800, 2023: 7400, 2024: 8000}  # R$ mil


@pytest.fixture
def cliente(sessao):
    carregar_companhias(sessao)
    for ano, receita in RECEITAS.items():
        with zipfile.ZipFile(io.BytesIO(amostras.zip_dfp(ano, receita, 1000))) as z, lote(sessao, "CVM_DFP") as ctx:
            cvm_demonstracoes.processar_zip(ctx, z, "DFP", ano)
    padronizar_todas(sessao)
    texto = "\n".join([amostras.linha_cotahist("20250102", "EXMP3", 10.0, 5_000_000),
                       amostras.linha_cotahist("20250102", "EXMP4", 12.0, 9_000_000)])
    with lote(sessao, "B3_COTAHIST") as ctx:
        cotahist.gravar(ctx, cotahist.parse(texto))
    recalcular(sessao)

    app.dependency_overrides[obter_sessao] = lambda: sessao
    yield TestClient(app)
    app.dependency_overrides.clear()


def indicadores(dados):
    return {n["metrica"]: n for grupo in dados["grupos"].values() for n in grupo}


def test_indicadores_da_acao(cliente):
    resposta = cliente.get("/acoes/exmp3")
    assert resposta.status_code == 200
    dados = resposta.json()
    assert dados["nome"] == "EMPRESA EXEMPLO S.A." and dados["outros_tickers"] == ["EXMP4"]
    ind = indicadores(dados)
    # lucro R$ 1.000.000; 1.000.000 de ações; cotação EXMP3 R$ 10
    assert ind["basico.p_l"]["valor"] == pytest.approx(10)
    assert ind["basico.lpa"]["valor"] == pytest.approx(1)
    assert ind["basico.p_vp"]["valor"] == pytest.approx(2)  # PL R$ 5.000.000
    assert ind["basico.roe"]["valor"] == pytest.approx(0.2)
    assert ind["basico.margem_liquida"]["valor"] == pytest.approx(0.125)
    # valor de mercado = 600 mil × 10 + 400 mil × 12
    assert ind["basico.valor_mercado"]["valor"] == pytest.approx(10_800_000)
    assert ind["basico.divida_liquida"]["valor"] == pytest.approx(1_400_000)
    assert ind["basico.ev_ebitda"]["valor"] == pytest.approx(12_200_000 / 1_900_000)
    assert ind["basico.liquidez_corrente"]["valor"] == pytest.approx(2)
    assert ind["basico.cagr_receita_5a"]["valor"] == pytest.approx((8000 / 5000) ** 0.2 - 1)
    assert ind["basico.liquidez_diaria"]["valor"] == pytest.approx(5_000_000)
    # sem proventos ingeridos: indisponível com motivo, nunca estimado
    assert ind["basico.dy"]["valor"] is None
    assert "dividendos" in ind["basico.dy"]["motivo_indisponivel"]
    # procedência de cada insumo
    fontes = {p["fonte"] for p in ind["basico.p_l"]["procedencia"]}
    assert fontes == {"B3_COTAHIST", "CVM_DFP"}
    lucro = next(p for p in ind["basico.p_l"]["procedencia"] if p["insumo"] == "lucro_liquido_controladores")
    assert lucro["data_referencia"] == "2024-12-31" and lucro["contas"][0]["conta"] == "3.11.01"


def test_pl_por_ticker_usa_a_propria_cotacao(cliente):
    ind = indicadores(cliente.get("/acoes/EXMP4").json())
    assert ind["basico.p_l"]["valor"] == pytest.approx(12)


def test_busca_so_lista_quando_digita(cliente):
    assert cliente.get("/acoes").json() == []  # sem busca não lista nada
    assert cliente.get("/acoes", params={"busca": "e"}).json() == []  # mínimo de 2 letras
    por_ticker = cliente.get("/acoes", params={"busca": "exmp"}).json()
    assert [a["ticker"] for a in por_ticker] == ["EXMP3", "EXMP4"]
    exmp3 = por_ticker[0]
    assert exmp3["cotacao"]["fonte"] == "B3_COTAHIST"
    assert exmp3["indicadores"]["basico.p_l"]["valor"] == pytest.approx(10)
    por_nome = cliente.get("/acoes", params={"busca": "banco exemplo"}).json()
    assert [a["ticker"] for a in por_nome] == ["BEXM3"]
    assert cliente.get("/acoes/NAOEXISTE").status_code == 404
    assert cliente.get("/fiis/EXMP3").status_code == 404
    assert len(cliente.get("/ativos/EXMP3/cotacoes").json()) == 1


def test_ranking_graham(cliente):
    r = cliente.get("/ranking/acoes", params={"metodo": "graham"}).json()
    assert "Não constituem recomendação" in r["aviso"]
    # LPA 1, VPA 5 → √(22,5 × 1 × 5) = 10,61; EXMP3 a R$ 10 tem desconto, EXMP4 a R$ 12 não
    primeiro = r["itens"][0]
    assert primeiro["ticker"] == "EXMP3" and primeiro["posicao"] == 1
    assert primeiro["valor_justo"] == pytest.approx((22.5 * 5) ** 0.5)
    assert primeiro["desconto"] == pytest.approx(1 - 10 / (22.5 * 5) ** 0.5)
    assert r["itens"][1]["desconto"] < 0
    assert r["excluidos"]["sem cotação"] == 1  # BEXM3
    # parâmetro do usuário: Taxa Graham 10 → √50 = 7,07 (as duas ficam acima do valor)
    r2 = cliente.get("/ranking/acoes", params={"metodo": "graham", "fator_graham": 10}).json()
    assert r2["itens"][0]["valor_justo"] == pytest.approx(50 ** 0.5)
    # liquidez mínima acima da de todos → ranking vazio
    r3 = cliente.get("/ranking/acoes", params={"metodo": "graham", "liquidez_minima": 1e9}).json()
    assert r3["itens"] == [] and r3["excluidos"]["liquidez abaixo do mínimo"] == 2


def test_ranking_greenblatt_e_exclusoes(cliente):
    padrao = cliente.get("/ranking/acoes", params={"metodo": "greenblatt"}).json()
    assert padrao["itens"] == [] and padrao["excluidos"]["utility"] == 2  # setor Energia Elétrica
    r = cliente.get("/ranking/acoes", params={"metodo": "greenblatt", "excluir_utilities": False}).json()
    item = r["itens"][0]
    # EBIT 1,6 mi; EV 12,2 mi; capital = (3,0 − 0,6) − (1,5 − 0,4) + 2,0 imobilizado = 3,3 mi
    assert item["earnings_yield"] == pytest.approx(1.6 / 12.2)
    assert item["retorno_capital"] == pytest.approx(1.6 / 3.3)
    assert item["soma_posicoes"] >= 2


def test_ranking_bazin_e_lynch_sem_dados(cliente):
    bazin = cliente.get("/ranking/acoes", params={"metodo": "bazin"}).json()
    assert bazin["itens"] == [] and "proventos não ingeridos" in bazin["excluidos"]
    lynch = cliente.get("/ranking/acoes", params={"metodo": "lynch"}).json()
    assert lynch["itens"] == []  # lucro estável → crescimento 0, preço justo de Lynch não se aplica
    assert cliente.get("/ranking/acoes", params={"metodo": "xyz"}).status_code == 422


def test_metodos_na_pagina_do_ativo(cliente):
    ind = indicadores(cliente.get("/acoes/EXMP3").json())
    assert ind["graham.valor_intrinseco"]["valor"] == pytest.approx((22.5 * 5) ** 0.5)
    assert ind["greenblatt.retorno_capital"]["valor"] == pytest.approx(1.6 / 3.3)
    assert ind["bazin.preco_teto"]["valor"] is None
    assert "dcf.valor" not in ind  # métodos sob demanda não aparecem como card


def test_status_dos_dados(cliente):
    s = cliente.get("/status").json()
    fontes = {f["fonte"]: f for f in s["fontes"]}
    assert fontes["CVM_DFP"]["status"] == "concluido" and fontes["BCB_SGS"]["status"] == "nunca executado"
    assert s["contagens"]["acoes_com_cotacao"] == 2 and s["contagens"]["empresas_com_balanco"] == 1


def test_banco_indicadores_nao_aplicaveis(cliente, sessao):
    from sqlalchemy import select

    from app.db.modelos import Ativo, IndicadorCalculado
    banco = sessao.scalar(select(Ativo).where(Ativo.ticker == "BEXM3"))
    ev = sessao.scalar(select(IndicadorCalculado).where(IndicadorCalculado.ativo_id == banco.id,
                                                        IndicadorCalculado.metrica == "basico.ev_ebitda"))
    assert ev.valor is None and "bancos" in ev.motivo_indisponivel


def test_metodologias(cliente):
    todas = cliente.get("/metodologias").json()
    assert any(m["id"] == "basico.p_l" for m in todas)
    roic = cliente.get("/metodologias/basico.roic").json()
    assert roic["parametros"][0]["padrao"] == 0.34
    assert cliente.get("/metodologias/nada").status_code == 404


def test_autenticacao(cliente):
    r = cliente.post("/auth/registrar", json={"email": "Eu@Exemplo.com", "senha": "senha-forte-1"})
    assert r.status_code == 201 and r.json()["email"] == "eu@exemplo.com"
    assert cliente.get("/auth/eu").status_code == 200
    assert cliente.post("/auth/registrar", json={"email": "eu@exemplo.com", "senha": "outra-senha"}).status_code == 409
    cliente.post("/auth/sair")
    cliente.cookies.clear()
    assert cliente.get("/auth/eu").status_code == 401
    assert cliente.post("/auth/entrar", json={"email": "eu@exemplo.com", "senha": "errada!!"}).status_code == 401
    assert cliente.post("/auth/entrar", json={"email": "eu@exemplo.com", "senha": "senha-forte-1"}).status_code == 200
    assert cliente.post("/auth/registrar", json={"email": "x@y.com", "senha": "curta"}).status_code == 422
    assert cliente.post("/auth/registrar", json={"email": "invalido", "senha": "senha-longa"}).status_code == 422


def test_series_e_tesouro(cliente):
    assert cliente.get("/series/CDI").json()["pontos"] == []
    assert cliente.get("/series/XYZ").status_code == 404
    assert cliente.get("/tesouro/taxas").json()["titulos"] == []
    assert cliente.get("/saude").json() == {"status": "ok"}


def test_dy_usa_jcp_liquido_e_data_de_pagamento(cliente, sessao, monkeypatch):
    from app.config import obter_configuracao
    monkeypatch.setattr(obter_configuracao(), "fonte_mercado", "b3")  # regra da B3: data de pagamento e JCP
    from datetime import date
    from decimal import Decimal

    from sqlalchemy import select

    from app.db.modelos import Ativo, Provento
    from app.ingestao.base import lote as abrir_lote

    ativo_id = sessao.scalar(select(Ativo.id).where(Ativo.ticker == "EXMP3"))
    # cotação de 02/01/2025 → janela de pagamento (03/01/2024, 02/01/2025]
    casos = (
        ("DIVIDENDO", "0.50", date(2024, 12, 20), date(2025, 1, 15)),  # pago depois: não entra
        ("JCP", "0.20", date(2024, 6, 20), date(2024, 7, 10)),  # entra líquido: 0,17
        ("DIVIDENDO", "0.30", date(2023, 12, 1), date(2024, 2, 1)),  # data-com antiga, pago na janela: entra
        ("DIVIDENDO", "9.99", date(2022, 12, 1), date(2023, 3, 1)),  # fora da janela
        ("DIVIDENDO", "1.00", date(2024, 11, 1), None),  # sem data de pagamento: não entra
    )
    with abrir_lote(sessao, "B3_PROVENTOS") as ctx:
        for tipo, valor, data_com, pagamento in casos:
            sessao.add(Provento(ativo_id=ativo_id, tipo=tipo, valor_por_cota=Decimal(valor), data_com=data_com,
                                data_pagamento=pagamento, **ctx.procedencia(data_com)))
    recalcular(sessao, ["EXMP3"])
    ind = indicadores(cliente.get("/acoes/EXMP3").json())
    # (0,20 × 0,85 + 0,30) ÷ R$ 10
    assert ind["basico.dy"]["valor"] == pytest.approx(0.047)
    assert ind["basico.payout"]["valor"] == pytest.approx(0.47)  # LPA = 1
    pagos = {p["data_pagamento"] for p in ind["basico.dy"]["procedencia"] if p["insumo"] == "provento"}
    assert pagos == {"2024-07-10", "2024-02-01"}
