"""Infraestrutura comum dos conectores: catálogo de fontes, lotes de ingestão e download."""

import hashlib
import logging
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import obter_configuracao
from app.db.modelos import Fonte, LoteIngestao

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class DefinicaoFonte:
    codigo: str
    nome: str
    url: str
    licenca: str


FONTES: tuple[DefinicaoFonte, ...] = (
    DefinicaoFonte("CVM_CADASTRO", "CVM — Cadastro de companhias abertas",
                   "https://dados.cvm.gov.br/dataset/cia_aberta-cad", "ODbL"),
    DefinicaoFonte("CVM_FCA", "CVM — Formulário Cadastral (valores mobiliários)",
                   "https://dados.cvm.gov.br/dataset/cia_aberta-doc-fca", "ODbL"),
    DefinicaoFonte("CVM_DFP", "CVM — Demonstrações Financeiras Padronizadas",
                   "https://dados.cvm.gov.br/dataset/cia_aberta-doc-dfp", "ODbL"),
    DefinicaoFonte("CVM_ITR", "CVM — Informações Trimestrais",
                   "https://dados.cvm.gov.br/dataset/cia_aberta-doc-itr", "ODbL"),
    DefinicaoFonte("CVM_FII_MENSAL", "CVM — Informe mensal de FII",
                   "https://dados.cvm.gov.br/dataset/fii-doc-inf_mensal", "ODbL"),
    DefinicaoFonte("B3_COTAHIST", "B3 — Séries históricas de cotações (COTAHIST)",
                   "https://www.b3.com.br/pt_br/market-data-e-indices/servicos-de-dados/market-data/historico/"
                   "mercado-a-vista/series-historicas/", "Política de Market Data B3 (uso pessoal)"),
    DefinicaoFonte("PROCESSAMENTO_CVM", "Organização dos balanços da CVM por período (processamento interno)",
                   "-", "-"),
    DefinicaoFonte("YAHOO_FINANCE", "Yahoo Finance — cotações e dividendos (API não oficial)",
                   "https://finance.yahoo.com", "Termos do Yahoo restringem uso automatizado; uso pessoal"),
    DefinicaoFonte("B3_PROVENTOS", "B3 — Proventos em dinheiro das companhias listadas",
                   "https://www.b3.com.br/pt_br/produtos-e-servicos/negociacao/renda-variavel/empresas-listadas.htm",
                   "Dados públicos da B3 (uso pessoal; consulta não documentada)"),
    DefinicaoFonte("FNET_RENDIMENTOS", "B3 FNET — Avisos aos cotistas estruturados (rendimentos de FII)",
                   "https://fnet.bmfbovespa.com.br/fnet/publico/abrirGerenciadorDocumentosCVM",
                   "Documentos públicos de fundos (uso pessoal)"),
    DefinicaoFonte("BRAPI", "brapi.dev — cotações e proventos", "https://brapi.dev",
                   "Termos brapi: exibição no próprio app, sem redistribuição"),
    DefinicaoFonte("BCB_SGS", "Banco Central — SGS", "https://dadosabertos.bcb.gov.br", "ODbL"),
    DefinicaoFonte("TESOURO_TD", "Tesouro Transparente — Taxas dos títulos ofertados pelo Tesouro Direto",
                   "https://www.tesourotransparente.gov.br/ckan/dataset/taxas-dos-titulos-ofertados-pelo-tesouro-direto",
                   "Dados abertos (licença a confirmar)"),
)


def garantir_fontes(sessao: Session) -> None:
    existentes = set(sessao.scalars(select(Fonte.codigo)))
    for f in FONTES:
        if f.codigo not in existentes:
            sessao.add(Fonte(codigo=f.codigo, nome=f.nome, url=f.url, licenca=f.licenca))
    sessao.flush()


def obter_fonte(sessao: Session, codigo: str) -> Fonte:
    fonte = sessao.scalar(select(Fonte).where(Fonte.codigo == codigo))
    if fonte is None:
        garantir_fontes(sessao)
        fonte = sessao.scalar(select(Fonte).where(Fonte.codigo == codigo))
    if fonte is None:
        raise ValueError(f"fonte desconhecida: {codigo}")
    return fonte


@dataclass
class Contexto:
    """O que cada linha gravada precisa para registrar a procedência."""

    sessao: Session
    fonte: Fonte
    lote: LoteIngestao
    coletado_em: datetime

    def procedencia(self, data_referencia: date) -> dict:
        return {
            "fonte_id": self.fonte.id,
            "lote_ingestao_id": self.lote.id,
            "data_referencia": data_referencia,
            "coletado_em": self.coletado_em,
        }


@contextmanager
def lote(sessao: Session, codigo_fonte: str, arquivo_origem: str | None = None):
    """Abre um lote de ingestão; em caso de erro desfaz os dados e registra a falha."""
    fonte = obter_fonte(sessao, codigo_fonte)
    registro = LoteIngestao(fonte_id=fonte.id, arquivo_origem=arquivo_origem, status="em_andamento")
    sessao.add(registro)
    sessao.commit()
    ctx = Contexto(sessao, fonte, registro, datetime.now(UTC))
    try:
        yield ctx
        registro.status = "concluido"
        registro.concluido_em = datetime.now(UTC)
        sessao.commit()
    except ArquivoIndisponivel as aviso:
        # Ex.: arquivo diário da B3 ainda não publicado (fim de semana, feriado, antes do fechamento).
        sessao.rollback()
        registro = sessao.get(LoteIngestao, registro.id)
        registro.status = "sem_arquivo"
        registro.erro = str(aviso)[:4000]
        registro.concluido_em = datetime.now(UTC)
        sessao.commit()
        log.info("%s", aviso)
    except Exception as erro:
        sessao.rollback()
        registro = sessao.get(LoteIngestao, registro.id)
        registro.status = "erro"
        registro.erro = repr(erro)[:4000]
        registro.concluido_em = datetime.now(UTC)
        sessao.commit()
        raise


def cliente_http() -> httpx.Client:
    cfg = obter_configuracao()
    return httpx.Client(
        timeout=httpx.Timeout(120.0, connect=20.0),
        follow_redirects=True,
        headers={"User-Agent": cfg.contato_user_agent},
    )


def baixar(url: str, fonte: str, nome_arquivo: str | None = None) -> tuple[Path, str]:
    """Baixa um arquivo para `dados_brutos/<fonte>/<data>/` e devolve (caminho, sha256)."""
    cfg = obter_configuracao()
    destino_dir = cfg.diretorio_dados_brutos / fonte / date.today().isoformat()
    destino_dir.mkdir(parents=True, exist_ok=True)
    destino = destino_dir / (nome_arquivo or url.rsplit("/", 1)[-1].split("?")[0])
    log.info("baixando %s", url)
    with cliente_http() as cliente, cliente.stream("GET", url) as resposta:
        if resposta.status_code == 404:
            raise ArquivoIndisponivel(f"arquivo não publicado (404): {url}")
        resposta.raise_for_status()
        sha = hashlib.sha256()
        with destino.open("wb") as saida:
            for bloco in resposta.iter_bytes():
                sha.update(bloco)
                saida.write(bloco)
    return destino, sha.hexdigest()


# ------------------------------------------------------------------ conversões


def decimal_br(texto: str | None) -> Decimal | None:
    """'1.234,56' → Decimal('1234.56'); vazio → None."""
    if texto is None:
        return None
    texto = str(texto).strip()
    if not texto or texto.lower() in {"nan", "none", "-"}:
        return None
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    try:
        return Decimal(texto)
    except InvalidOperation:
        return None


def data_br(texto: str | None) -> date | None:
    """'31/12/2024' ou '2024-12-31' → date; vazio → None."""
    if texto is None:
        return None
    texto = str(texto).strip()
    if not texto or texto.lower() == "nan":
        return None
    if "/" in texto:
        dia, mes, ano = texto.split("/")
        return date(int(ano), int(mes), int(dia))
    return date.fromisoformat(texto[:10])


class ArquivoIndisponivel(Exception):
    """A fonte ainda não publicou o arquivo pedido; não é erro, o lote fica como "sem_arquivo"."""


class EsquemaInesperado(Exception):
    """A fonte mudou o formato: falha alto em vez de gravar dado errado."""


def exigir_colunas(colunas_presentes, exigidas: set[str], arquivo: str) -> None:
    faltantes = exigidas - set(colunas_presentes)
    if faltantes:
        raise EsquemaInesperado(f"{arquivo}: colunas ausentes {sorted(faltantes)}")
