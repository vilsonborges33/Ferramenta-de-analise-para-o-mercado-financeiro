"""Fase 8: calculadoras, retorno de longo prazo (Siegel) e alertas."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.seguranca import usuario_atual
from app.config import obter_configuracao
from app.db.modelos import Alerta, Ativo, Usuario
from app.db.sessao import obter_sessao
from app.metodologias import ferramentas as f
from app.servicos import alertas as sa
from app.servicos import longo_prazo

rotas = APIRouter(tags=["ferramentas"])


def _r(res):
    return {"valor": res.valor, "motivo_indisponivel": res.motivo_indisponivel, **res.detalhes}


@rotas.get("/ferramentas/juros-compostos")
def juros_compostos(inicial: float = Query(0, ge=0), aporte: float = Query(0, ge=0),
                    taxa: float = Query(..., gt=-1, le=10), periodos: int = Query(..., ge=1, le=1200),
                    taxa_periodo: str = Query("mes", pattern="^(mes|ano)$")):
    """M_t = M_{t−1} × (1 + i) + aporte, aporte no fim de cada mês. Taxa anual vira mensal equivalente."""
    mensal = taxa if taxa_periodo == "mes" else f.taxa_equivalente(taxa, "ano", "mes").valor
    return {**_r(f.juros_compostos(inicial, aporte, mensal, periodos)), "taxa_mensal": mensal}


@rotas.get("/ferramentas/taxa-equivalente")
def taxa_equivalente(taxa: float = Query(..., gt=-1, le=100), origem: str = "mes", destino: str = "ano",
                     inflacao: float | None = Query(None, gt=-1, le=10)):
    """(1 + i_destino) = (1 + i_origem)^(n_origem / n_destino); opcional: taxa real anual por Fisher."""
    res = _r(f.taxa_equivalente(taxa, origem, destino))
    if inflacao is not None and res["valor"] is not None:
        anual = res["todas"]["ano"]
        res["real_anual"] = f.taxa_real(anual, inflacao).valor
    return res


@rotas.get("/ferramentas/aposentadoria")
def aposentadoria(inicial: float = Query(0, ge=0), aporte_mensal: float = Query(0, ge=0),
                  retorno_anual: float = Query(..., gt=-1, le=2), anos: int = Query(..., ge=1, le=80),
                  dividend_yield: float = Query(..., gt=0, le=1), meta_renda_mensal: float = Query(..., ge=0)):
    return _r(f.plano_aposentadoria(inicial, aporte_mensal, retorno_anual, anos, dividend_yield, meta_renda_mensal))


@rotas.get("/longo-prazo")
def retorno_longo_prazo(tickers: str = "", desde: date = date(2020, 1, 1), anos_cape: int = Query(10, ge=3, le=10),
                        sessao: Session = Depends(obter_sessao)):
    lista = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    return longo_prazo.longo_prazo(sessao, lista, desde, anos_cape)


# ------------------------------------------------------------------ alertas


class NovoAlerta(BaseModel):
    ticker: str
    tipo: str
    valor: float | None = None
    repetir_dias: int = Field(default=7, ge=1, le=90)
    canal: str = Field(default="email", pattern="^(email|tela)$")


def _json(sessao: Session, a: Alerta) -> dict:
    ativo = sessao.get(Ativo, a.ativo_id)
    return {"id": a.id, "ticker": ativo.ticker, "classe": ativo.classe, "tipo": a.condicao.get("tipo"),
            "valor": a.condicao.get("valor"), "repetir_dias": a.condicao.get("repetir_dias", 7), "canal": a.canal,
            "ativo": a.ativo, "descricao": sa.descrever(a.condicao.get("tipo"), a.condicao.get("valor")),
            "ultimo_disparo": a.ultimo_disparo.isoformat() if a.ultimo_disparo else None, **sa.situacao(sessao, a)}


@rotas.get("/alertas/condicoes")
def condicoes():
    return {"condicoes": [{"tipo": t, "rotulo": r, "percentual": t in sa.PERCENTUAIS, "precisa_valor": c != "teto"}
                          for t, (r, _, c) in sa.CONDICOES.items()],
            "email_configurado": bool(obter_configuracao().smtp_host)}


@rotas.get("/alertas")
def listar_alertas(usuario: Usuario = Depends(usuario_atual), sessao: Session = Depends(obter_sessao)):
    return [_json(sessao, a) for a in sessao.scalars(select(Alerta).where(Alerta.usuario_id == usuario.id)
                                                      .order_by(Alerta.id.desc()))]


@rotas.post("/alertas", status_code=201)
def criar_alerta(novo: NovoAlerta, usuario: Usuario = Depends(usuario_atual), sessao: Session = Depends(obter_sessao)):
    if novo.tipo not in sa.CONDICOES:
        raise HTTPException(422, "condição desconhecida")
    if sa.CONDICOES[novo.tipo][2] != "teto" and novo.valor is None:
        raise HTTPException(422, "informe o valor da condição")
    ativo = sessao.scalar(select(Ativo).where(Ativo.ticker == novo.ticker.strip().upper()))
    if ativo is None:
        raise HTTPException(422, f"ticker {novo.ticker.upper()} não encontrado")
    a = Alerta(usuario_id=usuario.id, ativo_id=ativo.id, canal=novo.canal, ativo=True,
               condicao={"tipo": novo.tipo, "valor": novo.valor, "repetir_dias": novo.repetir_dias})
    sessao.add(a)
    sessao.commit()
    return _json(sessao, a)


@rotas.delete("/alertas/{alerta_id}", status_code=204)
def apagar_alerta(alerta_id: int, usuario: Usuario = Depends(usuario_atual), sessao: Session = Depends(obter_sessao)):
    a = sessao.get(Alerta, alerta_id)
    if a is None or a.usuario_id != usuario.id:
        raise HTTPException(404, "alerta não encontrado")
    sessao.delete(a)
    sessao.commit()
