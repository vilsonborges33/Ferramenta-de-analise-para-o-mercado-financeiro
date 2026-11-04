from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import ativos, auth, carteira, fundos, screening, valuation
from app.config import obter_configuracao

app = FastAPI(title="Análise de Ações e FIIs", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in obter_configuracao().cors_origens.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth.rotas)
app.include_router(ativos.rotas)
app.include_router(screening.rotas)
app.include_router(valuation.rotas)
app.include_router(fundos.rotas)
app.include_router(carteira.rotas)


@app.get("/saude")
def saude():
    return {"status": "ok"}
