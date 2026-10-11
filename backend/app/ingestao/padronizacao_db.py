"""Grava a padronização das demonstrações no banco (lógica pura em `padronizacao.py`)."""

import logging

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.modelos import DemonstracaoLinha, DemonstracaoPadronizada, Empresa, Fonte
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
    total, falhas = 0, 0
    for empresa_id, nome in sessao.execute(select(Empresa.id, Empresa.nome)).all():
        try:
            total += padronizar_empresa(sessao, sessao.get(Empresa, empresa_id))
            sessao.commit()
        except Exception:
            sessao.rollback()
            falhas += 1
            log.exception("padronização falhou para %s (id %s)", nome, empresa_id)
    if falhas:
        log.warning("padronização: %s empresa(s) com falha", falhas)
    return total
