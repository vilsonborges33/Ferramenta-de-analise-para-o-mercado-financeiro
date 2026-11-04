"""Valuation (Fase 4): premissas, cálculo, comparativo, "Meus valuations" e exportação do DCF."""

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.seguranca import usuario_atual
from app.db.modelos import Ativo, Usuario, ValuationSalvo
from app.db.sessao import obter_sessao
from app.exportacao.dcf_xlsx import dcf_para_xlsx
from app.servicos import valuation as sv

rotas = APIRouter(tags=["valuation"])
FONTES = "CVM (demonstrações padronizadas, ODbL), Yahoo Finance (cotação e dividendos), Banco Central (Selic)"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class Pedido(BaseModel):
    metodo: str
    premissas: dict = Field(default_factory=dict)


class NovoValuation(Pedido):
    ticker: str
    nome: str = Field(min_length=1, max_length=200)
    narrativa: str | None = Field(default=None, max_length=5000)


def _insumos(sessao: Session, ticker: str) -> sv.Insumos:
    ins = sv.carregar_insumos(sessao, ticker)
    if ins is None:
        raise HTTPException(404, "ação não encontrada (valuation disponível para ações)")
    return ins


def _calcular(ins: sv.Insumos, metodo: str, premissas: dict) -> dict:
    try:
        return sv.calcular(ins, metodo, premissas)
    except sv.ErroValuation as erro:
        raise HTTPException(422, str(erro)) from erro


@rotas.get("/valuation/{ticker}")
def inicio(ticker: str, sessao: Session = Depends(obter_sessao)):
    """Insumos, premissas padrão de cada método e o comparativo com as premissas padrão."""
    ins = _insumos(sessao, ticker)
    return {"insumos": ins.como_dict(), "premissas": sv.premissas_padrao(ins), "comparativo": sv.comparar(ins),
            "metodos": [{"id": m, "nome": sv.NOMES[m], "metodologia": sv.METRICA_REGISTRO[m]} for m in sv.METODOS],
            "aviso": sv.AVISO_NAO_RECOMENDACAO}


@rotas.post("/valuation/{ticker}/calcular")
def calcular(ticker: str, pedido: Pedido, sessao: Session = Depends(obter_sessao)):
    return _calcular(_insumos(sessao, ticker), pedido.metodo, pedido.premissas)


def _xlsx(ticker: str, resultado: dict, acoes: float | None) -> Response:
    if resultado["metodo"] not in ("dcf_fcff", "dcf_fcfe"):
        raise HTTPException(422, "a exportação com fórmulas está disponível para os DCFs")
    conteudo = dcf_para_xlsx(resultado, ticker, acoes, resultado["aviso"], FONTES)
    nome = f"dcf-{ticker.lower()}-{resultado['metodo'].removeprefix('dcf_')}.xlsx"
    return Response(conteudo, media_type=XLSX, headers={"Content-Disposition": f'attachment; filename="{nome}"'})


@rotas.post("/valuation/{ticker}/exportar")
def exportar(ticker: str, pedido: Pedido, sessao: Session = Depends(obter_sessao)):
    ins = _insumos(sessao, ticker)
    return _xlsx(ins.ticker, _calcular(ins, pedido.metodo, pedido.premissas), ins.acoes)


def _como_dict(v: ValuationSalvo, ticker: str) -> dict:
    return {"id": v.id, "ticker": ticker, "metodo": v.metodo, "nome_metodo": sv.NOMES.get(v.metodo, v.metodo),
            "nome": v.nome, "narrativa": v.narrativa, "premissas": v.parametros, "resultado": v.resultado,
            "insumos": v.insumos_snapshot, "criado_em": v.criado_em.isoformat() if v.criado_em else None,
            "atualizado_em": v.atualizado_em.isoformat() if v.atualizado_em else None}


@rotas.get("/valuations")
def listar(ticker: str | None = None, usuario: Usuario = Depends(usuario_atual),
           sessao: Session = Depends(obter_sessao)):
    consulta = (select(ValuationSalvo, Ativo.ticker).join(Ativo, Ativo.id == ValuationSalvo.ativo_id)
                .where(ValuationSalvo.usuario_id == usuario.id).order_by(ValuationSalvo.atualizado_em.desc()))
    if ticker:
        consulta = consulta.where(Ativo.ticker == ticker.upper())
    return [_como_dict(v, t) for v, t in sessao.execute(consulta)]


@rotas.post("/valuations", status_code=201)
def salvar(novo: NovoValuation, usuario: Usuario = Depends(usuario_atual), sessao: Session = Depends(obter_sessao)):
    ins = _insumos(sessao, novo.ticker)
    resultado = _calcular(ins, novo.metodo, novo.premissas)
    ativo_id = sessao.scalar(select(Ativo.id).where(Ativo.ticker == ins.ticker))
    # O retrato dos insumos permite reproduzir o cálculo mesmo depois de novos balanços e cotações.
    v = ValuationSalvo(usuario_id=usuario.id, ativo_id=ativo_id, metodo=novo.metodo, nome=novo.nome.strip(),
                       parametros=resultado["premissas"], narrativa=novo.narrativa, resultado=resultado,
                       insumos_snapshot=ins.como_dict())
    sessao.add(v)
    sessao.commit()
    sessao.refresh(v)
    return _como_dict(v, ins.ticker)


def _meu(sessao: Session, usuario: Usuario, id_: int) -> tuple[ValuationSalvo, str]:
    linha = sessao.execute(select(ValuationSalvo, Ativo.ticker).join(Ativo, Ativo.id == ValuationSalvo.ativo_id)
                           .where(ValuationSalvo.id == id_, ValuationSalvo.usuario_id == usuario.id)).first()
    if linha is None:
        raise HTTPException(404, "valuation não encontrado")
    return linha[0], linha[1]


@rotas.delete("/valuations/{id_}", status_code=204)
def apagar(id_: int, usuario: Usuario = Depends(usuario_atual), sessao: Session = Depends(obter_sessao)):
    v, _ = _meu(sessao, usuario, id_)
    sessao.delete(v)
    sessao.commit()


@rotas.get("/valuations/{id_}/exportar.xlsx")
def exportar_salvo(id_: int, usuario: Usuario = Depends(usuario_atual), sessao: Session = Depends(obter_sessao)):
    v, ticker = _meu(sessao, usuario, id_)
    return _xlsx(ticker, v.resultado, (v.insumos_snapshot or {}).get("acoes"))
