"""Configuração do banco SQLite (SQLAlchemy 2.0 + WAL + Foreign Keys + Hook de Cofre)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

BACKEND_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("MINHA_FINANCEIRA_DATA_DIR") or (BACKEND_DIR / "data")).resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = Path(os.environ.get("MINHA_FINANCEIRA_DB_PATH") or (DATA_DIR / "minha_financeira.db")).resolve()
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH.as_posix()}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 30.0},
    future=True,
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragmas(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA synchronous=NORMAL;")
        cursor.execute("PRAGMA busy_timeout=30000;")
    finally:
        cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)


class Base(DeclarativeBase):
    pass


_change_listeners: list[Callable[[str], None]] = []


def register_db_change_listener(fn: Callable[[str], None]) -> None:
    if fn not in _change_listeners:
        _change_listeners.append(fn)


def notify_db_changed(reason: str = "write") -> None:
    for fn in list(_change_listeners):
        try:
            fn(reason)
        except Exception:
            pass


def init_db() -> None:
    import models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def dispose_engine() -> None:
    engine.dispose()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
