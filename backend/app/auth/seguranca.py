"""Autenticação básica: senha com argon2 e sessão em cookie httpOnly com JWT."""

from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import obter_configuracao
from app.db.modelos import Usuario
from app.db.sessao import obter_sessao

NOME_COOKIE = "sessao"
_hasher = PasswordHasher()


def gerar_hash(senha: str) -> str:
    return _hasher.hash(senha)


def conferir_senha(hash_: str, senha: str) -> bool:
    try:
        return _hasher.verify(hash_, senha)
    except VerificationError:
        return False


def emitir_token(usuario_id: int) -> str:
    cfg = obter_configuracao()
    agora = datetime.now(UTC)
    carga = {"sub": str(usuario_id), "iat": agora, "exp": agora + timedelta(hours=cfg.jwt_expiracao_horas)}
    return jwt.encode(carga, cfg.jwt_segredo, algorithm="HS256")


def usuario_do_token(token: str | None, sessao: Session) -> Usuario | None:
    if not token:
        return None
    try:
        carga = jwt.decode(token, obter_configuracao().jwt_segredo, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    usuario = sessao.get(Usuario, int(carga["sub"]))
    return usuario if usuario and usuario.ativo else None


def usuario_atual(sessao: Session = Depends(obter_sessao),
                  sessao_cookie: str | None = Cookie(default=None, alias=NOME_COOKIE)) -> Usuario:
    usuario = usuario_do_token(sessao_cookie, sessao)
    if usuario is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "não autenticado")
    return usuario
