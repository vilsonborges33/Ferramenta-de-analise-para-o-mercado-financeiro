"""Fundos imobiliários (Fase 5): dados do fundo, Gordon ajustado, documentos do FNET e Fund Screening."""

from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session

from app.api.screening import _favoritos
from app.auth.seguranca import NOME_COOKIE, usuario_do_token
from app.db.sessao import obter_sessao
from app.exportacao.tabela import Coluna, para_csv, para_xlsx
from app.servicos import fundos

rotas = APIRouter(tags=["fundos imobiliários"])

COLUNAS = [
    Coluna("posicao", "#", "numero"), Coluna("ticker", "Ticker"), Coluna("nome", "Fundo"),
    Coluna("segmento", "Segmento"), Coluna("tipo", "Tipo"), Coluna("preco", "Cotação", "moeda"),
    Coluna("data_preco", "Data da cotação"), Coluna("dy", "DY 12m", "percentual"), Coluna("p_vp", "P/VP", "numero"),
    Coluna("patrimonio", "Patrimônio líquido", "moeda"), Coluna("liquidez", "Liquidez diária", "moeda"),
    Coluna("vacancia", "Vacância", "percentual"), Coluna("alavancagem", "Alavancagem", "percentual"),
    Coluna("cotistas", "Cotistas", "numero"), Coluna("gordon_teto", "Gordon ajustado: preço teto", "moeda"),
    Coluna("gordon_margem", "Gordon ajustado: margem", "percentual"),
]
FONTES = "CVM (informes de FII, ODbL), Yahoo Finance (cotações e rendimentos), Tesouro Transparente"


def _ou_404(dados):
    if dados is None:
        raise HTTPException(404, "fundo não encontrado")
    return dados


@rotas.get("/fiis/{ticker}/fundo")
def fundo(ticker: str, sessao: Session = Depends(obter_sessao)):
    return _ou_404(fundos.detalhe_fundo(sessao, ticker))


@rotas.get("/fiis/{ticker}/gordon")
def gordon(ticker: str, base: str = "prefixado", taxa: float | None = Query(None, gt=0, le=1),
           premio: float = Query(fundos.PREMIO_PADRAO, ge=-0.1, le=0.5),
           crescimento: float = Query(fundos.CRESCIMENTO_PADRAO, ge=-0.1, le=0.3), liquida: bool = True,
           sessao: Session = Depends(obter_sessao)):
    if base not in fundos.BASES:
        raise HTTPException(422, f"base deve ser uma de {', '.join(fundos.BASES)}")
    return _ou_404(fundos.gordon_fundo(sessao, ticker, base, taxa, premio, crescimento, liquida))


@rotas.get("/fiis/{ticker}/documentos")
def documentos(ticker: str, sessao: Session = Depends(obter_sessao)):
    return _ou_404(fundos.documentos_fnet(sessao, ticker))


def _filtros(request: Request, ordenar_por: str = "gordon", segmentos: list[str] = Query(default=[]),
             tipos: list[str] = Query(default=[]), somente_favoritos: bool = False, base: str = "prefixado",
             premio: float = Query(fundos.PREMIO_PADRAO, ge=-0.1, le=0.5),
             crescimento: float = Query(fundos.CRESCIMENTO_PADRAO, ge=-0.1, le=0.3),
             sessao: Session = Depends(obter_sessao),
             sessao_cookie: str | None = Cookie(default=None, alias=NOME_COOKIE)) -> fundos.FiltrosFii:
    if ordenar_por not in fundos.ORDENACOES_FII:
        raise HTTPException(422, f"ordenar_por deve ser um de {', '.join(fundos.ORDENACOES_FII)}")
    if base not in fundos.BASES:
        raise HTTPException(422, f"base deve ser uma de {', '.join(fundos.BASES)}")
    faixas = {}
    for nome in fundos.FAIXAS_FII:
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
    return fundos.FiltrosFii(faixas=faixas, segmentos=tuple(segmentos), tipos=tuple(tipos), tickers=tickers,
                             ordenar_por=ordenar_por, base=base, premio=premio, crescimento=crescimento)


@rotas.get("/screening/fiis")
def screening(filtros: fundos.FiltrosFii = Depends(_filtros), sessao: Session = Depends(obter_sessao)):
    return fundos.screening_fiis(sessao, filtros)


@rotas.get("/screening/fiis/exportar")
def exportar(formato: str = "xlsx", filtros: fundos.FiltrosFii = Depends(_filtros),
             sessao: Session = Depends(obter_sessao)):
    if formato not in ("xlsx", "csv"):
        raise HTTPException(422, "formato deve ser xlsx ou csv")
    r = fundos.screening_fiis(sessao, filtros)
    args = (r["itens"], COLUNAS, r["aviso"], FONTES, r["atualizado_em"])
    if formato == "csv":
        conteudo, tipo = para_csv(*args), "text/csv; charset=utf-8"
    else:
        conteudo = para_xlsx(*args, titulo="Screening de FIIs")
        tipo = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    nome = f"screening-fiis-{r['atualizado_em'] or 'sem-data'}.{formato}"
    return Response(conteudo, media_type=tipo, headers={"Content-Disposition": f'attachment; filename="{nome}"'})
