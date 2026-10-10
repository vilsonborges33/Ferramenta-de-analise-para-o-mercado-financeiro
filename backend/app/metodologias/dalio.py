"""Ray Dalio, *Princípios* — diversificação entre fontes de retorno pouco correlacionadas.

- Matriz de correlação dos retornos.
- Contribuição de cada ativo para o risco da carteira.
- Paridade de risco: inverso da volatilidade (ingênua) e contribuições iguais (otimizada).
- Alocação estilo All Weather: pesos de referência por classe, editáveis.
"""

from collections.abc import Sequence

import numpy as np
from scipy.optimize import minimize

from app.metodologias.tipos import Resultado, indisponivel, ok

# Pesos de referência amplamente divulgados para a carteira All Weather (por classe de ativo).
ALL_WEATHER = {
    "acoes": 0.30,
    "titulos_longos": 0.40,
    "titulos_intermediarios": 0.15,
    "ouro": 0.075,
    "commodities": 0.075,
}


def matriz_correlacao(retornos: np.ndarray) -> Resultado:
    """Correlação de Pearson entre as colunas (ativos) de uma matriz períodos × ativos."""
    r = np.asarray(retornos, float)
    if r.ndim != 2 or r.shape[0] < 3 or r.shape[1] < 2:
        return indisponivel("são necessários ao menos 2 ativos e 3 períodos")
    if np.any(r.std(axis=0, ddof=1) == 0):
        return indisponivel("algum ativo sem variação: correlação indefinida")
    c = np.corrcoef(r, rowvar=False)
    fora_diagonal = c[~np.eye(c.shape[0], dtype=bool)]
    return ok(float(fora_diagonal.mean()), matriz=c.round(10).tolist())


def contribuicao_risco(pesos: Sequence[float], cov: np.ndarray) -> Resultado:
    """Fração do risco total vinda de cada ativo: w_i × (Σw)_i ÷ (wᵀΣw). Soma = 1."""
    w, cov = np.asarray(pesos, float), np.asarray(cov, float)
    variancia = float(w @ cov @ w)
    if variancia <= 0:
        return indisponivel("variância da carteira não positiva")
    contrib = w * (cov @ w) / variancia
    return ok(float(np.sqrt(variancia)), contribuicoes=contrib.round(10).tolist())


def paridade_inverso_volatilidade(volatilidades: Sequence[float]) -> Resultado:
    """Pesos ∝ 1/σ (ignora correlações)."""
    v = np.asarray(volatilidades, float)
    if np.any(v <= 0):
        return indisponivel("volatilidade não positiva")
    inv = 1 / v
    return ok(len(v), pesos=(inv / inv.sum()).round(10).tolist())


def paridade_risco(cov: np.ndarray) -> Resultado:
    """Pesos com contribuições de risco iguais (considera correlações), somente compradas."""
    cov = np.asarray(cov, float)
    n = cov.shape[0]

    def objetivo(w):
        var = w @ cov @ w
        contrib = w * (cov @ w) / var
        return float(((contrib - 1 / n) ** 2).sum())

    res = minimize(objetivo, np.full(n, 1 / n), method="SLSQP", bounds=[(1e-6, 1.0)] * n,
                   constraints=[{"type": "eq", "fun": lambda w: w.sum() - 1}], options={"ftol": 1e-14, "maxiter": 500})
    if not res.success:
        return indisponivel("otimização não convergiu")
    return ok(n, pesos=res.x.round(10).tolist())


def alocacao_all_weather(patrimonio: float, pesos: dict[str, float] | None = None) -> Resultado:
    """Valor alvo por classe = patrimônio × peso. Pesos precisam somar 100%."""
    pesos = pesos or ALL_WEATHER
    if abs(sum(pesos.values()) - 1) > 1e-9:
        return indisponivel("os pesos precisam somar 100%")
    return ok(patrimonio, alvos={k: patrimonio * v for k, v in pesos.items()})
