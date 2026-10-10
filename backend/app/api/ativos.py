from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.sessao import obter_sessao
from app.ingestao.bcb_sgs import SERIES
from app.metodologias.registro import POR_ID, TODAS
from app.servicos import consultas

rotas = APIRouter(tags=["dados"])


@rotas.get("/acoes")
def listar_acoes(busca: str | None = None, sessao: Session = Depends(obter_sessao)):
    return consultas.listar(sessao, "ACAO", busca)


@rotas.get("/acoes/{ticker}")
def detalhar_acao(ticker: str, sessao: Session = Depends(obter_sessao)):
    dados = consultas.detalhe(sessao, ticker)
    if dados is None or dados["classe"] == "FII":
        raise HTTPException(404, "ação não encontrada")
    return dados


@rotas.get("/fiis")
def listar_fiis(busca: str | None = None, sessao: Session = Depends(obter_sessao)):
    return consultas.listar(sessao, "FII", busca)


@rotas.get("/fiis/{ticker}")
def detalhar_fii(ticker: str, sessao: Session = Depends(obter_sessao)):
    dados = consultas.detalhe(sessao, ticker)
    if dados is None or dados["classe"] != "FII":
        raise HTTPException(404, "fundo não encontrado")
    return dados


@rotas.get("/ativos/{ticker}/cotacoes")
def cotacoes(ticker: str, sessao: Session = Depends(obter_sessao)):
    return consultas.historico_cotacoes(sessao, ticker)


@rotas.get("/metodologias")
def metodologias():
    return [m.como_dict() for m in TODAS]


@rotas.get("/metodologias/{metrica_id}")
def metodologia(metrica_id: str):
    if metrica_id not in POR_ID:
        raise HTTPException(404, "métrica não encontrada")
    return POR_ID[metrica_id].como_dict()


@rotas.get("/series/{codigo}")
def serie(codigo: str, desde: date | None = None, sessao: Session = Depends(obter_sessao)):
    if codigo not in SERIES:
        raise HTTPException(404, "série desconhecida")
    _, descricao, unidade = SERIES[codigo]
    return {"codigo": codigo, "descricao": descricao, "unidade": unidade, "fonte": "BCB_SGS",
            "pontos": consultas.serie(sessao, codigo, desde)}


@rotas.get("/tesouro/taxas")
def tesouro(sessao: Session = Depends(obter_sessao)):
    return {"fonte": "TESOURO_TD", "titulos": consultas.taxas_tesouro(sessao)}
