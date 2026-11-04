from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.sessao import obter_sessao
from app.ingestao.bcb_sgs import SERIES
from app.metodologias.registro import POR_ID, TODAS
from app.servicos import consultas, historico, ranking
from app.servicos.ranking import METODOS, Parametros

rotas = APIRouter(tags=["dados"])


@rotas.get("/acoes")
def listar_acoes(busca: str | None = None, sessao: Session = Depends(obter_sessao)):
    return consultas.listar(sessao, "ACAO", busca)


@rotas.get("/acoes/{ticker}")
def detalhar_acao(ticker: str, sessao: Session = Depends(obter_sessao)):
    dados = consultas.detalhe(sessao, ticker)
    if dados is None or dados["classe"] == "FII" or dados["classe"] in consultas.CLASSES_EUA:
        raise HTTPException(404, "ação não encontrada")
    return dados


@rotas.get("/eua")
def listar_eua(busca: str | None = None, sessao: Session = Depends(obter_sessao)):
    return consultas.listar(sessao, consultas.CLASSES_EUA, busca)


@rotas.get("/eua/{ticker}")
def detalhar_eua(ticker: str, sessao: Session = Depends(obter_sessao)):
    dados = consultas.detalhe(sessao, ticker)
    if dados is None or dados["classe"] not in consultas.CLASSES_EUA:
        raise HTTPException(404, "ativo dos EUA não encontrado")
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


def _ou_404(dados):
    if dados is None:
        raise HTTPException(404, "ativo não encontrado")
    return dados


@rotas.get("/acoes/{ticker}/historico")
def historico_anual(ticker: str, anos: int = Query(10, ge=1, le=20), sessao: Session = Depends(obter_sessao)):
    return _ou_404(historico.historico_anual(sessao, ticker, anos))


@rotas.get("/ativos/{ticker}/dividendos")
def dividendos(ticker: str, anos: int = Query(10, ge=1, le=20), sessao: Session = Depends(obter_sessao)):
    return _ou_404(historico.dividendos(sessao, ticker, anos))


@rotas.get("/ativos/{ticker}/risco")
def risco(ticker: str, sessao: Session = Depends(obter_sessao)):
    return _ou_404(historico.risco(sessao, ticker))


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


@rotas.get("/ranking/acoes")
def ranking_acoes(
    metodo: str = "greenblatt",
    liquidez_minima: float = Query(1_000_000, ge=0),
    yield_bazin: float = Query(0.06, gt=0, le=0.5),
    fator_graham: float = Query(22.5, gt=0, le=100),
    fator_lynch: float = Query(1.0, gt=0, le=5),
    excluir_financeiras: bool = True,
    excluir_utilities: bool = True,
    limite: int = Query(100, ge=1, le=500),
    sessao: Session = Depends(obter_sessao),
):
    if metodo not in METODOS:
        raise HTTPException(422, f"método deve ser um de {', '.join(METODOS)}")
    return ranking.ranking_acoes(sessao, metodo, Parametros(liquidez_minima, yield_bazin, fator_graham, fator_lynch,
                                                            excluir_financeiras, excluir_utilities, limite))


@rotas.get("/ferramentas/impacto-custos")
def impacto_custos(custo_anual: float = Query(..., ge=0, le=0.2), retorno_anual: float = Query(0.07, ge=-0.5, le=1),
                   inicial: float = Query(10000, ge=0), aporte_anual: float = Query(0, ge=0),
                   anos: int = Query(30, ge=1, le=60), custo_comparacao: float = Query(0.0003, ge=0, le=0.2)):
    """Bogle: quanto a taxa anual consome do patrimônio final, comparada a um fundo de custo baixo."""
    from app.metodologias import bogle

    r = bogle.impacto_custos(inicial, aporte_anual, retorno_anual, anos, custo_anual)
    comparacao = bogle.impacto_custos(inicial, aporte_anual, retorno_anual, anos, custo_comparacao)
    serie = [{"ano": n, "sem_custo": bogle.valor_futuro(inicial, aporte_anual, retorno_anual, n),
              "com_custo": bogle.valor_futuro(inicial, aporte_anual, retorno_anual, n, custo_anual),
              "comparacao": bogle.valor_futuro(inicial, aporte_anual, retorno_anual, n, custo_comparacao)}
             for n in range(anos + 1)]
    return {"impacto": r.valor, "impacto_comparacao": comparacao.valor, "serie": serie,
            "metodologia": "bogle.impacto_custos",
            "aviso": "Simulação com retorno constante; não constitui recomendação de investimento."}


@rotas.get("/status")
def status(sessao: Session = Depends(obter_sessao)):
    return consultas.status_dados(sessao)


@rotas.get("/painel")
def painel(sessao: Session = Depends(obter_sessao)):
    """Página inicial: Selic, CDI, IPCA, dólar, Tesouro e maiores variações do último pregão."""
    from app.servicos import painel as servico
    return servico.montar(sessao)
