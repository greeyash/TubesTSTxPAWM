"""Bebas Core Service: perencana wisata satu hari di Bandung (tema Tourism, K02)."""
import logging
from contextlib import asynccontextmanager

import sqlite3
from typing import List, Optional

from fastapi import Depends, FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from .common import now_wib
from .config import VERSION, settings
from .crowd.router import router as crowd_router
from .db import connect, get_db, init_db
from .events import EVENT_TYPES, list_events
from .identity.deps import require_roles
from .identity import service as identity
from .identity.router import router as identity_router
from .places.router import router as places_router
from .planning.router import router as planning_router
from .prediction.router import router as prediction_router
from .public.router import router as public_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("bebas")

DESCRIPTION = """
Core service kelompok **Bebas** (K02, tema Tourism).

**Autentikasi**
* Pengguna aplikasi: `POST /api/auth/login` lalu kirim `Authorization: Bearer <token>`.
  Peran: `wisatawan`, `pengelola`, `admin`.
* Kelompok lain: endpoint `/api/public/*` dengan header `X-API-Key: <kunci>`. Minta kunci ke admin Bebas.

**Bounded context** (nama di makalah → folder):
Identitas & Akses → `identity`, Katalog Tempat → `places`, Keramaian & Antrean → `crowd`,
Prediksi Kondisi Perjalanan → `prediction`, Perencanaan Perjalanan → `planning`.
Notifikasi Perjalanan dikerjakan di Tugas 3; event-nya sudah diterbitkan di `/api/events`.

Waktu memakai WIB (UTC+7).
"""


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.check()
    init_db()
    conn = connect()
    try:
        if identity.ensure_admin(conn, settings.admin_email, settings.admin_password):
            log.info("akun admin %s dibuat dari .env", settings.admin_email)
    finally:
        conn.close()
    yield


app = FastAPI(title="Bebas Core Service", version=VERSION, description=DESCRIPTION, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", tags=["Health"], summary="Cek service hidup")
def health():
    db_ok = True
    try:
        conn = connect()
        conn.execute("SELECT 1").fetchone()
        conn.close()
    except Exception:  # noqa: BLE001
        db_ok = False
    return {
        "status": "ok" if db_ok else "degraded",
        "service": "bebas-core",
        "version": VERSION,
        "time": now_wib().isoformat(timespec="seconds"),
        "database": "ok" if db_ok else "error",
        "external_apis": settings.external_apis,
    }


@app.get("/api/events", tags=["Admin"], summary="Semua domain event (outbox), untuk konsumen internal")
def events(
    after: int = Query(0, ge=0),
    type: Optional[List[str]] = Query(None, description=f"filter: {', '.join(EVENT_TYPES)}"),
    limit: int = Query(100, ge=1, le=500),
    _: dict = Depends(require_roles("admin")),
    db: sqlite3.Connection = Depends(get_db),
):
    return list_events(db, after, type, limit)


for r in (identity_router, places_router, crowd_router, prediction_router, planning_router, public_router):
    app.include_router(r)
