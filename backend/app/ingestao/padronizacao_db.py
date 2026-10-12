"""Grava a padronização das demonstrações no banco (lógica pura em `padronizacao.py`)."""

import logging

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.db.modelos import DemonstracaoLinha, DemonstracaoPadronizada, Empresa, Fonte, LoteIngestao
from app.ingestao.base import lote
from app.ingestao.padronizacao import padronizar

log = logging.getLogger(__name__)

_COLUNAS = ("documento", "tipo", "conta_codigo", "conta_descricao", "valor", "data_fim", "data_inicio",
            "versao", "consolidado", "data_referencia", "fonte_id", "lote_ingestao_id", "coletado_em")


def padronizar_empresa(sessao: Session, empresa: Empresa) -> int:
    consulta = select(*[getattr(DemonstracaoLinha, c) for c in _COLUNAS]).where(
        DemonstracaoLinha.empresa_id == empresa.id)
    linhas = [dict(zip(_COLUNAS, r, strict=True)) for r in sessao.execute(consulta)]
    if not linhas:
        return 0
    fontes = {f.codigo: f.id for f in sessao.scalars(select(Fonte))}
    periodos = padronizar(linhas, empresa.tipo_plano_contas)
    sessao.execute(delete(DemonstracaoPadronizada).where(DemonstracaoPadronizada.empresa_id == empresa.id))
    for p in periodos:
        origem = [lin for lin in linhas if lin["documento"] == p.documento and lin["data_referencia"] == p.data_fim]
        ultima = max(origem or linhas, key=lambda lin: lin["coletado_em"])
        sessao.add(DemonstracaoPadronizada(
            empresa_id=empresa.id, periodo=p.periodo, tipo_periodo=p.tipo_periodo, data_inicio=p.data_inicio,
            data_fim=p.data_fim, consolidado=p.consolidado, versao_usada=p.versao_usada, campos=p.campos,
            insumos=p.insumos, fonte_id=fontes.get(f"CVM_{p.documento}", ultima["fonte_id"]),
            lote_ingestao_id=ultima["lote_ingestao_id"], data_referencia=p.data_fim,
            coletado_em=ultima["coletado_em"],
        ))
    return len(periodos)


def padronizar_todas(sessao: Session) -> int:
    """Organiza os balanços de todas as empresas. O resultado (e as falhas) fica em "Status dos dados"."""
    total, falhas, empresas_ok = 0, [], 0
    lote_id = None
    with lote(sessao, "PROCESSAMENTO_CVM", "padronização") as ctx:
        lote_id = ctx.lote.id
    for empresa_id, nome in sessao.execute(select(Empresa.id, Empresa.nome)).all():
        try:
            n = padronizar_empresa(sessao, sessao.get(Empresa, empresa_id))
            sessao.commit()
            total += n
            empresas_ok += 1 if n else 0
        except Exception as erro:
            sessao.rollback()
            falhas.append(f"{nome}: {erro!r}"[:200])
            log.exception("padronização falhou para %s (id %s)", nome, empresa_id)
    registro = sessao.get(LoteIngestao, lote_id)
    registro.linhas_gravadas = total
    registro.erro = (f"{empresas_ok} empresas organizadas; {len(falhas)} com falha. Ex.: " + " | ".join(falhas[:5])
                     if falhas else f"{empresas_ok} empresas organizadas")
    registro.status = "erro" if falhas and not empresas_ok else "concluido"
    sessao.commit()
    if falhas:
        log.warning("padronização: %s empresa(s) com falha", len(falhas))
    return total


def empresas_sem_padronizacao(sessao: Session) -> int:
    """Empresas com linhas de balanço mas nenhum período organizado."""
    com_linhas = select(DemonstracaoLinha.empresa_id).distinct()
    com_periodos = select(DemonstracaoPadronizada.empresa_id).distinct()
    return sessao.scalar(select(func.count()).select_from(com_linhas.except_(com_periodos).subquery())) or 0
