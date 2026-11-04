"""Alertas por ativo (Fase 8): o usuário define uma condição sobre preço ou indicador; depois de cada recálculo
os alertas são avaliados e, se a condição for verdadeira, registram o disparo e mandam e-mail (se houver SMTP).

Um alerta disparado só volta a disparar depois de `repetir_dias` (padrão 7), para não mandar e-mail todo dia.
"""

import logging
import smtplib
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import obter_configuracao
from app.db.modelos import Alerta, Ativo, CotacaoDiaria, IndicadorCalculado, Usuario

log = logging.getLogger(__name__)

# tipo → (rótulo, métrica usada, comparação). "preco" = último fechamento.
CONDICOES: dict[str, tuple[str, str, str]] = {
    "preco_abaixo": ("Cotação abaixo de", "preco", "<="),
    "preco_acima": ("Cotação acima de", "preco", ">="),
    "dy_acima": ("Dividend yield 12 m acima de", "basico.dy", ">="),
    "pl_abaixo": ("P/L abaixo de", "basico.p_l", "<="),
    "pvp_abaixo": ("P/VP abaixo de", "pvp", "<="),
    "margem_graham_acima": ("Margem de segurança de Graham acima de", "graham.margem_seguranca", ">="),
    "abaixo_teto_bazin": ("Cotação abaixo do preço teto de Bazin", "bazin.preco_teto", "teto"),
}
PERCENTUAIS = {"dy_acima", "margem_graham_acima"}


def avaliar(tipo: str, limite: float | None, atual: float | None, preco: float | None = None) -> bool | None:
    """Verdadeiro/falso; None quando falta o dado (alerta não dispara com dado indisponível)."""
    if tipo not in CONDICOES or atual is None:
        return None
    comparacao = CONDICOES[tipo][2]
    if comparacao == "teto":
        return None if preco is None else preco <= atual
    if limite is None:
        return None
    return atual <= limite if comparacao == "<=" else atual >= limite


def descrever(tipo: str, limite: float | None) -> str:
    rotulo = CONDICOES.get(tipo, (tipo,))[0]
    if limite is None or CONDICOES.get(tipo, ("", "", ""))[2] == "teto":
        return rotulo
    if tipo in PERCENTUAIS:
        return f"{rotulo} {limite * 100:.2f}%".replace(".", ",")
    return f"{rotulo} {limite:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _valores(sessao: Session, ativo_id: int) -> dict[str, float | None]:
    preco = sessao.scalar(select(CotacaoDiaria.fechamento).where(CotacaoDiaria.ativo_id == ativo_id)
                          .order_by(CotacaoDiaria.data.desc()).limit(1))
    inds = {m: (None if v is None else float(v)) for m, v in sessao.execute(
        select(IndicadorCalculado.metrica, IndicadorCalculado.valor).where(IndicadorCalculado.ativo_id == ativo_id))}
    return {"preco": None if preco is None else float(preco), "pvp": inds.get("fii.p_vp", inds.get("basico.p_vp")),
            **inds}


def situacao(sessao: Session, alerta: Alerta) -> dict:
    tipo = alerta.condicao.get("tipo")
    limite = alerta.condicao.get("valor")
    valores = _valores(sessao, alerta.ativo_id)
    metrica = CONDICOES.get(tipo, ("", "", ""))[1]
    atual = valores.get(metrica)
    preco = valores["preco"]
    return {"atual": atual, "preco": preco, "condicao_verdadeira": avaliar(tipo, limite, atual, preco)}


def _enviar_email(destino: str, assunto: str, corpo: str) -> bool:
    c = obter_configuracao()
    if not c.smtp_host:
        return False
    msg = EmailMessage()
    msg["From"] = c.smtp_remetente or c.smtp_usuario
    msg["To"] = destino
    msg["Subject"] = assunto
    msg.set_content(corpo)
    try:
        with smtplib.SMTP(c.smtp_host, c.smtp_porta, timeout=20) as s:
            s.starttls()
            if c.smtp_usuario:
                s.login(c.smtp_usuario, c.smtp_senha)
            s.send_message(msg)
        return True
    except (OSError, smtplib.SMTPException):
        log.exception("falha ao enviar e-mail de alerta para %s", destino)
        return False


def verificar(sessao: Session, agora: datetime | None = None) -> int:
    """Avalia todos os alertas ativos; devolve quantos dispararam."""
    agora = agora or datetime.now(UTC)
    disparos = 0
    for alerta in sessao.scalars(select(Alerta).where(Alerta.ativo.is_(True))):
        repetir = timedelta(days=int(alerta.condicao.get("repetir_dias", 7)))
        if alerta.ultimo_disparo and agora - alerta.ultimo_disparo < repetir:
            continue
        s = situacao(sessao, alerta)
        if not s["condicao_verdadeira"]:
            continue
        ativo = sessao.get(Ativo, alerta.ativo_id)
        usuario = sessao.get(Usuario, alerta.usuario_id)
        texto = descrever(alerta.condicao.get("tipo"), alerta.condicao.get("valor"))
        corpo = (f"{ativo.ticker}: {texto}.\nValor atual: {s['atual']}\nCotação: {s['preco']}\n\n"
                 "Cálculo automático sobre dados públicos; não constitui recomendação de investimento.")
        if alerta.canal == "email" and usuario is not None:
            _enviar_email(usuario.email, f"Alerta {ativo.ticker}: {texto}", corpo)
        alerta.ultimo_disparo = agora
        disparos += 1
    sessao.commit()
    return disparos
