"""B3: proventos em dinheiro (dividendos, JCP, rendimentos) das companhias listadas.

Consulta pública usada pelo próprio site da B3 (página "Empresas listadas → Eventos corporativos"):
  GET https://sistemaswebb3-listados.b3.com.br/listedCompaniesProxy/CompanyCall/GetListedSupplementCompany/{p}
  p = base64 de {"issuingCompany": "PETR", "language": "pt-br"}

Não é uma API documentada: pode mudar sem aviso (DECISOES.md D-025). Datas em dd/mm/aaaa e valores
com vírgula decimal; o vínculo com o ticker é feito pelo ISIN (gravado a partir do COTAHIST).
"""

import base64
import json
import logging
import time

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.db.modelos import Ativo, Provento
from app.ingestao.base import Contexto, EsquemaInesperado, cliente_http, data_br, decimal_br, lote

log = logging.getLogger(__name__)

URL = "https://sistemaswebb3-listados.b3.com.br/listedCompaniesProxy/CompanyCall/GetListedSupplementCompany/{param}"


def tipo_provento(rotulo: str | None) -> str | None:
    r = (rotulo or "").upper()
    if "JRS" in r or "JUROS" in r:
        return "JCP"
    if "DIVID" in r:
        return "DIVIDENDO"
    if "RENDIMENTO" in r:
        return "RENDIMENTO_FII"
    if "AMORTIZ" in r:
        return "AMORTIZACAO"
    return None


def url_empresa(codigo: str) -> str:
    param = base64.b64encode(json.dumps({"issuingCompany": codigo, "language": "pt-br"}).encode()).decode()
    return URL.format(param=param)


def parse(resposta: object) -> list[dict]:
    """Extrai os proventos em dinheiro da resposta (lista com um objeto por companhia)."""
    if resposta in (None, "", [], {}):
        return []
    if isinstance(resposta, dict):
        resposta = [resposta]
    if not isinstance(resposta, list) or not isinstance(resposta[0], dict):
        raise EsquemaInesperado("B3 proventos: resposta em formato inesperado")
    registros = []
    for empresa in resposta:
        for p in empresa.get("cashDividends") or []:
            tipo = tipo_provento(p.get("label"))
            valor = decimal_br(p.get("rate"))
            data_com = data_br(p.get("lastDatePrior"))
            isin = (p.get("isinCode") or p.get("assetIssued") or "").strip()
            if tipo is None or valor is None or valor <= 0 or data_com is None or not isin:
                continue
            registros.append({
                "isin": isin, "tipo": tipo, "valor_por_cota": valor, "data_com": data_com,
                "data_aprovacao": data_br(p.get("approvedOn")), "data_pagamento": data_br(p.get("paymentDate")),
            })
    return registros


def gravar(ctx: Contexto, registros: list[dict], ativos_por_isin: dict[str, int]) -> int:
    gravados = 0
    for r in registros:
        ativo_id = ativos_por_isin.get(r["isin"])
        if ativo_id is None:
            continue
        valores = {k: v for k, v in r.items() if k != "isin"}
        valores.update(ativo_id=ativo_id, **ctx.procedencia(r["data_com"]))
        stmt = insert(Provento).values(**valores)
        # A data de pagamento pode ser divulgada depois do anúncio: atualiza no reprocessamento.
        stmt = stmt.on_conflict_do_update(
            index_elements=["ativo_id", "tipo", "data_com", "valor_por_cota"],
            set_={"data_pagamento": stmt.excluded.data_pagamento, "data_aprovacao": stmt.excluded.data_aprovacao,
                  "lote_ingestao_id": stmt.excluded.lote_ingestao_id, "coletado_em": stmt.excluded.coletado_em})
        ctx.sessao.execute(stmt)
        gravados += 1
    return gravados


def ingerir(sessao, codigos: list[str] | None = None, cliente=None, pausa: float = 0.3) -> int:
    """Uma consulta por companhia (código de 4 letras do ticker). Falhas isoladas não param as demais."""
    ativos = list(sessao.scalars(select(Ativo).where(Ativo.classe.in_(("ACAO", "UNIT")), Ativo.isin.is_not(None))))
    ativos_por_isin = {a.isin: a.id for a in ativos}
    codigos = codigos or sorted({a.ticker[:4] for a in ativos})
    proprio = cliente is None
    cliente = cliente or cliente_http()
    total, falhas = 0, []
    try:
        with lote(sessao, "B3_PROVENTOS", URL.format(param="*")) as ctx:
            for i, codigo in enumerate(codigos):
                if i and pausa:
                    time.sleep(pausa)
                try:
                    resposta = cliente.get(url_empresa(codigo))
                    if resposta.status_code == 404:
                        continue
                    resposta.raise_for_status()
                    total += gravar(ctx, parse(resposta.json()), ativos_por_isin)
                except Exception as erro:  # uma companhia com problema não interrompe as outras
                    falhas.append(f"{codigo}: {erro!r}"[:120])
            ctx.lote.linhas_gravadas = total
            if falhas:
                ctx.lote.erro = f"{len(falhas)} companhia(s) com falha; ex.: " + "; ".join(falhas[:5])
                log.warning("B3 proventos: %s falha(s), ex.: %s", len(falhas), falhas[:3])
            if codigos and len(falhas) == len(codigos):
                raise RuntimeError("todas as consultas de proventos à B3 falharam: " + falhas[0])
    finally:
        if proprio:
            cliente.close()
    return total
