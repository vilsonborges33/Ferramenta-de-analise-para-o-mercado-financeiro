from datetime import UTC, datetime, timedelta

from app.jobs import agendador


def test_atualizacao_ao_ligar_roda_imediatamente():
    """O container roda em UTC: a tarefa de inicialização não pode ser adiada pelo fuso de Brasília."""
    job = agendador.montar().get_job("atualizar_ao_iniciar")
    assert abs(job.next_run_time - datetime.now(UTC)) < timedelta(minutes=1)
