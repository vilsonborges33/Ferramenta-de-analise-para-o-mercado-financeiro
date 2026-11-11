import io

import pytest
from openpyxl import load_workbook

from app.servicos.screening import setor_besst
from tests.api.test_ponta_a_ponta import cliente  # noqa: F401  (fixture)


def test_screening_mostra_todos_os_metodos_lado_a_lado(cliente):  # noqa: F811
    r = cliente.get("/screening/acoes").json()
    assert "Não constituem recomendação" in r["aviso"]
    assert r["sem_cotacao"] == 1 and r["atualizado_em"] == "2025-01-02"
    assert [i["ticker"] for i in r["itens"]] == ["EXMP3", "EXMP4"]  # ordenado pela margem de Graham
    exmp3 = r["itens"][0]
    assert exmp3["posicao"] == 1
    assert exmp3["graham_valor"] == pytest.approx((22.5 * 5) ** 0.5)
    assert exmp3["graham_margem"] == pytest.approx(1 - 10 / (22.5 * 5) ** 0.5)
    assert exmp3["p_l"] == pytest.approx(10) and exmp3["roe"] == pytest.approx(0.2)
    assert exmp3["bazin_teto"] is None  # sem proventos
    assert exmp3["earnings_yield"] == pytest.approx(1.6 / 12.2) and exmp3["greenblatt_posicao"] is not None
    assert any("Energia Elétrica" in s for s in r["setores"])


def test_screening_filtros_por_faixa_e_setor(cliente):  # noqa: F811
    assert [i["ticker"] for i in cliente.get("/screening/acoes", params={"p_l_max": 11}).json()["itens"]] == ["EXMP3"]
    assert cliente.get("/screening/acoes", params={"dy_min": 0.01}).json()["itens"] == []  # DY indisponível
    assert len(cliente.get("/screening/acoes", params={"besst": True}).json()["itens"]) == 2  # energia elétrica
    assert cliente.get("/screening/acoes", params={"setores": ["Bancos"]}).json()["itens"] == []  # banco sem cotação
    assert cliente.get("/screening/acoes", params={"p_l_min": "x"}).status_code == 422
    assert cliente.get("/screening/acoes", params={"ordenar_por": "xyz"}).status_code == 422
    r = cliente.get("/screening/acoes", params={"fator_graham": 10}).json()
    assert r["itens"][0]["graham_valor"] == pytest.approx(50 ** 0.5)


def test_filtro_nao_reprova_o_que_nao_se_aplica():
    from app.servicos.screening import _dentro
    assert not _dentro(None, (None, 5))  # dado que falta reprova
    assert _dentro(None, (None, 5), nao_se_aplica=True)  # DL/EBITDA de banco: não se aplica, passa
    assert not _dentro(6, (None, 5), nao_se_aplica=True)  # havendo valor, o filtro vale normalmente


def test_setor_besst():
    assert setor_besst("Bancos") and setor_besst("Emp. Adm. Part. - Energia Elétrica")
    assert setor_besst("Saneamento, Serv. Água e Gás") and setor_besst("Seguradoras e Corretoras")
    assert setor_besst("Telecomunicações") and not setor_besst("Petróleo e Gás") and not setor_besst(None)


def test_exportacao_csv_e_xlsx(cliente):  # noqa: F811
    csv = cliente.get("/screening/acoes/exportar", params={"formato": "csv"})
    assert csv.status_code == 200 and "attachment" in csv.headers["content-disposition"]
    texto = csv.content.decode("utf-8-sig")
    assert texto.splitlines()[0].startswith("#;Ticker;Empresa") and "EXMP3" in texto
    assert "Não constituem recomendação" in texto and "10" in texto.splitlines()[1]
    xlsx = cliente.get("/screening/acoes/exportar", params={"formato": "xlsx", "p_l_max": 11})
    folha = load_workbook(io.BytesIO(xlsx.content)).active
    assert folha["B1"].value == "Ticker" and folha["B2"].value == "EXMP3" and folha["B3"].value is None
    assert folha["E2"].value == pytest.approx(10) and folha["G2"].number_format == "0.00%"
    assert cliente.get("/screening/acoes/exportar", params={"formato": "pdf"}).status_code == 422


def test_favoritos_exigem_login_e_filtram_o_screening(cliente):  # noqa: F811
    assert cliente.get("/favoritos").status_code == 401
    assert cliente.get("/screening/acoes", params={"somente_favoritos": True}).status_code == 401
    cliente.post("/auth/registrar", json={"email": "eu@exemplo.com", "senha": "senha-forte-1"})
    assert cliente.put("/favoritos/exmp4").status_code == 204
    assert cliente.put("/favoritos/EXMP4").status_code == 204  # repetir não duplica
    assert cliente.put("/favoritos/NAOEXISTE3").status_code == 404
    assert cliente.get("/favoritos").json() == ["EXMP4"]
    r = cliente.get("/screening/acoes", params={"somente_favoritos": True}).json()
    assert [i["ticker"] for i in r["itens"]] == ["EXMP4"]
    assert cliente.delete("/favoritos/EXMP4").status_code == 204
    assert cliente.get("/favoritos").json() == []
