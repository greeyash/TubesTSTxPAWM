import sqlite3
from typing import Any, Dict, List, Optional

from ..common import iso_utc, utcnow
from . import security

USER_COLS = "id, email, name, role, verified, created_at"


class IdentityError(Exception):
    pass


def get_user(db: sqlite3.Connection, user_id: int) -> Optional[Dict[str, Any]]:
    row = db.execute(f"SELECT {USER_COLS} FROM users WHERE id = ?", (user_id,)).fetchone()
    return _user(row) if row else None


def _user(row: sqlite3.Row) -> Dict[str, Any]:
    d = dict(row)
    d["verified"] = bool(d["verified"])
    return d


def create_user(db: sqlite3.Connection, email: str, name: str, password: str, role: str,
                verified: Optional[bool] = None) -> Dict[str, Any]:
    """Akun pengelola mendaftar dalam keadaan belum terverifikasi; admin memverifikasi."""
    if verified is None:
        verified = role != "pengelola"
    email = email.strip().lower()
    if db.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
        raise IdentityError("email sudah terdaftar")
    cur = db.execute(
        "INSERT INTO users(email, name, password_hash, role, verified, created_at) VALUES (?,?,?,?,?,?)",
        (email, name.strip(), security.hash_password(password), role, int(verified), iso_utc(utcnow())),
    )
    db.commit()
    return get_user(db, cur.lastrowid)  # type: ignore[return-value]


def authenticate(db: sqlite3.Connection, email: str, password: str) -> Optional[Dict[str, Any]]:
    row = db.execute("SELECT id, password_hash FROM users WHERE email = ?", (email.strip().lower(),)).fetchone()
    if not row or not security.verify_password(password, row["password_hash"]):
        return None
    return get_user(db, row["id"])


def list_users(db: sqlite3.Connection) -> List[Dict[str, Any]]:
    return [_user(r) for r in db.execute(f"SELECT {USER_COLS} FROM users ORDER BY id")]


def set_role(db: sqlite3.Connection, user_id: int, role: str) -> Optional[Dict[str, Any]]:
    db.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))
    db.commit()
    return get_user(db, user_id)


def set_verified(db: sqlite3.Connection, user_id: int, verified: bool) -> Optional[Dict[str, Any]]:
    db.execute("UPDATE users SET verified = ? WHERE id = ?", (int(verified), user_id))
    db.commit()
    return get_user(db, user_id)


def ensure_admin(db: sqlite3.Connection, email: str, password: str) -> bool:
    """Buat akun admin dari .env kalau belum ada. True kalau baru dibuat."""
    if not email or not password:
        return False
    if db.execute("SELECT 1 FROM users WHERE email = ?", (email.lower(),)).fetchone():
        return False
    create_user(db, email, "Administrator", password, "admin")
    return True


def _key_row(row: sqlite3.Row) -> Dict[str, Any]:
    d = dict(row)
    d["revoked"] = bool(d["revoked"])
    d.pop("key_hash", None)
    d.pop("created_by", None)
    return d


def create_api_key(db: sqlite3.Connection, client_name: str, created_by: Optional[int]) -> Dict[str, Any]:
    key = security.generate_api_key()
    cur = db.execute(
        "INSERT INTO api_keys(client_name, key_prefix, key_hash, created_by, created_at) VALUES (?,?,?,?,?)",
        (client_name.strip(), key[:10], security.hash_api_key(key), created_by, iso_utc(utcnow())),
    )
    db.commit()
    row = db.execute("SELECT * FROM api_keys WHERE id = ?", (cur.lastrowid,)).fetchone()
    out = _key_row(row)
    out["api_key"] = key
    return out


def list_api_keys(db: sqlite3.Connection) -> List[Dict[str, Any]]:
    return [_key_row(r) for r in db.execute("SELECT * FROM api_keys ORDER BY id")]


def revoke_api_key(db: sqlite3.Connection, key_id: int) -> bool:
    cur = db.execute("UPDATE api_keys SET revoked = 1 WHERE id = ?", (key_id,))
    db.commit()
    return cur.rowcount > 0


def check_api_key(db: sqlite3.Connection, key: str) -> Optional[Dict[str, Any]]:
    row = db.execute(
        "SELECT * FROM api_keys WHERE key_hash = ? AND revoked = 0", (security.hash_api_key(key),)
    ).fetchone()
    if not row:
        return None
    db.execute(
        "UPDATE api_keys SET last_used_at = ?, request_count = request_count + 1 WHERE id = ?",
        (iso_utc(utcnow()), row["id"]),
    )
    db.commit()
    return _key_row(row)
