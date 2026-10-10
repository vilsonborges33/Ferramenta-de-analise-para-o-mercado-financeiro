"""Processo `worker`: agenda as ingestões (docs/ARQUITETURA.md, seção 8). Horários de Brasília."""

import logging
from datetime import date

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from app.jobs import tarefas

FUSO = "America/Sao_Paulo"


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    tarefas.preparar()
    agendador = BlockingScheduler(timezone=FUSO)
    ano = lambda: [date.today().year]  # noqa: E731
    agendador.add_job(tarefas.macro, CronTrigger(hour=20, minute=0, timezone=FUSO), id="macro")
    agendador.add_job(tarefas.cotacoes_do_dia, CronTrigger(day_of_week="mon-fri", hour=20, minute=30,
                                                            timezone=FUSO), id="cotacoes")
    agendador.add_job(lambda: tarefas.companhias(), CronTrigger(hour=2, minute=0, timezone=FUSO), id="companhias")
    agendador.add_job(lambda: tarefas.demonstracoes(ano()), CronTrigger(hour=3, minute=0, timezone=FUSO),
                      id="demonstracoes")
    agendador.add_job(lambda: tarefas.fiis(ano()), CronTrigger(hour=4, minute=0, timezone=FUSO), id="fiis")
    agendador.add_job(tarefas.indicadores, CronTrigger(hour=5, minute=0, timezone=FUSO), id="indicadores_madrugada")
    agendador.add_job(tarefas.indicadores, CronTrigger(day_of_week="mon-fri", hour=21, minute=15, timezone=FUSO),
                      id="indicadores_noite")
    agendador.start()


if __name__ == "__main__":
    main()
