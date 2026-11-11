"""Correções achadas na conferência com a Ward (10/11/2026): units, risco com proventos, cotações erradas do Yahoo,
plano de contas das holdings, capital já sem tesouraria e recálculo que não para num ativo com problema."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select, update

from app.db.modelos import Ativo, ComposicaoCapital, CotacaoDiaria, IndicadorCalculado, Provento, SerieEconomica
from app.ingestao.base import lote
from app.ingestao.padronizacao import plano_pela_dre
from app.metodologias import portfolio
from app.servicos import historico, indicadores
from app.servicos.indicadores import Calculadora, recalcular
from tests import amostras
from tests.api.test_fii_ponta_a_ponta import cliente as cliente_fii  # noqa: F401  (fixture)
from tests.api.test_ponta_a_ponta import cliente  # noqa: F401  (fixture)
from tests.api.test_ponta_a_ponta import indicadores as por_metrica


def _cotar(sessao, ticker: str, pontos: list[tuple[date, float]]) -> Ativo:
    ativo = sessao.scalar(select(Ativo).where(Ativo.ticker == ticker))
    with lote(sessao, "YAHOO_FINANCE") as ctx:
        for dia, preco in pontos:
            sessao.add(CotacaoDiaria(ativo_id=ativo.id, data=dia, fechamento=Decimal(str(preco)),
                                     volume_financeiro=Decimal("1000000"), **ctx.procedencia(dia)))
    return ativo


def _nova_unit(sessao, ticker: str) -> Ativo:
    empresa_id = sessao.scalar(select(Ativo.empresa_id).where(Ativo.ticker == "EXMP3"))
    unit = Ativo(ticker=ticker, empresa_id=empresa_id, classe="UNIT", especie="UNIT")
    sessao.add(unit)
    sessao.flush()
    return unit


def test_unit_tem_indicadores_por_unit(cliente, sessao, monkeypatch):  # noqa: F811
    # EXMP11 = 1 ON + 2 PN: R$ 10 + 2 × R$ 12 = R$ 34. Empresa: lucro R$ 1 mi, PL R$ 5 mi, 1 mi de ações.
    monkeypatch.setitem(indicadores.COMPOSICAO_UNITS, "EXMP11", (1, 2))
    _nova_unit(sessao, "EXMP11")
    _nova_unit(sessao, "EXMP12")  # unit sem composição conhecida
    _cotar(sessao, "EXMP11", [(date(2025, 1, 2), 34.0)])
    _cotar(sessao, "EXMP12", [(date(2025, 1, 2), 34.0)])
    sessao.commit()
    recalcular(sessao)

    ind = por_metrica(cliente.get("/acoes/EXMP11").json())
    assert ind["basico.lpa"]["valor"] == pytest.approx(3)  # R$ 1 mi ÷ (1 mi ÷ 3) units
    assert ind["basico.vpa"]["valor"] == pytest.approx(15)
    assert ind["basico.p_l"]["valor"] == pytest.approx(34 / 3)
    assert ind["basico.p_vp"]["valor"] == pytest.approx(34 / 15)
    assert ind["graham.valor_intrinseco"]["valor"] == pytest.approx((22.5 * 3 * 15) ** 0.5)
    # O valor de mercado é o da empresa, igual ao das ações: 600 mil × R$ 10 + 400 mil × R$ 12.
    assert ind["basico.valor_mercado"]["valor"] == pytest.approx(10_800_000)

    sem = por_metrica(cliente.get("/acoes/EXMP12").json())
    assert sem["basico.lpa"]["valor"] is None and "composição da unit" in sem["basico.lpa"]["motivo_indisponivel"]
    assert "EXMP11" in [a["ticker"] for a in cliente.get("/acoes", params={"busca": "EXMP"}).json()]


def test_classe_sem_cotacao_vale_pela_unit(cliente, sessao, monkeypatch):  # noqa: F811
    # Como KLBN: só a unit negocia. Sem cotação de EXMP3/EXMP4, cada ação vale R$ 34 ÷ 3.
    monkeypatch.setitem(indicadores.COMPOSICAO_UNITS, "EXMP11", (1, 2))
    _nova_unit(sessao, "EXMP11")
    sessao.commit()
    _cotar(sessao, "EXMP11", [(date(2025, 1, 2), 34.0)])
    sessao.commit()
    sessao.expire_all()  # a lista de ativos da empresa foi carregada antes da unit existir
    empresa = sessao.scalar(select(Ativo).where(Ativo.ticker == "EXMP11")).empresa
    calc = Calculadora(sessao)
    calc.ultima_cotacao = lambda ativo_id, _orig=calc.ultima_cotacao: (  # só a unit tem cotação
        _orig(ativo_id) if sessao.get(Ativo, ativo_id).ticker == "EXMP11" else None)
    assert calc._precos_por_especie(empresa) == pytest.approx({"ON": 34 / 3, "PN": 34 / 3})


def test_capital_informado_sem_tesouraria(cliente, sessao, monkeypatch):  # noqa: F811
    sessao.execute(update(ComposicaoCapital).values(acoes_tesouraria_on=Decimal("100000")))
    sessao.commit()
    recalcular(sessao, ["EXMP3"])
    lpa = por_metrica(cliente.get("/acoes/EXMP3").json())["basico.lpa"]["valor"]
    assert lpa == pytest.approx(1_000_000 / 900_000)  # regra geral: integralizado − tesouraria

    monkeypatch.setitem(indicadores.CAPITAL_SEM_TESOURARIA, amostras.CNPJ, date(2020, 1, 1))
    recalcular(sessao, ["EXMP3"])
    lpa = por_metrica(cliente.get("/acoes/EXMP3").json())["basico.lpa"]["valor"]
    assert lpa == pytest.approx(1.0)  # como a Vale desde 03/2026: o integralizado já vem sem a tesouraria


def test_recalculo_continua_quando_um_ativo_falha(cliente, sessao, monkeypatch):  # noqa: F811
    original = Calculadora.materializar

    def falha_no_exmp3(self, ativo):
        if ativo.ticker == "EXMP3":
            raise AttributeError("'NoneType' object has no attribute 'como_dict'")
        return original(self, ativo)

    sessao.execute(update(IndicadorCalculado).values(calculado_em=IndicadorCalculado.calculado_em - timedelta(days=9)))
    sessao.commit()
    monkeypatch.setattr(Calculadora, "materializar", falha_no_exmp3)
    assert recalcular(sessao) > 0
    exmp4 = sessao.scalar(select(Ativo.id).where(Ativo.ticker == "EXMP4"))
    novos = sessao.scalar(select(IndicadorCalculado.calculado_em).where(IndicadorCalculado.ativo_id == exmp4).limit(1))
    assert novos.date() >= date.today() - timedelta(days=1)


def test_fii_sem_cotacao_com_rendimentos_nao_quebra(cliente_fii, sessao):  # noqa: F811
    ativo = sessao.scalar(select(Ativo).where(Ativo.ticker == "HGLG11"))
    sessao.execute(CotacaoDiaria.__table__.delete().where(CotacaoDiaria.ativo_id == ativo.id))
    with lote(sessao, "YAHOO_FINANCE") as ctx:
        d = date.today() - timedelta(days=30)
        sessao.add(Provento(ativo_id=ativo.id, tipo="RENDIMENTO_FII", valor_por_cota=Decimal("1"), data_com=d,
                            data_ex=d, **ctx.procedencia(d)))
    sessao.commit()
    calc = Calculadora(sessao)
    assert calc.materializar(ativo) > 0  # antes: 'NoneType' object has no attribute 'como_dict'


def test_risco_usa_retorno_total_e_ignora_pico(cliente, sessao):  # noqa: F811
    # R$ 10 por 20 pregões, data-ex de R$ 1 e R$ 9 daí em diante: retorno total zero (só preço daria −10%).
    # Um pregão com R$ 900 (cotação errada da fonte, como XPML11 em 01/2026) não pode virar volatilidade.
    hoje = date(2025, 6, 30)
    dias = [hoje - timedelta(days=60 - n) for n in range(60)]
    precos = [10.0 if n < 20 else 9.0 for n in range(60)]
    precos[40] = 900.0
    ativo = _cotar(sessao, "EXMP3", list(zip(dias, precos, strict=True)))  # a fixture já cota a R$ 10
    with lote(sessao, "YAHOO_FINANCE") as ctx:
        sessao.add(Provento(ativo_id=ativo.id, tipo="DIVIDENDO", valor_por_cota=Decimal("1"), data_com=dias[19],
                            data_ex=dias[20], **ctx.procedencia(dias[20])))
    with lote(sessao, "BCB_SGS") as ctx:
        for dia in dias:
            sessao.add(SerieEconomica(codigo="CDI", data=dia, valor=Decimal("0.04"), **ctx.procedencia(dia)))
    sessao.commit()
    r = historico.risco(sessao, "EXMP3", hoje)
    assert r["retorno_12m"] == pytest.approx(0, abs=1e-9)
    assert r["volatilidade_12m"]["valor"] == pytest.approx(0, abs=1e-9)


def test_indices_sem_picos_preserva_desdobramento():
    precos = [10.0] * 10 + [1.06] * 3 + [10.0] * 10  # pico de 3 dias: sai
    assert portfolio.indices_sem_picos(precos) == list(range(10)) + list(range(13, 23))
    desdobrada = [20.0] * 10 + [10.0] * 10  # desdobramento 1:2 sem ajuste: fica
    assert portfolio.indices_sem_picos(desdobrada) == list(range(20))


def test_fca_do_ano_anterior_completa_empresas_ausentes(cliente, sessao, monkeypatch, tmp_path):  # noqa: F811
    import zipfile

    from app.ingestao import cvm_companhias

    cab = ("CNPJ_Companhia;Data_Referencia;Versao;Valor_Mobiliario;Codigo_Negociacao;Mercado;Segmento;"
           "Data_Fim_Negociacao")
    por_ano = {
        2026: [f"{amostras.CNPJ};2026-01-01;1;Ações Ordinárias;EXMP3;Bolsa;Novo Mercado;"],
        # 2025: o banco ainda não entregou o de 2026 (fica com B3XM3, raiz com dígito como B3SA3); o EXMP9 da
        # empresa exemplo não entra, porque ela já está no FCA de 2026.
        2025: ["11.111.111/0001-11;2025-01-01;1;Ações Ordinárias;B3XM3;Bolsa;Nível 1;",
               f"{amostras.CNPJ};2025-01-01;1;Ações Ordinárias;EXMP9;Bolsa;Novo Mercado;"],
    }

    def baixar(url, fonte):
        ano = 2026 if "2026" in url else 2025
        caminho = tmp_path / f"fca_{ano}.zip"
        with zipfile.ZipFile(caminho, "w") as z:
            z.writestr(f"fca_cia_aberta_valor_mobiliario_{ano}.csv", amostras.csv(cab, por_ano[ano]))
        return caminho, f"hash{ano}"

    monkeypatch.setattr(cvm_companhias, "baixar", baixar)
    cvm_companhias.ingerir_valores_mobiliarios(sessao, 2026)
    tickers = set(sessao.scalars(select(Ativo.ticker)))
    assert "B3XM3" in tickers and "EXMP9" not in tickers


def test_plano_pela_dre():
    def dre(descricao):
        return [{"conta_codigo": "3.01", "tipo": "DRE", "data_fim": date(2025, 12, 31), "conta_descricao": descricao}]

    assert plano_pela_dre(dre("Receita de Venda de Bens e/ou Serviços"), "banco") == "geral"  # Itaúsa
    assert plano_pela_dre(dre("Receitas da Intermediação Financeira"), "banco") == "banco"
    assert plano_pela_dre(dre("Receitas das Atividades Seguradoras"), "seguradora") == "seguradora"
    assert plano_pela_dre([], "banco") == "banco"
    assert plano_pela_dre(dre("Receitas da Intermediação Financeira"), "geral") == "geral"
