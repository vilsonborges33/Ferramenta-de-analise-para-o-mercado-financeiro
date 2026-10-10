"""Padronização das demonstrações da CVM: `demonstracao_linha` → `demonstracao_padronizada`.

Regras (docs/ARQUITETURA.md, seção 4.4):
- Para cada documento (DFP/ITR) e data de referência, usa a versão mais recente.
- Prefere a demonstração consolidada; se a empresa não a publica, usa a individual.
- Trimestre isolado: DRE do ITR já traz o trimestre; DFC do ITR é acumulada no ano, então
  T(n) = acumulado(n) − acumulado(n−1). O 4º trimestre = DFP anual − acumulado de 9 meses.
- TTM = soma dos 4 trimestres consecutivos mais recentes; contas de balanço usam o último balanço.
- Supõe exercício social coincidente com o ano civil.
"""

import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

# ------------------------------------------------------------- mapeamento de contas


@dataclass(frozen=True)
class Regra:
    demonstracao: str  # BPA, BPP, DRE, DFC
    campo: str
    codigo: str | None = None  # conta exata
    prefixo: str | None = None  # contas descendentes (com `padrao`)
    padrao: str | None = None  # regex sobre a descrição
    nivel: int | None = None  # profundidade do código (nº de partes) quando só a descrição identifica

    def casa(self, codigo: str, descricao: str) -> bool:
        if self.codigo is not None:
            return codigo == self.codigo
        if self.prefixo is not None and not codigo.startswith(self.prefixo):
            return False
        if self.nivel is not None and codigo.count(".") + 1 != self.nivel:
            return False
        return bool(self.padrao and re.search(self.padrao, descricao, re.IGNORECASE))


_DA = r"deprecia|amortiza|exaust"
_CAPEX = r"(aquisi|adi[çc])\w*.*(imobilizado|intang)|(imobilizado|intang)\w*.*(aquisi|adi[çc])"
_DIVIDENDOS = r"dividend|juros sobre (o )?capital"

# Contas comuns a todos os planos (DFC tem a mesma estrutura).
_DFC = [
    Regra("DFC", "fco", codigo="6.01"),
    Regra("DFC", "depreciacao_amortizacao", prefixo="6.01.01.", padrao=_DA),
    Regra("DFC", "capex", prefixo="6.02.", padrao=_CAPEX),
    Regra("DFC", "dividendos_pagos", prefixo="6.03.", padrao=_DIVIDENDOS),
]

REGRAS: dict[str, list[Regra]] = {
    "geral": [
        Regra("DRE", "receita_liquida", codigo="3.01"),
        Regra("DRE", "custo", codigo="3.02"),
        Regra("DRE", "lucro_bruto", codigo="3.03"),
        Regra("DRE", "ebit", codigo="3.05"),
        Regra("DRE", "resultado_financeiro", codigo="3.06"),
        Regra("DRE", "lucro_antes_ir", codigo="3.07"),
        Regra("DRE", "lucro_liquido", codigo="3.11"),
        Regra("DRE", "lucro_liquido_controladores", codigo="3.11.01"),
        Regra("BPA", "ativo_total", codigo="1"),
        Regra("BPA", "ativo_circulante", codigo="1.01"),
        Regra("BPA", "caixa_equivalentes", codigo="1.01.01"),
        Regra("BPA", "aplicacoes_financeiras", codigo="1.01.02"),
        Regra("BPA", "imobilizado", codigo="1.02.03"),
        Regra("BPA", "intangivel", codigo="1.02.04"),
        Regra("BPP", "passivo_circulante", codigo="2.01"),
        Regra("BPP", "emprestimos_cp", codigo="2.01.04"),
        Regra("BPP", "passivo_nao_circulante", codigo="2.02"),
        Regra("BPP", "emprestimos_lp", codigo="2.02.01"),
        Regra("BPP", "patrimonio_liquido", codigo="2.03"),
        Regra("BPP", "participacao_nao_controladores", prefixo="2.03.", padrao=r"n[ãa]o controlador", nivel=3),
        *_DFC,
    ],
    # Bancos e seguradoras: códigos variam; identificação pela descrição. Campos sem sentido
    # para o setor (EBIT, dívida, circulante) ficam ausentes de propósito (DECISOES.md D-008).
    "banco": [
        Regra("DRE", "receita_liquida", prefixo="3.", padrao=r"^receitas? (da|de) intermedia", nivel=2),
        Regra("DRE", "lucro_antes_ir", prefixo="3.", padrao=r"^resultado antes d", nivel=2),
        Regra("DRE", "lucro_liquido", prefixo="3.", padrao=r"^lucro.*l[íi]quido.*per[íi]odo", nivel=2),
        Regra("DRE", "lucro_liquido_controladores", prefixo="3.", padrao=r"controladora", nivel=3),
        Regra("BPA", "ativo_total", codigo="1"),
        Regra("BPP", "patrimonio_liquido", prefixo="2.", padrao=r"^patrim[ôo]nio l[íi]quido", nivel=2),
        Regra("BPP", "participacao_nao_controladores", prefixo="2.", padrao=r"n[ãa]o controlador", nivel=3),
        *_DFC,
    ],
}
REGRAS["seguradora"] = REGRAS["banco"]

CAMPOS_FLUXO_DEMONSTRACOES = {"DRE", "DFC"}
CAMPOS_SOMADOS = {"depreciacao_amortizacao", "capex", "dividendos_pagos"}


def demonstracao_base(tipo: str) -> str:
    return "DFC" if tipo.startswith("DFC") else tipo


# ------------------------------------------------------------------ estrutura


@dataclass
class Bloco:
    """Valores padronizados de um recorte (documento + período) com as contas de origem."""

    campos: dict[str, float] = field(default_factory=dict)
    insumos: dict[str, list[dict]] = field(default_factory=lambda: defaultdict(list))


@dataclass
class PeriodoPadronizado:
    periodo: str
    tipo_periodo: str  # trimestre, ano, ttm
    data_inicio: date | None
    data_fim: date
    consolidado: bool
    versao_usada: int
    documento: str
    campos: dict[str, float]
    insumos: dict[str, list[dict]]


def _aplicar_regras(linhas: list[dict], regras: list[Regra]) -> Bloco:
    bloco = Bloco()
    for regra in regras:
        for linha in linhas:
            if demonstracao_base(linha["tipo"]) != regra.demonstracao:
                continue
            if not regra.casa(linha["conta_codigo"], linha["conta_descricao"]):
                continue
            # Contas somadas (D&A, capex, dividendos) só nas folhas não fixas, para não contar duas vezes.
            if regra.campo in CAMPOS_SOMADOS:
                bloco.campos[regra.campo] = bloco.campos.get(regra.campo, 0.0) + float(linha["valor"])
            elif regra.campo in bloco.campos:
                continue
            else:
                bloco.campos[regra.campo] = float(linha["valor"])
            bloco.insumos[regra.campo].append({
                "documento": linha["documento"], "tipo": linha["tipo"], "conta": linha["conta_codigo"],
                "descricao": linha["conta_descricao"], "versao": linha["versao"],
                "data_fim": linha["data_fim"].isoformat(), "valor": float(linha["valor"]),
            })
    _derivar(bloco)
    return bloco


def _derivar(bloco: Bloco) -> None:
    c = bloco.campos
    if "lucro_liquido_controladores" not in c and "lucro_liquido" in c:
        c["lucro_liquido_controladores"] = c["lucro_liquido"]
    if "patrimonio_liquido" in c:
        c["patrimonio_liquido_controladores"] = c["patrimonio_liquido"] - c.get("participacao_nao_controladores", 0.0)
    if "ativo_total" in c and "patrimonio_liquido" in c:
        c["passivo_total"] = c["ativo_total"] - c["patrimonio_liquido"]


def _trimestre(d: date) -> int:
    return (d.month - 1) // 3 + 1


def _selecionar(linhas: list[dict]) -> dict[tuple[str, date], list[dict]]:
    """Agrupa por (documento, data de referência), com versão mais recente e consolidado preferido."""
    grupos: dict[tuple[str, date], list[dict]] = defaultdict(list)
    for linha in linhas:
        grupos[(linha["documento"], linha["data_referencia"])].append(linha)
    escolhidas = {}
    for chave, grupo in grupos.items():
        consolidado = any(lin["consolidado"] for lin in grupo)
        grupo = [lin for lin in grupo if lin["consolidado"] == consolidado]
        versao = max(lin["versao"] for lin in grupo)
        escolhidas[chave] = [lin for lin in grupo if lin["versao"] == versao]
    return escolhidas


def _separar_fluxos(linhas: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    """Separa linhas de balanço, fluxos do trimestre (3 meses) e fluxos acumulados no ano."""
    balanco, trimestre, acumulado = [], [], []
    for lin in linhas:
        if demonstracao_base(lin["tipo"]) not in CAMPOS_FLUXO_DEMONSTRACOES:
            balanco.append(lin)
            continue
        inicio, fim = lin["data_inicio"], lin["data_fim"]
        meses = (fim.year - inicio.year) * 12 + fim.month - inicio.month + 1 if inicio else 12
        if meses <= 3:
            trimestre.append(lin)
        if inicio is None or inicio.month == 1:
            acumulado.append(lin)
    return balanco, trimestre, acumulado


def _subtrair(a: Bloco, b: Bloco, campos_fluxo: set[str]) -> Bloco:
    resultado = Bloco()
    for campo in campos_fluxo:
        if campo in a.campos and campo in b.campos:
            resultado.campos[campo] = a.campos[campo] - b.campos[campo]
            resultado.insumos[campo] = a.insumos.get(campo, []) + [
                {**i, "subtraido": True} for i in b.insumos.get(campo, [])]
    return resultado


def _campos_de(regras: list[Regra], demonstracoes: set[str]) -> set[str]:
    campos = {r.campo for r in regras if r.demonstracao in demonstracoes}
    if "lucro_liquido" in campos:
        campos.add("lucro_liquido_controladores")
    return campos


def padronizar(linhas: list[dict], tipo_plano: str = "geral") -> list[PeriodoPadronizado]:
    """Gera períodos anuais, trimestrais e TTM a partir das linhas brutas de uma empresa."""
    regras = REGRAS[tipo_plano]
    campos_dre = _campos_de(regras, {"DRE"})
    campos_dfc = _campos_de(regras, {"DFC"})
    escolhidas = _selecionar(linhas)

    anuais: dict[int, tuple[Bloco, list[dict]]] = {}
    trimestrais: dict[tuple[int, int], dict] = {}
    acumulados: dict[tuple[int, int], Bloco] = {}
    saida: list[PeriodoPadronizado] = []

    for (documento, data_ref), grupo in sorted(escolhidas.items(), key=lambda kv: kv[0][1]):
        consolidado = grupo[0]["consolidado"]
        versao = grupo[0]["versao"]
        balanco, trimestre, acumulado = _separar_fluxos(grupo)
        if documento == "DFP":
            bloco = _aplicar_regras(balanco + acumulado, regras)
            anuais[data_ref.year] = (bloco, grupo)
            saida.append(PeriodoPadronizado(f"{data_ref.year}-A", "ano", date(data_ref.year, 1, 1), data_ref,
                                            consolidado, versao, documento, bloco.campos, dict(bloco.insumos)))
        else:
            q = _trimestre(data_ref)
            bloco_bal = _aplicar_regras(balanco, regras)
            bloco_tri = _aplicar_regras(trimestre, regras)
            bloco_acu = _aplicar_regras(acumulado, regras)
            acumulados[(data_ref.year, q)] = bloco_acu
            trimestrais[(data_ref.year, q)] = {
                "data_fim": data_ref, "consolidado": consolidado, "versao": versao, "documento": documento,
                "balanco": bloco_bal, "dre": bloco_tri,
            }

    # DFC trimestral a partir dos acumulados e 4º trimestre a partir da DFP.
    for (ano, q), info in list(trimestrais.items()):
        if q == 1:
            dfc = Bloco({c: v for c, v in acumulados[(ano, 1)].campos.items() if c in campos_dfc},
                        defaultdict(list, {c: v for c, v in acumulados[(ano, 1)].insumos.items() if c in campos_dfc}))
        elif (ano, q - 1) in acumulados:
            dfc = _subtrair(acumulados[(ano, q)], acumulados[(ano, q - 1)], campos_dfc)
        else:
            dfc = Bloco()
        info["dfc"] = dfc
    for ano, (bloco_anual, grupo) in anuais.items():
        if (ano, 3) not in acumulados:
            continue
        acu9 = acumulados[(ano, 3)]
        trimestrais[(ano, 4)] = {
            "data_fim": grupo[0]["data_referencia"], "consolidado": grupo[0]["consolidado"],
            "versao": grupo[0]["versao"], "documento": "DFP",
            "balanco": Bloco({c: v for c, v in bloco_anual.campos.items() if c not in campos_dre | campos_dfc},
                             defaultdict(list, bloco_anual.insumos)),
            "dre": _subtrair(bloco_anual, acu9, campos_dre),
            "dfc": _subtrair(bloco_anual, acu9, campos_dfc),
        }

    def combinar(info: dict) -> Bloco:
        b = Bloco()
        for parte in ("balanco", "dre", "dfc"):
            b.campos.update(info[parte].campos)
            for campo, origem in info[parte].insumos.items():
                b.insumos[campo] = origem
        _derivar(b)
        return b

    for (ano, q), info in sorted(trimestrais.items()):
        bloco = combinar(info)
        inicio = date(ano, 3 * q - 2, 1)
        saida.append(PeriodoPadronizado(f"{ano}-T{q}", "trimestre", inicio, info["data_fim"], info["consolidado"],
                                        info["versao"], info["documento"], bloco.campos, dict(bloco.insumos)))
        janela = [(ano - (1 if q - k <= 0 else 0), (q - k - 1) % 4 + 1) for k in range(4)]
        if not all(j in trimestrais for j in janela):
            continue
        blocos = [combinar(trimestrais[j]) for j in janela]
        ttm = Bloco()
        ttm.campos.update({c: v for c, v in bloco.campos.items() if c not in campos_dre | campos_dfc})
        for c in campos_dre | campos_dfc:
            if all(c in b.campos for b in blocos):
                ttm.campos[c] = sum(b.campos[c] for b in blocos)
                ttm.insumos[c] = [i for b in blocos for i in b.insumos.get(c, [])]
        for c, origem in bloco.insumos.items():
            ttm.insumos.setdefault(c, origem)
        _derivar(ttm)
        inicio_ttm = date(janela[-1][0], 3 * janela[-1][1] - 2, 1)
        saida.append(PeriodoPadronizado(f"{ano}-T{q}", "ttm", inicio_ttm, info["data_fim"], info["consolidado"],
                                        info["versao"], info["documento"], ttm.campos, dict(ttm.insumos)))
    return saida
