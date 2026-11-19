"""Autenticação segura (bcrypt + JWT HS256) e isolamento rigoroso por perfil."""

from __future__ import annotations

import hashlib
import os
import secrets
from datetime import UTC, datetime, timedelta

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from database import DATA_DIR, get_db
from models import Usuario

ALGORITHM = "HS256"
TOKEN_EXPIRE_DAYS = 30
_bearer_scheme = HTTPBearer(auto_error=False)


def _load_or_create_jwt_secret() -> str:
    env_secret = (os.environ.get("JWT_SECRET") or "").strip()
    if env_secret:
        return env_secret
    # Deriva deterministicamente da chave AES do cofre se disponível (sobrevive a reinícios na nuvem!)
    vault_key = (os.environ.get("CLOUD_VAULT_AES_KEY") or "").strip()
    if vault_key:
        return hashlib.sha256(f"mf-jwt-v1:{vault_key}".encode("utf-8")).hexdigest()
    secret_file = DATA_DIR / ".jwt_secret"
    if secret_file.is_file():
        stored = secret_file.read_text(encoding="utf-8").strip()
        if stored:
            return stored
    generated = secrets.token_urlsafe(48)
    secret_file.write_text(generated, encoding="utf-8")
    return generated


JWT_SECRET = _load_or_create_jwt_secret()


def normalize_username(raw: str) -> str:
    return (raw or "").strip().lower()


def hash_password(password: str) -> str:
    raw = password.encode("utf-8")
    if len(raw) > 72:
        raw = hashlib.sha256(raw).digest()
    return bcrypt.hashpw(raw, bcrypt.gensalt(rounds=11)).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    if not password or not password_hash:
        return False
    raw = password.encode("utf-8")
    if len(raw) > 72:
        raw = hashlib.sha256(raw).digest()
    try:
        return bcrypt.checkpw(raw, password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(user_id: int, username: str) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "usr": username,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=TOKEN_EXPIRE_DAYS)).timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> Usuario:
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessão ausente ou expirada. Faça login novamente.",
        )
    token = credentials.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        sub = payload.get("sub")
        if not sub:
            raise ValueError("missing sub")
        user_id = int(sub)
    except (JWTError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de acesso inválido ou expirado.",
        )

    user = db.get(Usuario, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Perfil não encontrado. Faça login novamente.",
        )
    return user
