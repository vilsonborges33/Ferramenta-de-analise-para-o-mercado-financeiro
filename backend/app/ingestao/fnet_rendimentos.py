"""B3 FNET: avisos aos cotistas estruturados (rendimentos e amortizações de FII).

Listagem (consulta pública usada pelo próprio site do FNET, não documentada — DECISOES.md D-025):
  GET https://fnet.bmfbovespa.com.br/fnet/publico/pesquisarGerenciadorDocumentosDados
      ?tipoFundo=1&idCategoriaDocumento=14&idTipoDocumento=41&dataInicial=dd/mm/aaaa&dataFinal=...
Documento (XML estruturado, às vezes entregue em base64):
  GET https://fnet.bmfbovespa.com.br/fnet/publico/downloadDocumento?id={id}

Cada documento é processado uma vez (registro em `fii_documento`). Os campos do XML são lidos pelo nome
da tag, sem depender da posição, para tolerar pequenas variações do leiaute.
"""

import base64
import binascii
import logging
import re
import time
import xml.etree.ElementTree as ET
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.db.modelos import Ativo, Fii, FiiDocumento, Provento
from app.ingestao.base import Contexto, EsquemaInesperado, cliente_http, data_br, decimal_br, lote

log = logging.getLogger(__name__)

URL_LISTA = "https://fnet.bmfbovespa.com.br/fnet/publico/pesquisarGerenciadorDocumentosDados"
URL_DOCUMENTO = "https://fnet.bmfbovespa.com.br/fnet/publico/downloadDocumento?id={id}"
CATEGORIA_AVISO_ESTRUTURADO = 14
TIPO_RENDIMENTOS_AMORTIZACOES = 41
POR_PAGINA = 100


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _texto(elemento: ET.Element, *nomes: str) -> str | None:
    alvos = {n.lower() for n in nomes}
    for e in elemento.iter():
        if _local(e.tag) in alvos and (e.text or "").strip():
            return e.text.strip()
    return None


def decodificar(conteudo: bytes) -> bytes:
    """O FNET entrega o XML puro ou em base64 (às vezes entre aspas)."""
    bruto = conteudo.strip().strip(b'"')
    if bruto.startswith(b"<"):
        return bruto
    try:
        return base64.b64decode(bruto, validate=False)
    except (binascii.Error, ValueError) as erro:
        raise EsquemaInesperado("FNET: documento nem XML nem base64") from erro


def parse_documento(xml: bytes) -> dict:
    """Devolve {cnpj, ticker, isin, eventos: [{tipo, data_com, data_pagamento, data_aprovacao, valor}]}."""
    try:
        raiz = ET.fromstring(xml)
    except ET.ParseError as erro:
        raise EsquemaInesperado(f"FNET: XML inválido ({erro})") from erro
    eventos = []
    for e in raiz.iter():
        nome = _local(e.tag)
        if nome not in ("rendimento", "amortizacao"):
            continue
        valor = decimal_br(_texto(e, "ValorProventoCota", "ValorProvento", "ValorPorCota"))
        data_com = data_br(_texto(e, "DataBase", "DataBaseRendimento"))
        if valor is None or valor <= 0 or data_com is None:
            continue
        eventos.append({
            "tipo": "RENDIMENTO_FII" if nome == "rendimento" else "AMORTIZACAO",
            "valor_por_cota": valor, "data_com": data_com,
            "data_pagamento": data_br(_texto(e, "DataPagamento")),
            "data_aprovacao": data_br(_texto(e, "DataAprovacao")),
        })
    cnpj = _texto(raiz, "CNPJFundo", "CnpjFundo")
    return {
        "cnpj": re.sub(r"\D", "", cnpj or ""),
        "ticker": (_texto(raiz, "CodNegociacao", "CodigoNegociacao") or "").upper() or None,
        "isin": _texto(raiz, "CodigoISIN", "CodISIN"),
        "eventos": eventos,
    }


def listar(cliente, inicio: date, fim: date) -> list[dict]:
    documentos, deslocamento = [], 0
    while True:
        params = {
            "d": 0, "s": deslocamento, "l": POR_PAGINA, "o[0][dataEntrega]": "desc", "tipoFundo": 1,
            "idCategoriaDocumento": CATEGORIA_AVISO_ESTRUTURADO, "idTipoDocumento": TIPO_RENDIMENTOS_AMORTIZACOES,
            "idEspecieDocumento": 0, "dataInicial": inicio.strftime("%d/%m/%Y"), "dataFinal": fim.strftime("%d/%m/%Y"),
        }
        resposta = cliente.get(URL_LISTA, params=params)
        resposta.raise_for_status()
        corpo = resposta.json()
        pagina = corpo.get("data") or []
        documentos.extend(pagina)
        deslocamento += len(pagina)
        if not pagina or deslocamento >= int(corpo.get("recordsTotal") or 0):
            return documentos


def gravar(ctx: Contexto, id_fnet: str, doc: dict, data_entrega: date | None) -> int:
    sessao = ctx.sessao
    ativo_id = None
    if doc["ticker"]:
        ativo_id = sessao.scalar(select(Ativo.id).where(Ativo.ticker == doc["ticker"]))
    if ativo_id is None and doc["isin"]:
        ativo_id = sessao.scalar(select(Ativo.id).where(Ativo.isin == doc["isin"]))
    fii = None
    if doc["cnpj"]:
        fii = next((f for f in sessao.scalars(select(Fii).where(Fii.cnpj.is_not(None)))
                    if re.sub(r"\D", "", f.cnpj) == doc["cnpj"]), None)
    if fii is None and ativo_id is not None:
        fii = sessao.scalar(select(Fii).where(Fii.ativo_id == ativo_id))
    if fii is not None:
        sessao.execute(insert(FiiDocumento).values(
            fii_id=fii.id, tipo="RENDIMENTOS_AMORTIZACOES", data_entrega=data_entrega,
            url_fnet=URL_DOCUMENTO.format(id=id_fnet), id_fnet=str(id_fnet), status="processado",
            **ctx.procedencia(data_entrega or date.today())).on_conflict_do_nothing())
    if ativo_id is None:
        return 0
    gravados = 0
    for ev in doc["eventos"]:
        valores = {**ev, "ativo_id": ativo_id, **ctx.procedencia(ev["data_com"])}
        stmt = insert(Provento).values(**valores)
        stmt = stmt.on_conflict_do_update(
            index_elements=["ativo_id", "tipo", "data_com", "valor_por_cota"],
            set_={"data_pagamento": stmt.excluded.data_pagamento, "lote_ingestao_id": stmt.excluded.lote_ingestao_id,
                  "coletado_em": stmt.excluded.coletado_em})
        sessao.execute(stmt)
        gravados += 1
    return gravados


def ingerir(sessao, dias: int = 10, cliente=None, pausa: float = 0.2) -> int:
    """Processa os avisos de rendimento entregues nos últimos `dias` que ainda não foram lidos."""
    fim = date.today()
    inicio = fim - timedelta(days=dias)
    ja_lidos = set(sessao.scalars(select(FiiDocumento.id_fnet)))
    proprio = cliente is None
    cliente = cliente or cliente_http()
    total, falhas, processados = 0, [], 0
    try:
        with lote(sessao, "FNET_RENDIMENTOS", URL_LISTA) as ctx:
            for meta in listar(cliente, inicio, fim):
                id_fnet = str(meta.get("id"))
                if id_fnet in ja_lidos:
                    continue
                if processados and pausa:
                    time.sleep(pausa)
                processados += 1
                try:
                    resposta = cliente.get(URL_DOCUMENTO.format(id=id_fnet))
                    resposta.raise_for_status()
                    doc = parse_documento(decodificar(resposta.content))
                    entrega = data_br((meta.get("dataEntrega") or "")[:10])
                    total += gravar(ctx, id_fnet, doc, entrega)
                    ja_lidos.add(id_fnet)
                except Exception as erro:
                    falhas.append(f"{id_fnet}: {erro!r}"[:120])
            ctx.lote.linhas_gravadas = total
            if falhas:
                ctx.lote.erro = f"{len(falhas)} documento(s) com falha; ex.: " + "; ".join(falhas[:5])
                log.warning("FNET: %s documento(s) com falha, ex.: %s", len(falhas), falhas[:3])
            if processados and len(falhas) == processados:
                raise RuntimeError("todos os documentos do FNET falharam: " + falhas[0])
    finally:
        if proprio:
            cliente.close()
    return total
