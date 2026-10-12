"""Linha de comando: `python -m app.jobs.cli <comando>`.

Exemplos:
  python -m app.jobs.cli carga-inicial --de 2019 --ate 2026
  python -m app.jobs.cli macro
  python -m app.jobs.cli proventos
  python -m app.jobs.cli indicadores --tickers PETR4 VALE3
  python -m app.jobs.cli diagnostico PETR4
  python -m app.jobs.cli atualizar-mercado
  python -m app.jobs.cli completar   # organiza balanços pendentes + cotações/dividendos + indicadores
"""

import argparse
import logging
from datetime import date

from app.jobs import tarefas


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser(prog="app.jobs.cli")
    sub = p.add_subparsers(dest="comando", required=True)
    c = sub.add_parser("carga-inicial")
    c.add_argument("--de", type=int, default=date.today().year - 6)
    c.add_argument("--ate", type=int, default=date.today().year)
    sub.add_parser("companhias")
    for nome in ("demonstracoes", "fiis", "cotacoes-historicas"):
        s = sub.add_parser(nome)
        s.add_argument("anos", type=int, nargs="+")
    sub.add_parser("cotacoes-do-dia")
    sub.add_parser("macro")
    pv = sub.add_parser("proventos")
    pv.add_argument("--dias-fnet", type=int, default=400)
    d = sub.add_parser("diagnostico")
    d.add_argument("ticker", nargs="?", default="PETR4")
    sub.add_parser("atualizar-mercado")
    sub.add_parser("completar")
    i = sub.add_parser("indicadores")
    i.add_argument("--tickers", nargs="*")
    a = p.parse_args()

    if a.comando == "diagnostico":
        from app.jobs import diagnostico
        print(diagnostico.executar(a.ticker))
        return
    tarefas.preparar()
    match a.comando:
        case "carga-inicial":
            tarefas.carga_inicial(a.de, a.ate)
        case "companhias":
            tarefas.companhias()
        case "demonstracoes":
            tarefas.demonstracoes(a.anos)
        case "fiis":
            tarefas.fiis(a.anos)
        case "cotacoes-historicas":
            tarefas.cotacoes_historicas(a.anos)
        case "cotacoes-do-dia":
            tarefas.cotacoes_do_dia()
        case "macro":
            tarefas.macro()
        case "proventos":
            tarefas.proventos(a.dias_fnet)
            tarefas.indicadores()
        case "completar":
            tarefas.completar_carga(forcar=True)
        case "atualizar-mercado":
            ano = date.today().year
            tarefas.cotacoes_historicas(list(range(ano - tarefas.ANOS_CARGA_INICIAL, ano + 1)))
            tarefas.indicadores()
        case "indicadores":
            tarefas.indicadores(a.tickers)


if __name__ == "__main__":
    main()
