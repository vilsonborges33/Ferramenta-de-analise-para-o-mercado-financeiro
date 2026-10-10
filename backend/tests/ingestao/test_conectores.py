"""Conectores: parsing dos formatos e gravação com procedência (arquivos de amostra, valores fictícios)."""

import io
import zipfile
from datetime import date
from decimal import Decimal

import pandas as pd
import pytest
from sqlalchemy import select

from app.db.modelos import (
    Ativo,
    ComposicaoCapital,
    CotacaoDiaria,
    DemonstracaoLinha,
    Empresa,
    Fii,
    FiiInformeMensal,
    LoteIngestao,
    Provento,
    SerieEconomica,
    TituloTesouroTaxa,
)
from app.ingestao import bcb_sgs, brapi, cotahist, cvm_companhias, cvm_demonstracoes, cvm_fii, tesouro
from app.ingestao.base import EsquemaInesperado, data_br, decimal_br, lote
from tests import amostras


def test_conversoes_br():
    assert decimal_br("1.234,56") == Decimal("1234.56")
    assert decimal_br("1234.56") == Decimal("1234.56")
    assert decimal_br("") is None and decimal_br(None) is None and decimal_br("abc") is None
    assert data_br("31/12/2024") == date(2024, 12, 31)
    assert data_br("2024-12-31") == date(2024, 12, 31)
    assert data_br("") is None


def carregar_companhias(sessao):
    with lote(sessao, "CVM_CADASTRO") as ctx:
        cvm_companhias.gravar_cadastro(ctx, cvm_companhias.parse_cadastro(
            cvm_companhias.ler_csv_cvm(io.BytesIO(amostras.cadastro()))))
    with lote(sessao, "CVM_FCA") as ctx:
        cvm_companhias.gravar_valores_mobiliarios(ctx, cvm_companhias.parse_valores_mobiliarios(
            cvm_companhias.ler_csv_cvm(io.BytesIO(amostras.valores_mobiliarios()))))


def test_cadastro_e_tickers(sessao):
    carregar_companhias(sessao)
    empresas = {e.cnpj: e for e in sessao.scalars(select(Empresa))}
    assert empresas[amostras.CNPJ].codigo_cvm == "12345"
    assert empresas[amostras.CNPJ].tipo_plano_contas == "geral"
    assert empresas[amostras.CNPJ].segmento_listagem == "Novo Mercado"
    assert empresas["11.111.111/0001-11"].tipo_plano_contas == "banco"
    tickers = {a.ticker: a for a in sessao.scalars(select(Ativo))}
    assert set(tickers) == {"EXMP3", "EXMP4", "BEXM3"}  # debênture em balcão ignorada
    assert tickers["EXMP4"].especie == "PN"
    # procedência obrigatória
    e = empresas[amostras.CNPJ]
    assert e.fonte_id and e.lote_ingestao_id and e.coletado_em
    assert sessao.scalar(select(LoteIngestao).where(LoteIngestao.id == e.lote_ingestao_id)).status == "concluido"


def test_esquema_inesperado_falha_e_registra_lote(sessao):
    df = pd.DataFrame({"CNPJ_CIA": ["x"]})
    with pytest.raises(EsquemaInesperado), lote(sessao, "CVM_CADASTRO") as ctx:
        cvm_companhias.gravar_cadastro(ctx, cvm_companhias.parse_cadastro(df))
    ultimo = sessao.scalars(select(LoteIngestao).order_by(LoteIngestao.id.desc())).first()
    assert ultimo.status == "erro" and "colunas ausentes" in ultimo.erro


def test_demonstracoes_escala_e_composicao(sessao):
    carregar_companhias(sessao)
    with zipfile.ZipFile(io.BytesIO(amostras.zip_dfp(2024, 8000, 1000))) as z, lote(sessao, "CVM_DFP") as ctx:
        cvm_demonstracoes.processar_zip(ctx, z, "DFP", 2024)
    receita = sessao.scalar(select(DemonstracaoLinha).where(DemonstracaoLinha.conta_codigo == "3.01"))
    assert receita.valor == Decimal("8000000")  # escala MIL convertida para unidades
    assert receita.data_inicio == date(2024, 1, 1) and receita.consolidado
    capital = sessao.scalar(select(ComposicaoCapital))
    assert capital.acoes_ordinarias == 600000
    # reprocessar o mesmo arquivo não duplica
    total = sessao.query(DemonstracaoLinha).count()
    with zipfile.ZipFile(io.BytesIO(amostras.zip_dfp(2024, 8000, 1000))) as z, lote(sessao, "CVM_DFP") as ctx:
        cvm_demonstracoes.processar_zip(ctx, z, "DFP", 2024)
    assert sessao.query(DemonstracaoLinha).count() == total


def test_escala_desconhecida_falha():
    df = cvm_companhias.ler_csv_cvm(io.BytesIO(amostras._demo("DRE", "2024-12-31", "2024-01-01", "2024-12-31",
                                                              [("3.01", "Receita", 1)], escala="BILHAO")))
    with pytest.raises(ValueError, match="escala"):
        cvm_demonstracoes.parse_demonstracao(df, "DFP", "DRE", True)


def test_cotahist_parse_e_gravacao(sessao):
    carregar_companhias(sessao)
    texto = "\n".join([
        "00COTAHIST.2025BOVESPA 20250101" + " " * 214,
        amostras.linha_cotahist("20250102", "EXMP3", 10.0, 5_000_000),
        amostras.linha_cotahist("20250102", "EXMP4", 12.0, 9_000_000, isin="BREXMPACNPR0"),
        amostras.linha_cotahist("20250102", "EXMP3", 1000.0, 1, fator=100).replace("EXMP3       ", "OUTRO3      "),
        amostras.linha_cotahist("20250102", "HGLG11", 160.0, 7_000_000, codbdi="12", isin="BRHGLGCTF004"),
        "99COTAHIST.2025BOVESPA 20250101" + " " * 214,
    ])
    registros = cotahist.parse(texto)
    assert {r["ticker"] for r in registros} == {"EXMP3", "EXMP4", "OUTRO3", "HGLG11"}
    outro = next(r for r in registros if r["ticker"] == "OUTRO3")
    assert outro["fechamento"] == Decimal("10")  # fator de cotação 100 normalizado
    with lote(sessao, "B3_COTAHIST") as ctx:
        cotahist.criar_ativos_fii(ctx, registros)
        cotahist.gravar(ctx, registros)
    cot = sessao.scalar(select(CotacaoDiaria).join(Ativo).where(Ativo.ticker == "EXMP3"))
    assert cot.fechamento == Decimal("10") and cot.volume_financeiro == Decimal("5000000")
    assert sessao.scalar(select(Ativo).where(Ativo.ticker == "HGLG11")).classe == "FII"
    assert cotahist.parse(texto, {"EXMP4"})[0]["ticker"] == "EXMP4"


def test_cotahist_linha_curta():
    with pytest.raises(EsquemaInesperado):
        cotahist.parse_linha("01" + "x" * 100)


def test_bcb_janelas_e_gravacao(sessao):
    j = bcb_sgs.janelas(date(2000, 1, 1), date(2025, 1, 1))
    assert len(j) == 3 and j[0][0] == date(2000, 1, 1) and j[-1][1] == date(2025, 1, 1)
    assert all((fim - ini).days <= 3650 for ini, fim in j)
    pontos = bcb_sgs.parse([{"data": "02/01/2025", "valor": "0.045513"}, {"data": "03/01/2025", "valor": ""}])
    assert pontos == [(date(2025, 1, 2), Decimal("0.045513"))]
    with lote(sessao, "BCB_SGS") as ctx:
        bcb_sgs.gravar(ctx, "CDI", pontos)
        bcb_sgs.gravar(ctx, "CDI", pontos)  # idempotente
    assert sessao.query(SerieEconomica).count() == 1


def test_tesouro_parse(sessao):
    df = pd.DataFrame([{
        "Tipo Titulo": "Tesouro Prefixado", "Data Vencimento": "01/01/2031", "Data Base": "09/10/2026",
        "Taxa Compra Manha": "13,45", "Taxa Venda Manha": "13,57", "PU Compra Manha": "512,10",
        "PU Venda Manha": "509,80", "PU Base Manha": "509,00"}])
    registros = tesouro.parse(df)
    assert registros[0]["taxa_compra"] == Decimal("13.45") and registros[0]["vencimento"] == date(2031, 1, 1)
    assert tesouro.parse(df, desde=date(2027, 1, 1)) == []
    with lote(sessao, "TESOURO_TD") as ctx:
        tesouro.gravar(ctx, registros)
    assert sessao.scalar(select(TituloTesouroTaxa)).pu_venda == Decimal("509.80")


def test_brapi_parse_e_nao_sobrescreve_cotahist(sessao):
    carregar_companhias(sessao)
    resultado = {
        "symbol": "EXMP3", "regularMarketPrice": 10.5, "regularMarketTime": "2025-01-03T20:07:00.000Z",
        "regularMarketOpen": 10.1, "regularMarketDayHigh": 10.7, "regularMarketDayLow": 10.0,
        "dividendsData": {"cashDividends": [
            {"label": "DIVIDENDO", "rate": 0.5, "lastDatePrior": "2024-12-20T00:00:00.000Z",
             "paymentDate": "2025-01-15T00:00:00.000Z", "approvedOn": "2024-12-10T00:00:00.000Z"},
            {"label": "JCP", "rate": 0.2, "lastDatePrior": "2024-06-20T00:00:00.000Z"},
            {"label": "DESCONHECIDO", "rate": 1, "lastDatePrior": "2024-06-20T00:00:00.000Z"}]},
    }
    cot = brapi.parse_cotacao(resultado)
    assert cot["data"] == date(2025, 1, 3) and cot["fechamento"] == Decimal("10.5")
    assert brapi.parse_cotacao({"symbol": "X"}) is None
    proventos = brapi.parse_proventos(resultado)
    assert [p["tipo"] for p in proventos] == ["DIVIDENDO", "JCP"]
    with lote(sessao, "BRAPI") as ctx:
        brapi.gravar_cotacoes(ctx, [cot])
        brapi.gravar_cotacoes(ctx, [{**cot, "fechamento": Decimal("99")}])  # não sobrescreve
        brapi.gravar_proventos(ctx, proventos)
    assert sessao.scalar(select(CotacaoDiaria)).fechamento == Decimal("10.5")
    assert sessao.query(Provento).count() == 2


def _fii_csvs(cnpj_col="CNPJ_Fundo"):
    geral = pd.DataFrame([{cnpj_col: "11.728.688/0001-47", "Nome_Fundo": "FII EXEMPLO", "Data_Referencia": d,
                           "Versao": "1", "Codigo_ISIN": "BRHGLGCTF004", "Segmento_Atuacao": "Logística",
                           "Mandato": "Renda", "Tipo_Gestao": "Ativa", "Nome_Administrador": "ADM",
                           "Publico_Alvo": "Geral", "Data_Funcionamento": "2010-01-01"}
                          for d in ("2025-01-01", "2025-02-01")])
    comp = pd.DataFrame([{cnpj_col: "11.728.688/0001-47", "Data_Referencia": "2025-02-01", "Versao": v,
                          "Patrimonio_Liquido": pl, "Cotas_Emitidas": "1000", "Valor_Patrimonial_Cotas": "150.5",
                          "Total_Numero_Cotistas": "321", "Percentual_Dividend_Yield_Mes": "0.0080",
                          "Percentual_Rentabilidade_Patrimonial_Mes": "0.01", "Valor_Ativo": "160000"}
                         for v, pl in (("1", "100000"), ("2", "150500"))])
    ap = pd.DataFrame([{cnpj_col: "11.728.688/0001-47", "Data_Referencia": "2025-02-01", "Versao": "2",
                        "Imoveis_Renda_Acabados": "140000", "Disponibilidades": "5000", "Total_Passivo": "9500"}])
    return geral, comp, ap


@pytest.mark.parametrize("coluna", ["CNPJ_Fundo", "CNPJ_Fundo_Classe"])
def test_fii_informe_mensal(sessao, coluna):
    fundos, informes = cvm_fii.parse(*_fii_csvs(coluna))
    assert len(fundos) == 1 and fundos[0]["isin"] == "BRHGLGCTF004"
    assert len(informes) == 1 and informes[0]["versao"] == 2  # versão mais recente
    assert informes[0]["patrimonio_liquido"] == Decimal("150500")
    assert informes[0]["imoveis_renda_acabados"] == Decimal("140000")
    sessao.add(Ativo(ticker="HGLG11", classe="FII", isin="BRHGLGCTF004"))
    sessao.flush()
    with lote(sessao, "CVM_FII_MENSAL") as ctx:
        cvm_fii.gravar(ctx, fundos, informes)
    fii = sessao.scalar(select(Fii))
    assert fii.ativo_id == sessao.scalar(select(Ativo.id).where(Ativo.ticker == "HGLG11"))
    assert sessao.scalar(select(FiiInformeMensal)).numero_cotistas == 321


def test_fii_sem_coluna_cnpj_falha():
    geral, comp, ap = _fii_csvs()
    with pytest.raises(EsquemaInesperado):
        cvm_fii.parse(geral.drop(columns=["CNPJ_Fundo"]), comp, ap)
