"""
Gerenciador de Persistência 24/7 em Cofre Criptografado AES-256-GCM (R$ 0,00)
+ Exportação Isolada de Backup ZIP por Perfil para a Minha Financeira.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import secrets
import shutil
import sqlite3
import tempfile
import threading
import time
import urllib.error
import urllib.request
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from services.vault_crypto import (
    GitHubEncryptedVaultClient,
    decode_vault_aes_key,
    merge_missing_users_sqlite,
)

TRACKED_TABLES = (
    "usuarios",
    "caixa_lancamentos",
    "contas_vencer",
    "conta_pagamentos",
    "cartoes",
    "cartao_compras",
    "cartao_fatura_pagamentos",
    "modulos_divida",
    "modulo_compras",
    "modulo_fatura_pagamentos",
)


def _atomic_write_bytes(path: Path, content: bytes, private: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.parent / f".{path.name}.tmp.{os.getpid()}.{secrets.token_hex(6)}"
    try:
        with open(tmp_path, "wb") as fh:
            fh.write(content)
            fh.flush()
            try:
                os.fsync(fh.fileno())
            except OSError:
                pass
        if private and os.name != "nt":
            try:
                os.chmod(tmp_path, 0o600)
            except OSError:
                pass
        os.replace(tmp_path, path)
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass


def _atomic_write_json(path: Path, payload: dict[str, Any], private: bool = False) -> None:
    raw = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    _atomic_write_bytes(path, raw, private=private)


def _read_json_safe(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(512 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _iso_utc(ts: float | None) -> str | None:
    if not ts:
        return None
    return datetime.fromtimestamp(ts, tz=UTC).isoformat().replace("+00:00", "Z")


def create_sqlite_snapshot(src_db_path: Path, dst_snapshot_path: Path) -> dict[str, Any]:
    if not src_db_path.is_file():
        raise FileNotFoundError(f"Banco SQLite não encontrado em: {src_db_path}")
    dst_snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    if dst_snapshot_path.exists():
        dst_snapshot_path.unlink()

    src_conn = sqlite3.connect(str(src_db_path), timeout=30.0)
    dst_conn = sqlite3.connect(str(dst_snapshot_path), timeout=30.0)
    try:
        with dst_conn:
            src_conn.backup(dst_conn)
        dst_conn.execute("PRAGMA journal_mode=DELETE;")
        integrity_row = dst_conn.execute("PRAGMA integrity_check;").fetchone()
        integrity = str(integrity_row[0] if integrity_row else "").lower()
        if integrity != "ok":
            raise RuntimeError(f"Snapshot SQLite falhou no integrity_check: {integrity}")

        tables = {
            r[0]
            for r in dst_conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        counts = {
            tbl: (int(dst_conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]) if tbl in tables else 0)
            for tbl in TRACKED_TABLES
        }
    finally:
        dst_conn.close()
        src_conn.close()

    return {
        "sha256": _sha256_file(dst_snapshot_path),
        "size": dst_snapshot_path.stat().st_size,
        "counts": counts,
    }


def validate_sqlite_file(candidate_path: Path) -> dict[str, int]:
    if not candidate_path.is_file() or candidate_path.stat().st_size < 100:
        raise ValueError("Arquivo de banco vazio ou incompleto.")
    with open(candidate_path, "rb") as fh:
        if fh.read(16) != b"SQLite format 3\x00":
            raise ValueError("Arquivo não possui cabeçalho SQLite 3 válido.")

    conn = sqlite3.connect(str(candidate_path), timeout=20.0)
    try:
        chk = conn.execute("PRAGMA integrity_check;").fetchone()
        if not chk or str(chk[0]).lower() != "ok":
            raise ValueError(f"Banco falhou no integrity_check: {chk}")
        tables = {
            r[0]
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        if "usuarios" not in tables:
            raise ValueError("Banco não contém a tabela 'usuarios' da Minha Financeira.")
        return {
            tbl: (int(conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]) if tbl in tables else 0)
            for tbl in TRACKED_TABLES
        }
    finally:
        conn.close()


def _default_http_transport(
    method: str,
    url: str,
    headers: dict[str, str] | None = None,
    data: bytes | None = None,
    timeout: float = 35.0,
) -> tuple[int, dict[str, str], bytes]:
    req = urllib.request.Request(url, data=data, headers=headers or {}, method=method.upper())
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return int(resp.status), {k: v for k, v in resp.headers.items()}, resp.read()
    except urllib.error.HTTPError as err:
        err_headers = {k: v for k, v in err.headers.items()} if err.headers else {}
        body = err.read() if err.fp else b""
        return int(err.code), err_headers, body


class CloudVaultManager:
    def __init__(
        self,
        *,
        data_dir: str | Path,
        db_path: str | Path,
        engine_disposer: Callable[[], None] | None = None,
        schema_migrator: Callable[[], None] | None = None,
        http_transport: Callable[..., tuple[int, dict[str, str], bytes]] | None = None,
        debounce_seconds: float = 2.0,
        max_wait_seconds: float = 10.0,
        is_cloud_container: bool | None = None,
    ) -> None:
        self.data_dir = Path(data_dir).resolve()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = Path(db_path).resolve()
        self.vault_creds_path = self.data_dir / "cloud_vault.json"
        self.meta_path = self.data_dir / ".cloud_vault_meta.json"

        self._engine_disposer = engine_disposer
        self._schema_migrator = schema_migrator
        self._http = http_transport or _default_http_transport
        self.debounce_seconds = float(debounce_seconds)
        self.max_wait_seconds = float(max_wait_seconds)
        self.is_cloud_container = (
            bool(is_cloud_container)
            if is_cloud_container is not None
            else bool(
                os.environ.get("RENDER")
                or os.environ.get("RENDER_SERVICE_ID")
                or os.environ.get("CLOUD_CONTAINER") == "1"
            )
        )

        self._state_lock = threading.RLock()
        self._io_lock = threading.RLock()
        self.vault_credentials: dict[str, Any] = {}
        self.meta: dict[str, Any] = _read_json_safe(self.meta_path)

        self._dirty = False
        self._first_dirty_at = 0.0
        self._last_dirty_at = 0.0
        self._syncing = False
        self._restoring = False
        self._boot_restore_failed = False
        self._shutdown = False
        self._last_error: str | None = None
        self._last_reason: str = ""
        self._wake_event = threading.Event()
        self._worker_thread: threading.Thread | None = None

        self._load_initial_vault_credentials()

    def _load_initial_vault_credentials(self) -> None:
        env_tok = (os.environ.get("CLOUD_VAULT_GITHUB_TOKEN") or "").strip()
        env_repo = (os.environ.get("CLOUD_VAULT_REPO") or "").strip()
        env_key = (os.environ.get("CLOUD_VAULT_AES_KEY") or "").strip()
        env_branch = (os.environ.get("CLOUD_VAULT_BRANCH") or "main").strip() or "main"

        if env_tok and env_repo and env_key:
            try:
                decode_vault_aes_key(env_key)
                self.vault_credentials = {
                    "github_token": env_tok,
                    "repo": env_repo,
                    "aes_key": env_key,
                    "branch": env_branch,
                    "auto_sync_enabled": True,
                }
                return
            except Exception as exc:
                self._last_error = f"Configuração CLOUD_VAULT inválida: {exc}"

        file_vault = _read_json_safe(self.vault_creds_path)
        if file_vault.get("github_token") and file_vault.get("repo") and file_vault.get("aes_key"):
            try:
                decode_vault_aes_key(str(file_vault["aes_key"]))
                self.vault_credentials = file_vault
            except Exception:
                self.vault_credentials = {}

    def _build_vault_client(self) -> GitHubEncryptedVaultClient:
        with self._state_lock:
            tok = str(self.vault_credentials.get("github_token") or "").strip()
            repo = str(self.vault_credentials.get("repo") or "").strip()
            key_str = str(self.vault_credentials.get("aes_key") or "").strip()
            branch = str(self.vault_credentials.get("branch") or "main").strip() or "main"
        return GitHubEncryptedVaultClient(
            token=tok,
            repo=repo,
            aes_key=decode_vault_aes_key(key_str),
            branch=branch,
            http_transport=self._http,
        )

    def _save_meta(self) -> None:
        _atomic_write_json(self.meta_path, self.meta, private=False)

    def is_vault_connected(self) -> bool:
        with self._state_lock:
            return bool(
                self.vault_credentials.get("github_token")
                and self.vault_credentials.get("repo")
                and self.vault_credentials.get("aes_key")
            )

    def status(self) -> dict[str, Any]:
        with self._state_lock:
            vault_ok = self.is_vault_connected()
            last_sync_ts = self.meta.get("last_sync_at")
            last_restore_ts = self.meta.get("last_restore_at")
            repo = str(self.vault_credentials.get("repo") or "")
            return {
                "vault_connected": vault_ok,
                "provider": "github_vault" if vault_ok else "local_sqlite",
                "repo": repo if vault_ok else "",
                "auto_sync_enabled": bool(self.vault_credentials.get("auto_sync_enabled", True)),
                "syncing": self._syncing,
                "restoring": self._restoring,
                "pending_changes": self._dirty,
                "revision": int(self.meta.get("revision") or 0),
                "last_sync_iso": _iso_utc(last_sync_ts),
                "last_restore_iso": _iso_utc(last_restore_ts),
                "last_error": self._last_error,
                "counts": self.meta.get("counts") or {},
                "is_cloud_container": self.is_cloud_container,
                "keep_alive_interval_minutes": 10,
            }

    def public_health_summary(self) -> dict[str, Any]:
        st = self.status()
        return {
            "vault_conectado": st["vault_connected"],
            "provedor": st["provider"],
            "auto_sync": st["auto_sync_enabled"],
            "ultimo_backup": st["last_sync_iso"],
            "revisao": st["revision"],
            "container_nuvem": st["is_cloud_container"],
        }

    def hydrate_vault(
        self,
        *,
        github_token: str,
        repo: str,
        aes_key: str,
        branch: str = "main",
    ) -> dict[str, Any]:
        tok = (github_token or "").strip()
        repo_clean = (repo or "").strip().strip("/")
        key_clean = (aes_key or "").strip()
        branch_clean = (branch or "main").strip() or "main"
        if not tok or not repo_clean or not key_clean:
            raise ValueError("Credenciais do cofre em nuvem incompletas.")

        key_bytes = decode_vault_aes_key(key_clean)
        test_client = GitHubEncryptedVaultClient(
            token=tok,
            repo=repo_clean,
            aes_key=key_bytes,
            branch=branch_clean,
            http_transport=self._http,
        )
        test_client.verify_repo_access()

        with self._state_lock:
            self.vault_credentials = {
                "github_token": tok,
                "repo": repo_clean,
                "aes_key": key_clean,
                "branch": branch_clean,
                "auto_sync_enabled": True,
            }
            self._boot_restore_failed = False
            self._last_error = None
            _atomic_write_json(self.vault_creds_path, self.vault_credentials, private=True)

        restore_res = self.restore_from_vault(
            force=True, on_boot=False, merge_pre_hydration_local=True
        )
        sync_res: dict[str, Any] | None = None
        if (
            not restore_res.get("remote_backup_found") or restore_res.get("merged_local_users", 0) > 0
        ) and self.db_path.is_file():
            sync_res = self.sync_now(force=True, reason="vault_hydrate_sync")

        st = self.status()
        st["hydrate_result"] = restore_res
        if sync_res is not None:
            st["sync_result"] = sync_res
        return st

    def sync_now(self, *, force: bool = False, reason: str = "manual") -> dict[str, Any]:
        if not self.is_vault_connected():
            return {"ok": False, "skipped": True, "reason": "not_connected"}
        if not self.db_path.is_file():
            return {"ok": False, "skipped": True, "reason": "local_db_missing"}

        if not force and self._boot_restore_failed:
            retry_res = self.restore_from_vault(force=False, on_boot=True)
            if not retry_res.get("ok"):
                return {
                    "ok": False,
                    "blocked_boot_restore_pending": True,
                    "detail": "Aguardando restauração inicial do cofre antes de sincronizar.",
                }
            if retry_res.get("restored"):
                return {"ok": True, "action": "restored_after_boot_retry", **retry_res}

        with self._io_lock:
            with self._state_lock:
                self._syncing = True
                self._dirty = False

            tmp_dir = Path(tempfile.mkdtemp(prefix="mf_vsync_"))
            try:
                snap_file = tmp_dir / "minha_financeira.db"
                snap_info = create_sqlite_snapshot(self.db_path, snap_file)

                if not force and self.meta.get("db_sha256") == snap_info["sha256"]:
                    return {"ok": True, "action": "up_to_date", "revision": self.meta.get("revision", 0)}

                vclient = self._build_vault_client()
                remote_state = vclient.read_branch_state()
                remote_blobs = (remote_state or {}).get("blobs") or {}

                remote_manifest: dict[str, Any] = {}
                if "manifest.json.enc" in remote_blobs:
                    try:
                        raw_mf = vclient.download_decrypted(remote_blobs["manifest.json.enc"]["sha"])
                        remote_manifest = json.loads(raw_mf.decode("utf-8"))
                    except Exception:
                        remote_manifest = {}

                remote_users = int(((remote_manifest.get("counts") or {}).get("usuarios")) or 0)
                local_users = int(snap_info["counts"].get("usuarios") or 0)
                local_rev = int(self.meta.get("revision") or 0)
                remote_rev = int(remote_manifest.get("revision") or 0)
                remote_sha = str(remote_manifest.get("db_sha256") or "")

                if not force and remote_users > 0 and local_users == 0:
                    msg = "Proteção anti-perda ativada: o cofre possui perfis salvos e o banco local está vazio."
                    with self._state_lock:
                        self._last_error = msg
                    return {"ok": False, "blocked_anti_wipe": True, "detail": msg}

                if not force and local_rev == 0 and remote_rev > 0 and remote_sha and remote_sha != snap_info["sha256"]:
                    msg = f"Proteção anti-perda ativada: o cofre já possui revisão ativa (#{remote_rev})."
                    with self._state_lock:
                        self._last_error = msg
                    return {"ok": False, "blocked_anti_wipe": True, "blocked_remote_newer": True, "detail": msg}

                new_tree_blobs: dict[str, str] = {}
                db_changed = (
                    force
                    or (remote_sha != snap_info["sha256"])
                    or ("minha_financeira.db.enc" not in remote_blobs)
                )
                if db_changed:
                    new_tree_blobs["minha_financeira.db.enc"] = vclient.upload_encrypted(
                        snap_file.read_bytes()
                    )
                else:
                    new_tree_blobs["minha_financeira.db.enc"] = remote_blobs["minha_financeira.db.enc"]["sha"]

                now_ts = time.time()
                next_rev = max(local_rev, remote_rev) + 1
                manifest_payload = {
                    "schema_version": 1,
                    "sistema": "Minha Financeira",
                    "provider": "github_vault",
                    "revision": next_rev,
                    "updated_at": now_ts,
                    "updated_at_iso": _iso_utc(now_ts),
                    "source": "render" if self.is_cloud_container else "local",
                    "reason": reason,
                    "db_sha256": snap_info["sha256"],
                    "db_size": snap_info["size"],
                    "counts": snap_info["counts"],
                }
                new_tree_blobs["manifest.json.enc"] = vclient.upload_encrypted(
                    json.dumps(manifest_payload, ensure_ascii=False, indent=2).encode("utf-8")
                )

                last_hist_ts = float(self.meta.get("last_history_snapshot_at") or 0)
                rotate_parent = (now_ts - last_hist_ts) >= 3600
                vclient.commit_tree(
                    blob_entries=new_tree_blobs,
                    prev_state=remote_state,
                    rotate_parent=rotate_parent,
                    message=f"mf vault sync rev #{next_rev} ({reason})",
                )
                if rotate_parent:
                    self.meta["last_history_snapshot_at"] = now_ts

                with self._state_lock:
                    self.meta.update(
                        revision=next_rev,
                        db_sha256=snap_info["sha256"],
                        db_size=snap_info["size"],
                        counts=snap_info["counts"],
                        last_sync_at=now_ts,
                    )
                    self._last_error = None
                    self._save_meta()

                return {
                    "ok": True,
                    "action": "synced",
                    "provider": "github_vault",
                    "revision": next_rev,
                    "db_uploaded": db_changed,
                    "counts": snap_info["counts"],
                }
            except Exception as exc:
                with self._state_lock:
                    self._last_error = str(exc)
                raise
            finally:
                shutil.rmtree(tmp_dir, ignore_errors=True)
                with self._state_lock:
                    self._syncing = False

    def restore_from_vault(
        self,
        *,
        force: bool = False,
        on_boot: bool = False,
        merge_pre_hydration_local: bool = False,
    ) -> dict[str, Any]:
        if not self.is_vault_connected():
            return {"ok": False, "restored": False, "reason": "not_connected"}

        with self._io_lock:
            with self._state_lock:
                self._restoring = True

            tmp_dir = Path(tempfile.mkdtemp(prefix="mf_vrestore_"))
            try:
                vclient = self._build_vault_client()
                remote_state = vclient.read_branch_state()
                remote_blobs = (remote_state or {}).get("blobs") or {}
                if not remote_state or "minha_financeira.db.enc" not in remote_blobs:
                    self._boot_restore_failed = False
                    if on_boot and self.db_path.is_file():
                        self.notify_change("initial_seed_on_boot")
                    return {
                        "ok": True,
                        "restored": False,
                        "remote_backup_found": False,
                        "reason": "remote_db_not_found",
                    }

                remote_manifest: dict[str, Any] = {}
                if "manifest.json.enc" in remote_blobs:
                    try:
                        raw_mf = vclient.download_decrypted(remote_blobs["manifest.json.enc"]["sha"])
                        remote_manifest = json.loads(raw_mf.decode("utf-8"))
                    except Exception:
                        remote_manifest = {}

                local_exists = self.db_path.is_file()
                local_sha256 = ""
                local_snap = tmp_dir / "local_check.db"
                if local_exists:
                    try:
                        info_local = create_sqlite_snapshot(self.db_path, local_snap)
                        local_sha256 = info_local["sha256"]
                    except Exception:
                        local_sha256 = ""

                remote_sha = str(remote_manifest.get("db_sha256") or "")
                db_restored = False
                merged_local_users = 0

                if force or not remote_sha or remote_sha != local_sha256 or not local_exists:
                    dl_db = tmp_dir / "minha_financeira_remote.db"
                    dl_db.write_bytes(
                        vclient.download_decrypted(remote_blobs["minha_financeira.db.enc"]["sha"])
                    )
                    validate_sqlite_file(dl_db)

                    if merge_pre_hydration_local and local_snap.is_file():
                        merged_local_users = merge_missing_users_sqlite(dl_db, local_snap)

                    if self._engine_disposer:
                        try:
                            self._engine_disposer()
                        except Exception:
                            pass

                    self.db_path.parent.mkdir(parents=True, exist_ok=True)
                    if not self.db_path.exists():
                        _atomic_write_bytes(self.db_path, dl_db.read_bytes())
                    else:
                        src_conn = sqlite3.connect(str(dl_db), timeout=30.0)
                        dst_conn = sqlite3.connect(str(self.db_path), timeout=30.0)
                        try:
                            with dst_conn:
                                src_conn.backup(dst_conn)
                            try:
                                dst_conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
                            except Exception:
                                pass
                        finally:
                            dst_conn.close()
                            src_conn.close()

                    if self._schema_migrator:
                        self._schema_migrator()
                    db_restored = True

                final_snap = tmp_dir / "post_restore_snap.db"
                final_info = create_sqlite_snapshot(self.db_path, final_snap)
                now_ts = time.time()
                with self._state_lock:
                    self.meta.update(
                        revision=int(remote_manifest.get("revision") or self.meta.get("revision") or 1),
                        db_sha256=final_info["sha256"],
                        db_size=final_info["size"],
                        counts=final_info["counts"],
                        last_restore_at=now_ts,
                    )
                    if not self.meta.get("last_sync_at") and remote_manifest.get("updated_at"):
                        self.meta["last_sync_at"] = float(remote_manifest["updated_at"])
                    self._dirty = False
                    self._boot_restore_failed = False
                    self._last_error = None
                    self._save_meta()

                return {
                    "ok": True,
                    "restored": db_restored,
                    "remote_backup_found": True,
                    "db_restored": db_restored,
                    "merged_local_users": merged_local_users,
                    "counts": final_info["counts"],
                }
            except Exception as exc:
                with self._state_lock:
                    if on_boot:
                        self._boot_restore_failed = True
                    self._last_error = f"Falha ao restaurar do cofre em nuvem: {exc}"
                if on_boot:
                    return {"ok": False, "restored": False, "error": str(exc)}
                raise
            finally:
                shutil.rmtree(tmp_dir, ignore_errors=True)
                with self._state_lock:
                    self._restoring = False

    def notify_change(self, reason: str = "write") -> None:
        with self._state_lock:
            if self._shutdown or self._restoring:
                return
            if not self.is_vault_connected():
                return
            if not bool(self.vault_credentials.get("auto_sync_enabled", True)):
                return
            now = time.monotonic()
            if not self._dirty:
                self._first_dirty_at = now
            self._last_dirty_at = now
            self._dirty = True
            self._last_reason = reason
            self._wake_event.set()
            if self._worker_thread is None or not self._worker_thread.is_alive():
                self._worker_thread = threading.Thread(
                    target=self._background_loop,
                    name="mf-vault-sync",
                    daemon=True,
                )
                self._worker_thread.start()

    def _background_loop(self) -> None:
        while not self._shutdown:
            self._wake_event.wait(timeout=1.0)
            self._wake_event.clear()
            if self._shutdown:
                break
            while True:
                with self._state_lock:
                    if not self._dirty or self._shutdown:
                        break
                    now = time.monotonic()
                    since_last = now - self._last_dirty_at
                    since_first = now - self._first_dirty_at
                    reason = self._last_reason
                    if since_last < self.debounce_seconds and since_first < self.max_wait_seconds:
                        wait_for = min(
                            self.debounce_seconds - since_last,
                            self.max_wait_seconds - since_first,
                        )
                    else:
                        wait_for = 0.0
                if wait_for > 0:
                    self._wake_event.wait(timeout=max(0.05, wait_for))
                    self._wake_event.clear()
                    continue
                try:
                    self.sync_now(force=False, reason=reason)
                except Exception:
                    time.sleep(2.0)
                break

    def flush_pending(self) -> dict[str, Any] | None:
        with self._state_lock:
            has_dirty = self._dirty
            reason = self._last_reason or "shutdown_flush"
        if has_dirty and self.is_vault_connected():
            try:
                return self.sync_now(force=False, reason=reason)
            except Exception as exc:
                return {"ok": False, "error": str(exc)}
        return None

    def shutdown(self) -> None:
        self.flush_pending()
        with self._state_lock:
            self._shutdown = True
            self._wake_event.set()
            worker = self._worker_thread
        if worker is not None and worker.is_alive() and worker is not threading.current_thread():
            worker.join(timeout=5.0)

    def export_user_backup_zip_bytes(self, usuario_id: int) -> bytes:
        """Gera pacote .zip isolado contendo exclusivamente o SQLite + manifest do usuário logado."""
        tmp_dir = Path(tempfile.mkdtemp(prefix="mf_zip_"))
        try:
            snap_file = tmp_dir / "minha_financeira.db"
            create_sqlite_snapshot(self.db_path, snap_file)

            uid = int(usuario_id)
            conn = sqlite3.connect(str(snap_file), timeout=30.0)
            try:
                tables = {
                    r[0]
                    for r in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    ).fetchall()
                }
                with conn:
                    for tbl in (
                        "modulo_fatura_pagamentos",
                        "modulo_compras",
                        "modulos_divida",
                        "cartao_fatura_pagamentos",
                        "cartao_compras",
                        "cartoes",
                        "conta_pagamentos",
                        "contas_vencer",
                        "caixa_lancamentos",
                    ):
                        if tbl in tables:
                            conn.execute(f"DELETE FROM {tbl} WHERE usuario_id != ?", (uid,))
                    if "usuarios" in tables:
                        conn.execute("DELETE FROM usuarios WHERE id != ?", (uid,))
                conn.execute("VACUUM;")
            finally:
                conn.close()

            pruned_counts = validate_sqlite_file(snap_file)
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                zf.write(snap_file, arcname="minha_financeira.db")
                manifest = {
                    "sistema": "Minha Financeira",
                    "escopo": "perfil_isolado",
                    "exported_at_iso": _iso_utc(time.time()),
                    "db_sha256": _sha256_file(snap_file),
                    "counts": pruned_counts,
                }
                zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
            return buf.getvalue()
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)
