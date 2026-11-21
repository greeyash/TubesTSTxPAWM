"""Bebas Core Service: perencana wisata satu hari di Bandung (tema Tourism, K02)."""
import logging
from contextlib import asynccontextmanager

import sqlite3
from typing import List, Optional

from fastapi import Depends, FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .common import now_wib
from .config import VERSION, settings
from .crowd.router import router as crowd_router
from .db import connect, get_db, init_db
from .events import EVENT_TYPES, feed, list_events
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
* Kelompok lain (server ke server): endpoint `/api/public/*` dengan header `X-API-Key: <kunci>`.
* Data non-pribadi (katalog, keramaian, prediksi kepadatan, feed) juga terbuka tanpa kunci, dibatasi rate limit,
  supaya aplikasi kelompok lain tidak perlu menyimpan API key di APK.

**Format error**: `{"error": "KODE_ERROR", "message": "..."}` (400/401/403/404/409/422/429/503).

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


ERROR_CODES = {400: "BAD_REQUEST", 401: "UNAUTHORIZED", 403: "FORBIDDEN", 404: "NOT_FOUND",
               405: "METHOD_NOT_ALLOWED", 409: "CONFLICT", 422: "VALIDATION_ERROR", 429: "RATE_LIMITED",
               500: "INTERNAL_ERROR", 503: "SERVICE_UNAVAILABLE"}


@app.exception_handler(StarletteHTTPException)
async def http_error(_: Request, exc: StarletteHTTPException):
    return JSONResponse({"error": ERROR_CODES.get(exc.status_code, f"HTTP_{exc.status_code}"),
                         "message": str(exc.detail)},
                        status_code=exc.status_code, headers=getattr(exc, "headers", None))


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError):
    details = [{"field": ".".join(str(x) for x in e["loc"] if x not in ("body", "query", "path")),
                "message": e["msg"]} for e in exc.errors()]
    message = "; ".join(f"{d['field'] or 'request'}: {d['message']}" for d in details[:3])
    return JSONResponse({"error": "VALIDATION_ERROR", "message": message, "details": details}, status_code=422)


@app.get("/api", tags=["Health"], summary="Info service dan tautan dokumentasi")
def api_root():
    return {
        "service": "bebas-core",
        "version": VERSION,
        "description": "Perencana wisata & kuliner Bandung berbasis prediksi kemacetan dan cuaca (K02, Tourism)",
        "docs": "/docs",
        "openapi": "/openapi.json",
        "health": "/api/health",
        "auth": "Bearer JWT (POST /api/auth/login) untuk pengguna; X-API-Key untuk /api/public/*",
    }


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


@app.get("/api/feed", tags=["Events"], summary="Feed event publik (format bersama Jelajah Nusantara)")
def public_feed(since: int = Query(0, ge=0, description="seq terakhir yang sudah diproses"),
                limit: int = Query(50, ge=1, le=200), db: sqlite3.Connection = Depends(get_db)):
    return feed(db, since, limit)


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
