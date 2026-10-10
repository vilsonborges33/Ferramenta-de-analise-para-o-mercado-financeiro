import re
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.seguranca import NOME_COOKIE, conferir_senha, emitir_token, gerar_hash, usuario_atual
from app.config import obter_configuracao
from app.db.modelos import Usuario
from app.db.sessao import obter_sessao

rotas = APIRouter(prefix="/auth", tags=["autenticação"])


class Credenciais(BaseModel):
    email: str
    senha: str

    @field_validator("email")
    @classmethod
    def email_valido(cls, v: str) -> str:
        v = v.strip().lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", v):
            raise ValueError("e-mail inválido")
        return v


class Registro(Credenciais):
    nome: str | None = None

    @field_validator("senha")
    @classmethod
    def senha_forte(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("a senha precisa ter ao menos 8 caracteres")
        return v


class UsuarioSaida(BaseModel):
    id: int
    email: str
    nome: str | None


def _definir_cookie(resposta: Response, usuario_id: int) -> None:
    cfg = obter_configuracao()
    resposta.set_cookie(NOME_COOKIE, emitir_token(usuario_id), httponly=True, samesite="lax",
                        secure=cfg.cookie_seguro, max_age=cfg.jwt_expiracao_horas * 3600)


@rotas.post("/registrar", response_model=UsuarioSaida, status_code=status.HTTP_201_CREATED)
def registrar(dados: Registro, resposta: Response, sessao: Session = Depends(obter_sessao)):
    if sessao.scalar(select(Usuario).where(Usuario.email == dados.email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "e-mail já cadastrado")
    usuario = Usuario(email=dados.email, hash_senha=gerar_hash(dados.senha), nome=dados.nome)
    sessao.add(usuario)
    sessao.commit()
    _definir_cookie(resposta, usuario.id)
    return UsuarioSaida(id=usuario.id, email=usuario.email, nome=usuario.nome)


@rotas.post("/entrar", response_model=UsuarioSaida)
def entrar(dados: Credenciais, resposta: Response, sessao: Session = Depends(obter_sessao)):
    usuario = sessao.scalar(select(Usuario).where(Usuario.email == dados.email))
    if usuario is None or not usuario.ativo or not conferir_senha(usuario.hash_senha, dados.senha):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "e-mail ou senha incorretos")
    usuario.ultimo_login = datetime.now(UTC)
    sessao.commit()
    _definir_cookie(resposta, usuario.id)
    return UsuarioSaida(id=usuario.id, email=usuario.email, nome=usuario.nome)


@rotas.post("/sair", status_code=status.HTTP_204_NO_CONTENT)
def sair(resposta: Response):
    resposta.delete_cookie(NOME_COOKIE)


@rotas.get("/eu", response_model=UsuarioSaida)
def eu(usuario: Usuario = Depends(usuario_atual)):
    return UsuarioSaida(id=usuario.id, email=usuario.email, nome=usuario.nome)
