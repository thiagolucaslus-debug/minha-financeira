"""Fixtures isoladas do pytest para Minha Financeira (banco SQLite limpo por teste)."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    data_dir = tmp_path / "mf_data"
    db_path = data_dir / "test_mf.db"
    monkeypatch.setenv("MINHA_FINANCEIRA_DATA_DIR", str(data_dir))
    monkeypatch.setenv("MINHA_FINANCEIRA_DB_PATH", str(db_path))
    monkeypatch.setenv("JWT_SECRET", "test-jwt-secret-minha-financeira-2026")
    monkeypatch.delenv("CLOUD_VAULT_GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("CLOUD_VAULT_REPO", raising=False)
    monkeypatch.delenv("CLOUD_VAULT_AES_KEY", raising=False)
    monkeypatch.delenv("CLOUD_VAULT_HYDRATE_SECRET", raising=False)

    # Limpa todos os módulos da aplicação (incluindo o pacote `routers`) para isolamento total por teste
    to_clear = [
        name
        for name in list(sys.modules)
        if name in ("database", "models", "auth", "schemas", "main", "routers", "services")
        or name.startswith("routers.")
        or name.startswith("services.")
    ]
    for mod_name in to_clear:
        sys.modules.pop(mod_name, None)

    main_mod = importlib.import_module("main")
    with TestClient(main_mod.app) as tc:
        yield tc


def register_and_headers(client: TestClient, nome: str, username: str, senha: str = "senha123") -> dict[str, str]:
    resp = client.post(
        "/api/auth/register",
        json={"nome": nome, "username": username, "senha": senha},
    )
    assert resp.status_code == 201, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
