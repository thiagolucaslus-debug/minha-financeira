"""
Minha Financeira — API FastAPI + Cofre Criptografado 24/7 + Servidor SPA/PWA.
"""

from __future__ import annotations

import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from database import DATA_DIR, DB_PATH, dispose_engine, init_db, register_db_change_listener  # noqa: E402
from routers import (  # noqa: E402
    auth_routes,
    caixa_routes,
    cartoes_routes,
    cloud_routes,
    contas_routes,
    modulos_routes,
    painel_routes,
)
from services.cloud_vault import CloudVaultManager  # noqa: E402

PROJECT_ROOT = BACKEND_DIR.parent
FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"

vault_manager = CloudVaultManager(
    data_dir=DATA_DIR,
    db_path=DB_PATH,
    engine_disposer=dispose_engine,
    schema_migrator=init_db,
)
cloud_routes.bind_vault_manager(vault_manager)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    if vault_manager.is_vault_connected():
        vault_manager.restore_from_vault(force=False, on_boot=True)
        init_db()
    register_db_change_listener(vault_manager.notify_change)
    try:
        yield
    finally:
        vault_manager.shutdown()


app = FastAPI(
    title="Minha Financeira",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_PREFIXES = ("/api", "")
# Expõe todas as rotas de API sob `/api/...` (evita qualquer colisão com rotas React do SPA)
for router in (
    auth_routes.router,
    caixa_routes.router,
    contas_routes.router,
    cartoes_routes.router,
    modulos_routes.router,
    painel_routes.router,
    cloud_routes.router,
):
    app.include_router(router, prefix="/api")

# Alias de compatibilidade para hidratação do workflow 24/7
app.include_router(cloud_routes.router)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "sistema": "Minha Financeira",
        "versao": "1.0.0",
        "git_sha": (os.environ.get("RENDER_GIT_COMMIT") or os.environ.get("GIT_SHA") or "")[:12],
        "nuvem": vault_manager.public_health_summary(),
    }


# Servir assets e SPA compilado do Vite (em produção Docker/Render ou build local)
if FRONTEND_DIST.is_dir():
    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/{full_path:path}")
    def serve_spa(full_path: str):
        if full_path.startswith("api/") or full_path == "api":
            raise HTTPException(status_code=404, detail="Endpoint não encontrado.")

        candidate = (FRONTEND_DIST / full_path).resolve()
        try:
            candidate.relative_to(FRONTEND_DIST.resolve())
        except ValueError as exc:
            raise HTTPException(status_code=404, detail="Recurso inválido.") from exc

        if full_path and candidate.is_file():
            headers = {}
            if candidate.name == "sw.js":
                headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
                headers["Service-Worker-Allowed"] = "/"
            elif candidate.name == "manifest.webmanifest":
                headers["Content-Type"] = "application/manifest+json; charset=utf-8"
                headers["Cache-Control"] = "no-cache"
            return FileResponse(str(candidate), headers=headers)

        index_html = FRONTEND_DIST / "index.html"
        if index_html.is_file():
            return FileResponse(
                str(index_html),
                headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
            )
        raise HTTPException(status_code=404, detail="Frontend não compilado.")
