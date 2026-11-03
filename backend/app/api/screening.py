"""Stock screening, favoritos e exportação (Fase 3)."""

from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Request, Response
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.auth.seguranca import NOME_COOKIE, usuario_atual, usuario_do_token
from app.db.modelos import Ativo, Favorito, Usuario
from app.db.sessao import obter_sessao
from app.exportacao.tabela import Coluna, para_csv, para_xlsx
from app.servicos.screening import FAIXAS, ORDENACOES, FiltrosScreening, screening_acoes

rotas = APIRouter(tags=["screening"])

COLUNAS_EXPORTACAO = [
    Coluna("posicao", "#", "numero"), Coluna("ticker", "Ticker"), Coluna("nome", "Empresa"),
    Coluna("setor", "Setor"), Coluna("preco", "Cotação", "moeda"), Coluna("data_preco", "Data da cotação"),
    Coluna("dy", "DY 12m", "percentual"), Coluna("p_l", "P/L", "numero"), Coluna("p_vp", "P/VP", "numero"),
    Coluna("roe", "ROE", "percentual"), Coluna("margem_liquida", "Margem líquida", "percentual"),
    Coluna("dl_ebitda", "Dív. líq./EBITDA", "numero"), Coluna("liquidez", "Liquidez diária", "moeda"),
    Coluna("graham_valor", "Graham: valor intrínseco", "moeda"),
    Coluna("graham_margem", "Graham: margem", "percentual"),
    Coluna("bazin_teto", "Bazin: preço teto", "moeda"), Coluna("bazin_margem", "Bazin: margem", "percentual"),
    Coluna("lynch_valor", "Lynch: preço justo", "moeda"), Coluna("lynch_margem", "Lynch: margem", "percentual"),
    Coluna("lynch_peg", "PEG", "numero"),
    Coluna("earnings_yield", "Greenblatt: earnings yield", "percentual"),
    Coluna("retorno_capital", "Greenblatt: retorno s/ capital", "percentual"),
    Coluna("greenblatt_posicao", "Greenblatt: posição", "numero"),
]
FONTES_EXPORTACAO = "CVM (balanços, ODbL) e Yahoo Finance (cotações e dividendos)"


def _favoritos(sessao: Session, usuario_id: int) -> set[str]:
    return set(sessao.scalars(select(Ativo.ticker).join(Favorito, Favorito.ativo_id == Ativo.id)
                              .where(Favorito.usuario_id == usuario_id)))


def _filtros(
    request: Request,
    ordenar_por: str = "graham",
    setores: list[str] = Query(default=[]),
    besst: bool = False,
    somente_favoritos: bool = False,
    yield_bazin: float = Query(0.06, gt=0, le=0.5),
    fator_graham: float = Query(22.5, gt=0, le=100),
    fator_lynch: float = Query(1.0, gt=0, le=5),
    sessao: Session = Depends(obter_sessao),
    sessao_cookie: str | None = Cookie(default=None, alias=NOME_COOKIE),
) -> FiltrosScreening:
    if ordenar_por not in ORDENACOES:
        raise HTTPException(422, f"ordenar_por deve ser um de {', '.join(ORDENACOES)}")
    faixas = {}
    for nome in FAIXAS:  # ex.: dy_min=0.06&p_l_max=12
        limites = []
        for lado in ("min", "max"):
            texto = request.query_params.get(f"{nome}_{lado}")
            try:
                limites.append(float(texto) if texto not in (None, "") else None)
            except ValueError as erro:
                raise HTTPException(422, f"{nome}_{lado} precisa ser um número") from erro
        if any(v is not None for v in limites):
            faixas[nome] = tuple(limites)
    tickers = None
    if somente_favoritos:
        usuario = usuario_do_token(sessao_cookie, sessao)
        if usuario is None:
            raise HTTPException(401, "entre na sua conta para filtrar pelos favoritos")
        tickers = frozenset(_favoritos(sessao, usuario.id))
    return FiltrosScreening(faixas=faixas, setores=tuple(setores), besst=besst, tickers=tickers,
                            ordenar_por=ordenar_por, yield_bazin=yield_bazin, fator_graham=fator_graham,
                            fator_lynch=fator_lynch)


@rotas.get("/screening/acoes")
def screening(filtros: FiltrosScreening = Depends(_filtros), sessao: Session = Depends(obter_sessao)):
    return screening_acoes(sessao, filtros)


@rotas.get("/screening/acoes/exportar")
def exportar(formato: str = "xlsx", filtros: FiltrosScreening = Depends(_filtros),
             sessao: Session = Depends(obter_sessao)):
    if formato not in ("xlsx", "csv"):
        raise HTTPException(422, "formato deve ser xlsx ou csv")
    r = screening_acoes(sessao, filtros)
    args = (r["itens"], COLUNAS_EXPORTACAO, r["aviso"], FONTES_EXPORTACAO, r["atualizado_em"])
    if formato == "csv":
        conteudo, tipo = para_csv(*args), "text/csv; charset=utf-8"
    else:
        conteudo = para_xlsx(*args, titulo="Screening de ações")
        tipo = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    nome = f"screening-acoes-{r['atualizado_em'] or 'sem-data'}.{formato}"
    return Response(conteudo, media_type=tipo, headers={"Content-Disposition": f'attachment; filename="{nome}"'})


@rotas.get("/favoritos")
def listar_favoritos(usuario: Usuario = Depends(usuario_atual), sessao: Session = Depends(obter_sessao)):
    return sorted(_favoritos(sessao, usuario.id))


@rotas.put("/favoritos/{ticker}", status_code=204)
def favoritar(ticker: str, usuario: Usuario = Depends(usuario_atual), sessao: Session = Depends(obter_sessao)):
    ativo = sessao.scalar(select(Ativo).where(Ativo.ticker == ticker.upper()))
    if ativo is None:
        raise HTTPException(404, "ativo não encontrado")
    if sessao.get(Favorito, (usuario.id, ativo.id)) is None:
        sessao.add(Favorito(usuario_id=usuario.id, ativo_id=ativo.id))
        sessao.commit()


@rotas.delete("/favoritos/{ticker}", status_code=204)
def desfavoritar(ticker: str, usuario: Usuario = Depends(usuario_atual), sessao: Session = Depends(obter_sessao)):
    ativo_id = sessao.scalar(select(Ativo.id).where(Ativo.ticker == ticker.upper()))
    if ativo_id is not None:
        sessao.execute(delete(Favorito).where(Favorito.usuario_id == usuario.id, Favorito.ativo_id == ativo_id))
        sessao.commit()
