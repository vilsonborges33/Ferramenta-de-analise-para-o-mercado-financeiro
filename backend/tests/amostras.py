"""Construtores de arquivos de amostra no formato das fontes. Valores fictícios."""

import io
import zipfile

CAB_DEMO = ("CNPJ_CIA;DT_REFER;VERSAO;DENOM_CIA;CD_CVM;GRUPO_DFP;MOEDA;ESCALA_MOEDA;ORDEM_EXERC;"
            "DT_INI_EXERC;DT_FIM_EXERC;CD_CONTA;DS_CONTA;VL_CONTA;ST_CONTA_FIXA")
CAB_BP = ("CNPJ_CIA;DT_REFER;VERSAO;DENOM_CIA;CD_CVM;GRUPO_DFP;MOEDA;ESCALA_MOEDA;ORDEM_EXERC;"
          "DT_FIM_EXERC;CD_CONTA;DS_CONTA;VL_CONTA;ST_CONTA_FIXA")
CNPJ = "00.000.000/0001-91"


def csv(cabecalho: str, linhas: list[str]) -> bytes:
    return ("\n".join([cabecalho, *linhas]) + "\n").encode("latin-1")


def cadastro() -> bytes:
    return csv("CNPJ_CIA;DENOM_SOCIAL;DENOM_COMERC;DT_REG;DT_CONST;DT_CANCEL;MOTIVO_CANCEL;SIT;DT_INI_SIT;CD_CVM;"
               "SETOR_ATIV",
               [f"{CNPJ};EMPRESA EXEMPLO S.A.;EXEMPLO;2000-01-01;1990-01-01;;;ATIVO;2000-01-01;012345;"
                "Energia Elétrica",
                "11.111.111/0001-11;BANCO EXEMPLO S.A.;BANCO;2001-01-01;1990-01-01;;;ATIVO;2001-01-01;054321;"
                "Bancos"])


def valores_mobiliarios() -> bytes:
    return csv("CNPJ_Companhia;Data_Referencia;Versao;Valor_Mobiliario;Codigo_Negociacao;Mercado;Segmento;"
               "Data_Fim_Negociacao",
               [f"{CNPJ};2025-01-01;1;Ações Ordinárias;EXMP3;Bolsa;Novo Mercado;",
                f"{CNPJ};2025-01-01;1;Ações Preferenciais;EXMP4;Bolsa;Novo Mercado;",
                f"{CNPJ};2025-01-01;1;Debêntures;EXMP11;Balcão Organizado;;",
                "11.111.111/0001-11;2025-01-01;1;Ações Ordinárias;BEXM3;Bolsa;Nível 1;"])


def _demo(tipo_doc: str, ref: str, ini: str | None, fim: str, contas: list[tuple[str, str, float]],
          escala="MIL") -> bytes:
    if ini is None:
        return csv(CAB_BP, [f"{CNPJ};{ref};1;EXEMPLO;12345;{tipo_doc};REAL;{escala};ÚLTIMO;{fim};{c};{d};{v};S"
                            for c, d, v in contas])
    return csv(CAB_DEMO, [f"{CNPJ};{ref};1;EXEMPLO;12345;{tipo_doc};REAL;{escala};ÚLTIMO;{ini};{fim};{c};{d};{v};S"
                          for c, d, v in contas])


def zip_dfp(ano: int, receita: float, lucro: float, versao_extra: bool = False) -> bytes:
    fim, ini = f"{ano}-12-31", f"{ano}-01-01"
    arquivos = {
        f"dfp_cia_aberta_DRE_con_{ano}.csv": _demo("DRE", fim, ini, fim, [
            ("3.01", "Receita de Venda de Bens e/ou Serviços", receita),
            ("3.03", "Resultado Bruto", receita * 0.4),
            ("3.05", "Resultado Antes do Resultado Financeiro e dos Tributos", receita * 0.2),
            ("3.11", "Lucro/Prejuízo Consolidado do Período", lucro),
            ("3.11.01", "Atribuído a Sócios da Empresa Controladora", lucro)]),
        f"dfp_cia_aberta_BPA_con_{ano}.csv": _demo("BPA", fim, None, fim, [
            ("1", "Ativo Total", 10000), ("1.01", "Ativo Circulante", 3000),
            ("1.01.01", "Caixa e Equivalentes de Caixa", 500), ("1.01.02", "Aplicações Financeiras", 100),
            ("1.02.03", "Imobilizado", 2000)]),
        f"dfp_cia_aberta_BPP_con_{ano}.csv": _demo("BPP", fim, None, fim, [
            ("2.01", "Passivo Circulante", 1500), ("2.01.04", "Empréstimos e Financiamentos", 400),
            ("2.02.01", "Empréstimos e Financiamentos", 1600), ("2.03", "Patrimônio Líquido Consolidado", 5000)]),
        f"dfp_cia_aberta_DFC_MI_con_{ano}.csv": _demo("DFC", fim, ini, fim, [
            ("6.01", "Caixa Líquido Atividades Operacionais", 900),
            ("6.01.01.02", "Depreciação e amortização", 300)]),
        f"dfp_cia_aberta_composicao_capital_{ano}.csv": csv(
            "CNPJ_CIA;DT_REFER;VERSAO;DENOM_CIA;QT_ACAO_ORDIN_CAP_INTEGR;QT_ACAO_PREF_CAP_INTEGR;"
            "QT_ACAO_TOTAL_CAP_INTEGR;QT_ACAO_ORDIN_TESOURO;QT_ACAO_PREF_TESOURO;QT_ACAO_TOTAL_TESOURO",
            [f"{CNPJ};{fim};1;EXEMPLO;600000;400000;1000000;0;0;0"]),
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        for nome, conteudo in arquivos.items():
            z.writestr(nome, conteudo)
    return buffer.getvalue()


def linha_cotahist(data: str, ticker: str, fechamento: float, volume: float, codbdi="02", isin="BREXMPACNOR0",
                   fator=1) -> str:
    def p(v, n=13):
        return f"{round(v * 100):0{n}d}"
    linha = (
        "01" + data + codbdi + ticker.ljust(12) + "010" + "EXEMPLO".ljust(12) + "ON NM".ljust(10) + "   " + "R$  "
        + p(fechamento) + p(fechamento) + p(fechamento) + p(fechamento) + p(fechamento) + p(0) + p(0)
        + "00100" + f"{1000:018d}" + p(volume, 18) + p(0) + "0" + "99991231" + f"{fator:07d}" + p(0)
        + isin.ljust(12) + "100"
    )
    assert len(linha) == 245, len(linha)
    return linha
