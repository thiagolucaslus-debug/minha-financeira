"""Rotas do Cofre Criptografado 24/7 e Exportação Isolada de Backup ZIP por Perfil."""

from __future__ import annotations

import hmac
import os

from fastapi import APIRouter, Depends, HTTPException, Response, status

from auth import get_current_user
from models import Usuario
from schemas import VaultHydrateRequest
from services.cloud_vault import CloudVaultManager
from services.dates import today_brt_iso

router = APIRouter(prefix="/cloud", tags=["Nuvem & Backup"])

_vault_manager: CloudVaultManager | None = None


def bind_vault_manager(manager: CloudVaultManager) -> None:
    global _vault_manager
    _vault_manager = manager


def get_vault_manager() -> CloudVaultManager:
    if _vault_manager is None:
        raise RuntimeError("CloudVaultManager não inicializado.")
    return _vault_manager


@router.get("/status")
def cloud_status(_current_user: Usuario = Depends(get_current_user)):
    return get_vault_manager().status()


@router.post("/vault/hydrate")
def hydrate_vault(req: VaultHydrateRequest):
    expected = (os.environ.get("CLOUD_VAULT_HYDRATE_SECRET") or "").strip()
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="CLOUD_VAULT_HYDRATE_SECRET não configurado no servidor.",
        )
    if not hmac.compare_digest(req.hydrate_secret.strip(), expected):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Segredo de hidratação inválido.",
        )
    try:
        return get_vault_manager().hydrate_vault(
            github_token=req.github_token,
            repo=req.repo,
            aes_key=req.aes_key,
            branch=req.branch,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/vault/sync")
def sync_vault_now(_current_user: Usuario = Depends(get_current_user)):
    mgr = get_vault_manager()
    if not mgr.is_vault_connected():
        raise HTTPException(status_code=400, detail="Cofre em nuvem não configurado neste ambiente.")
    try:
        res = mgr.sync_now(force=True, reason="manual_user_sync")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Falha ao sincronizar com o cofre: {exc}") from exc
    if res.get("blocked_anti_wipe") or res.get("blocked_boot_restore_pending"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=res.get("detail") or "Sincronização bloqueada pela proteção anti-perda.",
        )
    return res


@router.get("/backup/export")
def export_user_backup(current_user: Usuario = Depends(get_current_user)):
    zip_bytes = get_vault_manager().export_user_backup_zip_bytes(current_user.id)
    safe_user = "".join(ch for ch in current_user.username if ch.isalnum() or ch in ("-", "_")) or "perfil"
    filename = f"minha_financeira_{safe_user}_{today_brt_iso()}.zip"
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
