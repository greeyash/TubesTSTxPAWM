"""Dependency autentikasi: Bearer JWT untuk pengguna, X-API-Key untuk kelompok lain."""
import sqlite3
import threading
import time
from collections import deque
from typing import Any, Callable, Deque, Dict, Optional

import jwt
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer

from ..config import settings
from ..db import get_db
from . import service
from .security import decode_token

bearer = HTTPBearer(auto_error=False, description="JWT dari POST /api/auth/login")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False, description="API key dari admin Bebas")

User = Dict[str, Any]


def _unauthorized(msg: str) -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, msg, headers={"WWW-Authenticate": "Bearer"})


def get_current_user(
    cred: Optional[HTTPAuthorizationCredentials] = Security(bearer),
    db: sqlite3.Connection = Depends(get_db),
) -> User:
    if cred is None:
        raise _unauthorized("perlu token Bearer")
    try:
        payload = decode_token(cred.credentials)
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise _unauthorized("token tidak valid atau kedaluwarsa")
    user = service.get_user(db, user_id)
    if not user:
        raise _unauthorized("pengguna tidak ditemukan")
    return user


def require_roles(*roles: str) -> Callable[..., User]:
    def dep(user: User = Depends(get_current_user)) -> User:
        if user["role"] not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"hanya untuk peran: {', '.join(roles)}")
        return user

    return dep


def require_api_key(
    key: Optional[str] = Security(api_key_header),
    db: sqlite3.Connection = Depends(get_db),
) -> Dict[str, Any]:
    if not key:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "perlu header X-API-Key")
    client = service.check_api_key(db, key)
    if not client:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "API key tidak valid atau sudah dicabut")
    _rate_limit(client["id"])
    return client


_calls: Dict[int, Deque[float]] = {}
_calls_lock = threading.Lock()


def _rate_limit(key_id: int) -> None:
    """Jendela geser 60 detik per API key (default 120 panggilan/menit)."""
    now = time.monotonic()
    with _calls_lock:
        q = _calls.setdefault(key_id, deque())
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= settings.api_key_rate_per_min:
            retry = int(60 - (now - q[0])) + 1
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                                f"batas {settings.api_key_rate_per_min} panggilan/menit per API key terlampaui",
                                headers={"Retry-After": str(retry)})
        q.append(now)


def require_manager(user: User = Depends(get_current_user)) -> User:
    """Admin, atau pengelola yang sudah diverifikasi."""
    if user["role"] == "admin":
        return user
    if user["role"] != "pengelola":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "hanya untuk peran: pengelola, admin")
    if not user["verified"]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "akun pengelola belum diverifikasi admin")
    return user
