"""Testes do Cofre Criptografado AES-256-GCM 24/7, Anti-Wipe, Merge e Exportação ZIP Isolada."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import secrets
import sqlite3
import zipfile
from pathlib import Path

import pytest

from conftest import register_and_headers
from services.cloud_vault import CloudVaultManager
from services.vault_crypto import (
    decrypt_vault_blob,
    encrypt_vault_blob,
    merge_missing_users_sqlite,
)


class FakeGitHubVaultTransport:
    """Simulador fiel da Git Data API do GitHub para validar sync/restore/anti-wipe sem rede."""

    def __init__(self):
        self.blobs: dict[str, bytes] = {}
        self.trees: dict[str, list[dict]] = {}
        self.commits: dict[str, dict] = {}
        self.refs: dict[str, str] = {}

    def __call__(self, method: str, url: str, headers=None, data=None, timeout=30.0):
        path = url.split("https://api.github.com/repos/owner/mf-vault", 1)[-1]
        body = json.loads(data.decode("utf-8")) if data else {}

        if method == "GET" and path == "":
            return 200, {}, json.dumps({"full_name": "owner/mf-vault", "private": True}).encode()

        if method == "GET" and path.startswith("/git/ref/heads/"):
            branch = path.split("/git/ref/heads/", 1)[1]
            if branch not in self.refs:
                return 404, {}, b"{}"
            return 200, {}, json.dumps({"object": {"sha": self.refs[branch]}}).encode()

        if method == "GET" and path.startswith("/git/commits/"):
            sha = path.split("/git/commits/", 1)[1]
            return 200, {}, json.dumps(self.commits[sha]).encode()

        if method == "GET" and path.startswith("/git/trees/"):
            sha = path.split("/git/trees/", 1)[1].split("?")[0]
            return 200, {}, json.dumps({"tree": self.trees[sha]}).encode()

        if method == "GET" and path.startswith("/git/blobs/"):
            sha = path.split("/git/blobs/", 1)[1]
            return 200, {}, json.dumps({"content": base64.b64encode(self.blobs[sha]).decode()}).encode()

        if method == "POST" and path == "/git/blobs":
            raw = base64.b64decode(body["content"])
            sha = hashlib.sha1(raw).hexdigest()
            self.blobs[sha] = raw
            return 201, {}, json.dumps({"sha": sha}).encode()

        if method == "POST" and path == "/git/trees":
            sha = hashlib.sha1(json.dumps(body["tree"], sort_keys=True).encode()).hexdigest()
            self.trees[sha] = body["tree"]
            return 201, {}, json.dumps({"sha": sha}).encode()

        if method == "POST" and path == "/git/commits":
            sha = hashlib.sha1(f"{body['tree']}:{body['message']}:{len(self.commits)}".encode()).hexdigest()
            self.commits[sha] = {
                "sha": sha,
                "tree": {"sha": body["tree"]},
                "parents": [{"sha": p} for p in body.get("parents", [])],
            }
            return 201, {}, json.dumps({"sha": sha}).encode()

        if method == "POST" and path == "/git/refs":
            branch = body["ref"].replace("refs/heads/", "")
            self.refs[branch] = body["sha"]
            return 201, {}, json.dumps({"ref": body["ref"]}).encode()

        if method == "PATCH" and path.startswith("/git/refs/heads/"):
            branch = path.split("/git/refs/heads/", 1)[1]
            self.refs[branch] = body["sha"]
            return 200, {}, json.dumps({"object": {"sha": body["sha"]}}).encode()

        return 404, {}, b"{}"


def test_aes_gcm_vault_crypto_roundtrip_and_tamper():
    key = secrets.token_bytes(32)
    plain = b"SQLite payload confidencial Minha Financeira"
    enc = encrypt_vault_blob(plain, key)
    assert enc[:4] == b"MFV1"
    assert decrypt_vault_blob(enc, key) == plain

    # Adulteração de 1 byte deve falhar autenticação GCM
    tampered = bytearray(enc)
    tampered[-1] ^= 0xFF
    with pytest.raises(Exception):
        decrypt_vault_blob(bytes(tampered), key)


def test_vault_sync_container_wipe_restore_and_anti_wipe(tmp_path: Path):
    transport = FakeGitHubVaultTransport()
    aes_hex = secrets.token_hex(32)

    # 1. Container A cria banco com 1 usuário e sincroniza no cofre criptografado
    dir_a = tmp_path / "container_a"
    db_a = dir_a / "minha_financeira.db"
    dir_a.mkdir()
    conn = sqlite3.connect(str(db_a))
    conn.execute("CREATE TABLE usuarios (id INTEGER PRIMARY KEY, nome TEXT, username TEXT, senha_hash TEXT, tema_preferido TEXT)")
    conn.execute("INSERT INTO usuarios VALUES (1, 'Thiago', 'thiago', 'hash1', 'dark')")
    conn.commit()
    conn.close()

    mgr_a = CloudVaultManager(data_dir=dir_a, db_path=db_a, http_transport=transport, is_cloud_container=True)
    mgr_a.hydrate_vault(github_token="ghp_testtoken123456789", repo="owner/mf-vault", aes_key=aes_hex)
    sync_res = mgr_a.sync_now(force=True, reason="test_seed")
    assert sync_res["ok"] is True
    assert sync_res["revision"] >= 1

    # 2. Container B sobe zerado (restart do Render) e restaura 100% do cofre
    dir_b = tmp_path / "container_b"
    db_b = dir_b / "minha_financeira.db"
    dir_b.mkdir()
    mgr_b = CloudVaultManager(data_dir=dir_b, db_path=db_b, http_transport=transport, is_cloud_container=True)
    mgr_b.vault_credentials = {
        "github_token": "ghp_testtoken123456789",
        "repo": "owner/mf-vault",
        "aes_key": aes_hex,
        "branch": "main",
        "auto_sync_enabled": True,
    }
    rest = mgr_b.restore_from_vault(force=False, on_boot=True)
    assert rest["ok"] is True
    assert rest["db_restored"] is True
    assert rest["counts"]["usuarios"] == 1

    # 3. Proteção Anti-Wipe: container C com banco vazio NÃO pode sobrescrever cofre com usuários
    dir_c = tmp_path / "container_c"
    db_c = dir_c / "minha_financeira.db"
    dir_c.mkdir()
    c_conn = sqlite3.connect(str(db_c))
    c_conn.execute("CREATE TABLE usuarios (id INTEGER PRIMARY KEY, nome TEXT, username TEXT, senha_hash TEXT, tema_preferido TEXT)")
    c_conn.commit()
    c_conn.close()

    mgr_c = CloudVaultManager(data_dir=dir_c, db_path=db_c, http_transport=transport, is_cloud_container=True)
    mgr_c.vault_credentials = dict(mgr_b.vault_credentials)
    blocked = mgr_c.sync_now(force=False, reason="accidental_empty")
    assert blocked["ok"] is False
    assert blocked["blocked_anti_wipe"] is True


def test_per_user_isolated_backup_zip_and_hydrate_auth(client, tmp_path: Path, monkeypatch):
    h_a = register_and_headers(client, "User A", "user_a")
    h_b = register_and_headers(client, "User B", "user_b")

    client.post(
        "/api/caixa",
        headers=h_a,
        json={"tipo": "entrada", "descricao": "Segredo A", "categoria": "Uber / App", "valor": 300.0, "data": "2026-05-10"},
    )
    client.post(
        "/api/caixa",
        headers=h_b,
        json={"tipo": "entrada", "descricao": "Segredo B", "categoria": "Salário", "valor": 9999.0, "data": "2026-05-10"},
    )

    # Exporta backup ZIP do User A -> deve conter APENAS User A e 1 lançamento
    resp_zip = client.get("/api/cloud/backup/export", headers=h_a)
    assert resp_zip.status_code == 200
    assert resp_zip.headers["content-type"] == "application/zip"

    zf = zipfile.ZipFile(io.BytesIO(resp_zip.content))
    manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
    assert manifest["counts"]["usuarios"] == 1
    assert manifest["counts"]["caixa_lancamentos"] == 1

    extracted_db = tmp_path / "extracted_a.db"
    extracted_db.write_bytes(zf.read("minha_financeira.db"))
    conn = sqlite3.connect(str(extracted_db))
    users = [r[0] for r in conn.execute("SELECT username FROM usuarios").fetchall()]
    descs = [r[0] for r in conn.execute("SELECT descricao FROM caixa_lancamentos").fetchall()]
    conn.close()
    assert users == ["user_a"]
    assert descs == ["Segredo A"]

    # Validação de segredo de hidratação
    monkeypatch.setenv("CLOUD_VAULT_HYDRATE_SECRET", "segredo-super-forte-123")
    bad_hyd = client.post(
        "/cloud/vault/hydrate",
        json={
            "hydrate_secret": "segredo-errado-000",
            "github_token": "ghp_1234567890",
            "repo": "owner/vault",
            "aes_key": "a" * 64,
        },
    )
    assert bad_hyd.status_code == 403


def test_merge_missing_users_remaps_foreign_keys(tmp_path: Path):
    base_db = tmp_path / "base.db"
    extra_db = tmp_path / "extra.db"
    schema = """
        CREATE TABLE usuarios (id INTEGER PRIMARY KEY, nome TEXT, username TEXT UNIQUE, senha_hash TEXT, tema_preferido TEXT);
        CREATE TABLE caixa_lancamentos (id INTEGER PRIMARY KEY, usuario_id INTEGER, tipo TEXT, descricao TEXT, categoria TEXT, valor_centavos INTEGER, data TEXT, forma_pagamento TEXT, observacao TEXT, origem_tipo TEXT, origem_ref_id INTEGER);
        CREATE TABLE modulos_divida (id INTEGER PRIMARY KEY, usuario_id INTEGER, nome TEXT, descricao TEXT, cor_hex TEXT, dia_fechamento INTEGER, dia_vencimento INTEGER, limite_centavos INTEGER, ativo INTEGER);
        CREATE TABLE modulo_compras (id INTEGER PRIMARY KEY, usuario_id INTEGER, modulo_id INTEGER, descricao TEXT, categoria TEXT, data_compra TEXT, valor_total_centavos INTEGER, parcelas_total INTEGER, competencia_inicial TEXT, observacao TEXT);
    """
    for dbp, uname, mod_name in ((base_db, "base_user", "Thiago"), (extra_db, "new_user", "Seu Luiz")):
        c = sqlite3.connect(str(dbp))
        c.executescript(schema)
        c.execute("INSERT INTO usuarios VALUES (1, ?, ?, 'h', 'dark')", (uname, uname))
        c.execute("INSERT INTO modulos_divida VALUES (1, 1, ?, '', '#10B981', 10, 18, 0, 1)", (mod_name,))
        c.execute("INSERT INTO modulo_compras VALUES (1, 1, 1, 'Compra X', 'Dívidas', '2026-05-01', 10000, 2, '2026-05', '')")
        c.commit()
        c.close()

    merged = merge_missing_users_sqlite(base_db, extra_db)
    assert merged == 1

    c = sqlite3.connect(str(base_db))
    users = c.execute("SELECT id, username FROM usuarios ORDER BY id").fetchall()
    mods = c.execute("SELECT id, usuario_id, nome FROM modulos_divida ORDER BY id").fetchall()
    compras = c.execute("SELECT id, usuario_id, modulo_id FROM modulo_compras ORDER BY id").fetchall()
    c.close()

    assert users == [(1, "base_user"), (2, "new_user")]
    assert mods == [(1, 1, "Thiago"), (2, 2, "Seu Luiz")]
    assert compras == [(1, 1, 1), (2, 2, 2)]
