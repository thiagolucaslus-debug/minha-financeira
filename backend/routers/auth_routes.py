"""Rotas de autenticação multi-perfil, perfil do usuário e troca de senha."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from auth import (
    create_access_token,
    get_current_user,
    hash_password,
    normalize_username,
    verify_password,
)
from database import get_db, notify_db_changed
from models import Usuario
from schemas import LoginRequest, PasswordChangeRequest, ProfileUpdateRequest, RegisterRequest

router = APIRouter(prefix="/auth", tags=["Autenticação"])


def _serialize_user(user: Usuario) -> dict:
    return {
        "id": user.id,
        "nome": user.nome,
        "username": user.username,
        "tema_preferido": user.tema_preferido,
        "criado_em": user.criado_em.isoformat() if user.criado_em else None,
    }


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    uname = normalize_username(req.username)
    exists = db.scalar(select(Usuario).where(Usuario.username == uname))
    if exists is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Este nome de usuário já está em uso. Escolha outro.",
        )

    user = Usuario(
        nome=req.nome,
        username=uname,
        senha_hash=hash_password(req.senha),
        tema_preferido="dark",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    notify_db_changed("auth_register")

    token = create_access_token(user.id, user.username)
    return {"access_token": token, "token_type": "bearer", "usuario": _serialize_user(user)}


@router.post("/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    uname = normalize_username(req.username)
    user = db.scalar(select(Usuario).where(Usuario.username == uname))
    if user is None or not verify_password(req.senha, user.senha_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário ou senha incorretos.",
        )
    token = create_access_token(user.id, user.username)
    return {"access_token": token, "token_type": "bearer", "usuario": _serialize_user(user)}


@router.get("/me")
def get_me(current_user: Usuario = Depends(get_current_user)):
    return _serialize_user(current_user)


@router.put("/me")
def update_me(
    req: ProfileUpdateRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if req.nome is not None:
        current_user.nome = req.nome
    if req.username is not None:
        new_u = normalize_username(req.username)
        if new_u != current_user.username:
            conflict = db.scalar(
                select(Usuario).where(Usuario.username == new_u, Usuario.id != current_user.id)
            )
            if conflict is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Este nome de usuário já está em uso por outro perfil.",
                )
            current_user.username = new_u
    if req.tema_preferido is not None:
        current_user.tema_preferido = req.tema_preferido

    db.commit()
    db.refresh(current_user)
    notify_db_changed("auth_profile_update")
    return {
        "usuario": _serialize_user(current_user),
        "access_token": create_access_token(current_user.id, current_user.username),
    }


@router.put("/password")
def change_password(
    req: PasswordChangeRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if not verify_password(req.senha_atual, current_user.senha_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A senha atual informada não confere.",
        )
    current_user.senha_hash = hash_password(req.nova_senha)
    db.commit()
    notify_db_changed("auth_password_change")
    return {"ok": True, "detail": "Senha atualizada com sucesso."}
