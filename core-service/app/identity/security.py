"""Hash password (PBKDF2), JWT, dan API key. Hanya pustaka standar + PyJWT."""
import hashlib
import hmac
import secrets
from datetime import timedelta
from typing import Any, Dict, Tuple

import jwt

from ..common import utcnow
from ..config import settings

_ITER = 200_000
API_KEY_PREFIX = "bbs_"


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), _ITER)
    return f"pbkdf2_sha256${_ITER}${salt}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iters, salt, digest = stored.split("$")
    except ValueError:
        return False
    if algo != "pbkdf2_sha256":
        return False
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iters))
    return hmac.compare_digest(dk.hex(), digest)


def create_token(user_id: int, role: str) -> Tuple[str, int]:
    expires = settings.jwt_expire_minutes * 60
    now = utcnow()
    payload = {"sub": str(user_id), "role": role, "iat": now, "exp": now + timedelta(seconds=expires)}
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256"), expires


def decode_token(token: str) -> Dict[str, Any]:
    return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])


def generate_api_key() -> str:
    return API_KEY_PREFIX + secrets.token_urlsafe(32)


def hash_api_key(key: str) -> str:
    # API key acak 256-bit, jadi SHA-256 tanpa salt sudah cukup (bukan password manusia)
    return hashlib.sha256(key.encode()).hexdigest()
