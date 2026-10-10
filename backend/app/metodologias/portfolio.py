"""Andrew Lo e Stephen Foerster, *Em Busca do Portfólio Perfeito* — teoria moderna de portfólio.

- Retornos, média e covariância anualizadas.
- Retorno e volatilidade da carteira; índice de Sharpe.
- CAPM: β = cov(ativo, mercado) ÷ var(mercado); E[R] = rf + β × (E[Rm] − rf).
- Fronteira eficiente de Markowitz (somente posições compradas, pesos somando 1), carteira de
  mínima variância e carteira de máximo Sharpe.
- Fatores: valor (earnings yield), tamanho (valor de mercado), momento (retorno 12−1 meses), em percentis.
- Diversificação: número efetivo de ativos = 1 ÷ Σw².
"""

from collections.abc import Sequence

import numpy as np
from scipy.optimize import minimize

from app.metodologias.tipos import Resultado, indisponivel, ok

PERIODOS_ANO = 252


def retornos_simples(precos: Sequence[float]) -> np.ndarray:
    p = np.asarray(precos, dtype=float)
    return p[1:] / p[:-1] - 1


def estatisticas(retornos: np.ndarray, periodos_ano: int = PERIODOS_ANO) -> tuple[np.ndarray, np.ndarray]:
    """(média anualizada, covariância anualizada) de uma matriz períodos × ativos."""
    r = np.asarray(retornos, dtype=float)
    return r.mean(axis=0) * periodos_ano, np.cov(r, rowvar=False, ddof=1).reshape(r.shape[1], r.shape[1]) * periodos_ano


def retorno_carteira(pesos: Sequence[float], medias: Sequence[float]) -> float:
    return float(np.dot(pesos, medias))


def volatilidade_carteira(pesos: Sequence[float], cov: np.ndarray) -> float:
    w = np.asarray(pesos, dtype=float)
    return float(np.sqrt(w @ np.asarray(cov) @ w))


def sharpe(retorno: float | None, volatilidade: float | None, taxa_livre_risco: float) -> Resultado:
    """(retorno − rf) ÷ volatilidade."""
    if retorno is None or volatilidade is None:
        return indisponivel("dado indisponível: retorno ou volatilidade")
    if volatilidade <= 0:
        return indisponivel("volatilidade não positiva")
    return ok((retorno - taxa_livre_risco) / volatilidade)


def beta(retornos_ativo: Sequence[float], retornos_mercado: Sequence[float]) -> Resultado:
    """β = cov(ativo, mercado) ÷ var(mercado), com as duas séries alinhadas."""
    a, m = np.asarray(retornos_ativo, float), np.asarray(retornos_mercado, float)
    if len(a) != len(m) or len(a) < 3:
        return indisponivel("séries desalinhadas ou curtas demais (mínimo 3 observações)")
    var_m = np.var(m, ddof=1)
    if var_m == 0:
        return indisponivel("mercado sem variação")
    return ok(float(np.cov(a, m, ddof=1)[0, 1] / var_m))


def capm(taxa_livre_risco: float, beta_: float, retorno_mercado: float) -> Resultado:
    """E[R] = rf + β × (E[Rm] − rf)."""
    return ok(taxa_livre_risco + beta_ * (retorno_mercado - taxa_livre_risco))


def _otimizar(objetivo, n: int, restricoes: list[dict]) -> np.ndarray | None:
    w0 = np.full(n, 1 / n)
    res = minimize(objetivo, w0, method="SLSQP", bounds=[(0.0, 1.0)] * n,
                   constraints=[{"type": "eq", "fun": lambda w: w.sum() - 1}, *restricoes],
                   options={"ftol": 1e-12, "maxiter": 500})
    return res.x if res.success else None


def minima_variancia(cov: np.ndarray) -> Resultado:
    """Carteira de mínima variância global (somente compradas)."""
    cov = np.asarray(cov, float)
    w = _otimizar(lambda w: w @ cov @ w, cov.shape[0], [])
    if w is None:
        return indisponivel("otimização não convergiu")
    return ok(volatilidade_carteira(w, cov), pesos=w.round(10).tolist())


def maximo_sharpe(medias: Sequence[float], cov: np.ndarray, taxa_livre_risco: float) -> Resultado:
    """Carteira tangente (máximo Sharpe, somente compradas)."""
    mu, cov = np.asarray(medias, float), np.asarray(cov, float)
    if np.all(mu <= taxa_livre_risco):
        return indisponivel("nenhum ativo com retorno esperado acima da taxa livre de risco")
    w = _otimizar(lambda w: -(w @ mu - taxa_livre_risco) / np.sqrt(w @ cov @ w), len(mu), [])
    if w is None:
        return indisponivel("otimização não convergiu")
    ret, vol = retorno_carteira(w, mu), volatilidade_carteira(w, cov)
    return ok((ret - taxa_livre_risco) / vol, pesos=w.round(10).tolist(), retorno=ret, volatilidade=vol)


def fronteira_eficiente(medias: Sequence[float], cov: np.ndarray, pontos: int = 20) -> Resultado:
    """Pontos (volatilidade, retorno, pesos) da fronteira, do mínimo de variância ao maior retorno."""
    mu, cov = np.asarray(medias, float), np.asarray(cov, float)
    if len(mu) < 2:
        return indisponivel("a fronteira exige ao menos 2 ativos")
    mv = minima_variancia(cov)
    if not mv.disponivel:
        return mv
    r_min, r_max = retorno_carteira(mv.detalhes["pesos"], mu), float(mu.max())
    curva = []
    for alvo in np.linspace(r_min, r_max, pontos):
        w = _otimizar(lambda w: w @ cov @ w, len(mu), [{"type": "eq", "fun": lambda w, a=alvo: w @ mu - a}])
        if w is not None:
            curva.append({"retorno": float(alvo), "volatilidade": volatilidade_carteira(w, cov),
                          "pesos": w.round(10).tolist()})
    if not curva:
        return indisponivel("otimização não convergiu")
    return ok(len(curva), pontos=curva)


def numero_efetivo_ativos(pesos: Sequence[float]) -> Resultado:
    """1 ÷ Σw² (1 = concentrada num ativo; n = igualmente distribuída entre n ativos)."""
    w = np.asarray(pesos, float)
    soma = float((w**2).sum())
    if soma == 0:
        return indisponivel("pesos todos zero")
    return ok(1 / soma)


def momento(precos_mensais: Sequence[float]) -> Resultado:
    """Retorno de 12 meses excluindo o último mês: P(t−1) ÷ P(t−12) − 1 (exige 13 preços mensais)."""
    if len(precos_mensais) < 13:
        return indisponivel("menos de 13 meses de preços")
    p = list(precos_mensais)
    if p[-13] <= 0:
        return indisponivel("preço não positivo")
    return ok(p[-2] / p[-13] - 1)


def percentis(valores: dict[str, float | None]) -> dict[str, float]:
    """Percentil (0–1) de cada ativo dentro do conjunto; ignora valores None."""
    validos = sorted((v, k) for k, v in valores.items() if v is not None)
    n = len(validos)
    if n == 1:
        return {validos[0][1]: 1.0}
    return {k: i / (n - 1) for i, (_, k) in enumerate(validos)}
