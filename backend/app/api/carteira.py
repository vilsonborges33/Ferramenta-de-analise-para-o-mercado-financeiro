"""Carteira e diário de decisões (Fase 6). Tudo exige login; cada usuário vê só o que é seu."""

import hashlib
from datetime import UTC, date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.auth.seguranca import usuario_atual
from app.db.modelos import (
    ArquivoImportacao,
    Ativo,
    Carteira,
    DiarioDecisao,
    Lancamento,
    PrecoMedioAjuste,
    Usuario,
)
from app.db.sessao import obter_sessao
from app.ingestao import b3_investidor
from app.ingestao.base import EsquemaInesperado
from app.metodologias import carteira as mc
from app.servicos import carteira as sc

rotas = APIRouter(tags=["carteira"])
TAMANHO_MAXIMO_ARQUIVO = 5 * 1024 * 1024


class NovaCarteira(BaseModel):
    nome: str = Field(min_length=1, max_length=200)


class NovoLancamento(BaseModel):
    ticker: str
    tipo: str
    data: date
    quantidade: float = Field(gt=0)
    preco: float = Field(default=0.0, ge=0)
    taxas: float = Field(default=0.0, ge=0)


class AjustePreco(BaseModel):
    preco_medio: float | None = Field(default=None, gt=0)  # None remove o ajuste
    motivo: str | None = Field(default=None, max_length=500)


class Decisao(BaseModel):
    ticker: str | None = None
    data: date
    decisao: str = Field(min_length=1, max_length=200)
    tese: str = Field(min_length=1, max_length=10000)
    premissas: dict = Field(default_factory=dict)
    data_revisao_prevista: date | None = None
    revisao: str | None = Field(default=None, max_length=10000)
    resultado_observado: str | None = Field(default=None, max_length=10000)


def _minha(sessao: Session, usuario: Usuario, carteira_id: int) -> Carteira:
    c = sessao.get(Carteira, carteira_id)
    if c is None or c.usuario_id != usuario.id:
        raise HTTPException(404, "carteira não encontrada")
    return c


def _ativo(sessao: Session, ticker: str) -> Ativo:
    a = sessao.scalar(select(Ativo).where(Ativo.ticker == ticker.strip().upper()))
    if a is None:
        raise HTTPException(422, f"ticker {ticker.upper()} não encontrado")
    return a


def _validar(sessao: Session, carteira_id: int, novos: list[mc.Movimento]) -> None:
    try:
        mc.consolidar(sc.movimentos(sessao, carteira_id) + novos)
    except mc.ErroCarteira as erro:
        raise HTTPException(422, str(erro)) from erro


@rotas.get("/carteiras")
def listar(usuario: Usuario = Depends(usuario_atual), sessao: Session = Depends(obter_sessao)):
    carteiras = sessao.scalars(select(Carteira).where(Carteira.usuario_id == usuario.id).order_by(Carteira.id))
    return [{"id": c.id, "nome": c.nome, "lancamentos": sc.total_lancamentos(sessao, c.id)} for c in carteiras]


@rotas.post("/carteiras", status_code=201)
def criar(nova: NovaCarteira, usuario: Usuario = Depends(usuario_atual), sessao: Session = Depends(obter_sessao)):
    c = Carteira(usuario_id=usuario.id, nome=nova.nome.strip())
    sessao.add(c)
    sessao.commit()
    return {"id": c.id, "nome": c.nome, "lancamentos": 0}


@rotas.patch("/carteiras/{carteira_id}")
def renomear(carteira_id: int, nova: NovaCarteira, usuario: Usuario = Depends(usuario_atual),
             sessao: Session = Depends(obter_sessao)):
    c = _minha(sessao, usuario, carteira_id)
    c.nome = nova.nome.strip()
    sessao.commit()
    return {"id": c.id, "nome": c.nome}


@rotas.delete("/carteiras/{carteira_id}", status_code=204)
def apagar(carteira_id: int, usuario: Usuario = Depends(usuario_atual), sessao: Session = Depends(obter_sessao)):
    c = _minha(sessao, usuario, carteira_id)
    sessao.execute(delete(Lancamento).where(Lancamento.carteira_id == c.id))
    sessao.execute(delete(PrecoMedioAjuste).where(PrecoMedioAjuste.carteira_id == c.id))
    sessao.delete(c)
    sessao.commit()


@rotas.get("/carteiras/{carteira_id}/lancamentos")
def lancamentos(carteira_id: int, usuario: Usuario = Depends(usuario_atual), sessao: Session = Depends(obter_sessao)):
    _minha(sessao, usuario, carteira_id)
    return [{"id": lan.id, "ticker": ticker, "classe": classe, "tipo": lan.tipo, "data": lan.data.isoformat(),
             "quantidade": float(lan.quantidade), "preco": float(lan.preco or 0), "taxas": float(lan.taxas or 0),
             "origem": lan.origem} for lan, ticker, classe in reversed(sc._lancamentos(sessao, carteira_id))]


@rotas.post("/carteiras/{carteira_id}/lancamentos", status_code=201)
def lancar(carteira_id: int, novo: NovoLancamento, usuario: Usuario = Depends(usuario_atual),
           sessao: Session = Depends(obter_sessao)):
    c = _minha(sessao, usuario, carteira_id)
    tipo = novo.tipo.upper()
    if tipo not in mc.TIPOS:
        raise HTTPException(422, f"tipo deve ser um de {', '.join(mc.TIPOS)}")
    ativo = _ativo(sessao, novo.ticker)
    if ativo.mercado != "B3":  # a carteira consolida em reais; ativos em dólar ficam para uma etapa futura
        raise HTTPException(422, f"{ativo.ticker} é negociado nos EUA: por enquanto a carteira aceita só ativos da B3")
    if tipo in ("COMPRA", "VENDA") and novo.preco <= 0:
        raise HTTPException(422, "compra e venda precisam de preço")
    _validar(sessao, c.id, [mc.Movimento(novo.data, ativo.ticker, tipo, novo.quantidade, novo.preco, novo.taxas)])
    lan = Lancamento(carteira_id=c.id, ativo_id=ativo.id, tipo=tipo, data=novo.data,
                     quantidade=Decimal(str(novo.quantidade)), preco=Decimal(str(novo.preco)),
                     taxas=Decimal(str(novo.taxas)), origem="manual")
    sessao.add(lan)
    sessao.commit()
    return {"id": lan.id}


@rotas.delete("/carteiras/{carteira_id}/lancamentos/{lancamento_id}", status_code=204)
def desfazer(carteira_id: int, lancamento_id: int, usuario: Usuario = Depends(usuario_atual),
             sessao: Session = Depends(obter_sessao)):
    c = _minha(sessao, usuario, carteira_id)
    lan = sessao.get(Lancamento, lancamento_id)
    if lan is None or lan.carteira_id != c.id:
        raise HTTPException(404, "lançamento não encontrado")
    sessao.delete(lan)
    sessao.flush()
    try:  # apagar uma compra não pode deixar uma venda posterior sem posição
        mc.consolidar(sc.movimentos(sessao, c.id))
    except mc.ErroCarteira as erro:
        sessao.rollback()
        raise HTTPException(422, f"não dá para apagar: {erro}") from erro
    sessao.commit()


@rotas.post("/carteiras/{carteira_id}/importar")
async def importar(carteira_id: int, request: Request, nome_arquivo: str = "extrato.xlsx",
                   usuario: Usuario = Depends(usuario_atual), sessao: Session = Depends(obter_sessao)):
    """Corpo da requisição = o arquivo .xlsx exportado da Área do Investidor B3 (Negociação ou Movimentação)."""
    c = _minha(sessao, usuario, carteira_id)
    conteudo = await request.body()
    if not conteudo or len(conteudo) > TAMANHO_MAXIMO_ARQUIVO:
        raise HTTPException(422, "envie o arquivo .xlsx da B3 (até 5 MB)")
    try:
        lido = b3_investidor.ler(conteudo)
    except EsquemaInesperado as erro:
        raise HTTPException(422, str(erro)) from erro
    hash_ = hashlib.sha256(conteudo).hexdigest()
    existentes = {(lan.data, ticker, lan.tipo, float(lan.quantidade), round(float(lan.preco or 0), 6))
                  for lan, ticker, _ in sc._lancamentos(sessao, c.id)}
    ativos = {a.ticker: a for a in sessao.scalars(select(Ativo).where(
        Ativo.ticker.in_({m["ticker"] for m in lido["movimentos"]})))}
    erros, novos, repetidos = list(lido["erros"]), [], 0
    for m in lido["movimentos"]:
        if m["ticker"] not in ativos:
            erros.append(f"{m['ticker']} em {m['data']:%d/%m/%Y}: ticker não cadastrado")
            continue
        chave = (m["data"], m["ticker"], m["tipo"], float(m["quantidade"]), round(float(m["preco"]), 6))
        if chave in existentes:
            repetidos += 1  # mesmo arquivo (ou período) importado de novo
            continue
        existentes.add(chave)
        novos.append(m)
    _validar(sessao, c.id, [mc.Movimento(m["data"], m["ticker"], m["tipo"], m["quantidade"], m["preco"])
                            for m in novos])
    registro = ArquivoImportacao(usuario_id=usuario.id, tipo=lido["tipo_arquivo"], nome_arquivo=nome_arquivo[:300],
                                 hash=hash_, processado_em=datetime.now(UTC), linhas_ok=len(novos),
                                 linhas_erro=len(erros))
    sessao.add(registro)
    sessao.flush()
    for m in novos:
        sessao.add(Lancamento(carteira_id=c.id, ativo_id=ativos[m["ticker"]].id, tipo=m["tipo"], data=m["data"],
                              quantidade=Decimal(str(m["quantidade"])), preco=Decimal(str(m["preco"])),
                              taxas=Decimal(0), origem="b3", arquivo_importacao_id=registro.id))
    sessao.commit()
    return {"tipo_arquivo": lido["tipo_arquivo"], "importados": len(novos), "repetidos": repetidos,
            "ignorados": lido["ignoradas"], "erros": erros[:50]}


@rotas.put("/carteiras/{carteira_id}/preco-medio/{ticker}")
def ajustar_preco_medio(carteira_id: int, ticker: str, ajuste: AjustePreco, usuario: Usuario = Depends(usuario_atual),
                        sessao: Session = Depends(obter_sessao)):
    """Preço médio informado à mão (ex.: posição antiga sem histórico). Sem valor, volta ao calculado."""
    c = _minha(sessao, usuario, carteira_id)
    ativo = _ativo(sessao, ticker)
    sessao.execute(delete(PrecoMedioAjuste).where(PrecoMedioAjuste.carteira_id == c.id,
                                                  PrecoMedioAjuste.ativo_id == ativo.id))
    if ajuste.preco_medio is not None:
        sessao.add(PrecoMedioAjuste(carteira_id=c.id, ativo_id=ativo.id, motivo=ajuste.motivo,
                                    preco_medio_manual=Decimal(str(ajuste.preco_medio))))
    sessao.commit()
    return {"ticker": ativo.ticker, "preco_medio": ajuste.preco_medio}


@rotas.get("/carteiras/{carteira_id}/resumo")
def resumo(carteira_id: int, usuario: Usuario = Depends(usuario_atual), sessao: Session = Depends(obter_sessao)):
    return sc.resumo(sessao, _minha(sessao, usuario, carteira_id))


@rotas.get("/carteiras/{carteira_id}/rentabilidade")
def rentabilidade(carteira_id: int, usuario: Usuario = Depends(usuario_atual), sessao: Session = Depends(obter_sessao)):
    return sc.rentabilidade(sessao, _minha(sessao, usuario, carteira_id))


@rotas.get("/carteiras/{carteira_id}/proventos")
def proventos(carteira_id: int, usuario: Usuario = Depends(usuario_atual), sessao: Session = Depends(obter_sessao)):
    return sc.proventos_recebidos(sessao, _minha(sessao, usuario, carteira_id))


@rotas.get("/carteiras/{carteira_id}/otimizador")
def otimizador(carteira_id: int, anos: int = 2, usuario: Usuario = Depends(usuario_atual),
               sessao: Session = Depends(obter_sessao)):
    if not 1 <= anos <= 5:
        raise HTTPException(422, "anos deve estar entre 1 e 5")
    return sc.otimizador(sessao, _minha(sessao, usuario, carteira_id), anos)


# ---------------------------------------------------------------- diário de decisões


def _decisao_dict(d: DiarioDecisao, ticker: str | None) -> dict:
    return {"id": d.id, "ticker": ticker, "data": d.data.isoformat(), "decisao": d.decisao, "tese": d.tese,
            "premissas": d.premissas, "revisao": d.revisao, "resultado_observado": d.resultado_observado,
            "data_revisao_prevista": d.data_revisao_prevista.isoformat() if d.data_revisao_prevista else None,
            "revisao_pendente": bool(d.data_revisao_prevista and d.data_revisao_prevista <= date.today()
                                     and not d.revisao)}


@rotas.get("/diario")
def diario(usuario: Usuario = Depends(usuario_atual), sessao: Session = Depends(obter_sessao)):
    linhas = sessao.execute(select(DiarioDecisao, Ativo.ticker).outerjoin(Ativo, Ativo.id == DiarioDecisao.ativo_id)
                            .where(DiarioDecisao.usuario_id == usuario.id)
                            .order_by(DiarioDecisao.data.desc(), DiarioDecisao.id.desc()))
    return [_decisao_dict(d, t) for d, t in linhas]


def _preencher(d: DiarioDecisao, dados: Decisao, sessao: Session) -> str | None:
    ativo = _ativo(sessao, dados.ticker) if dados.ticker else None
    d.ativo_id = ativo.id if ativo else None
    for campo in ("data", "decisao", "tese", "premissas", "data_revisao_prevista", "revisao", "resultado_observado"):
        setattr(d, campo, getattr(dados, campo))
    return ativo.ticker if ativo else None


@rotas.post("/diario", status_code=201)
def registrar(dados: Decisao, usuario: Usuario = Depends(usuario_atual), sessao: Session = Depends(obter_sessao)):
    d = DiarioDecisao(usuario_id=usuario.id)
    ticker = _preencher(d, dados, sessao)
    sessao.add(d)
    sessao.commit()
    return _decisao_dict(d, ticker)


def _minha_decisao(sessao: Session, usuario: Usuario, id_: int) -> DiarioDecisao:
    d = sessao.get(DiarioDecisao, id_)
    if d is None or d.usuario_id != usuario.id:
        raise HTTPException(404, "registro não encontrado")
    return d


@rotas.put("/diario/{id_}")
def atualizar(id_: int, dados: Decisao, usuario: Usuario = Depends(usuario_atual),
              sessao: Session = Depends(obter_sessao)):
    d = _minha_decisao(sessao, usuario, id_)
    ticker = _preencher(d, dados, sessao)
    sessao.commit()
    return _decisao_dict(d, ticker)


@rotas.delete("/diario/{id_}", status_code=204)
def apagar_decisao(id_: int, usuario: Usuario = Depends(usuario_atual), sessao: Session = Depends(obter_sessao)):
    sessao.delete(_minha_decisao(sessao, usuario, id_))
    sessao.commit()
