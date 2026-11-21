"""Konteks Tempat: data tempat wisata dan aturan jam buka/ramai."""
import json
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..events import emit
from ..common import hhmm_to_min, is_weekend, iso_utc, minute_of_day, now_wib, slugify, to_wib, utcnow

JSON_FIELDS = ("closed_days", "peak_hours", "parking", "signature_menu")
LIST_FIELDS = ("closed_days", "signature_menu")
BOOL_FIELDS = ("rain_friendly", "halal")
NULLABLE = ("description", "address", "corridor_slug", "manager_id", "food_type", "price_level")
LATE_CLOSE_MIN = 21 * 60


class PlaceError(Exception):
    def __init__(self, msg: str, code: int = 400):
        super().__init__(msg)
        self.code = code


def row_to_place(row: sqlite3.Row, at: Optional[datetime] = None) -> Dict[str, Any]:
    p = dict(row)
    for f in JSON_FIELDS:
        p[f] = json.loads(p[f]) if p[f] else ([] if f in LIST_FIELDS else {})
    for f in BOOL_FIELDS:
        p[f] = bool(p[f])
    p["parking"].setdefault("vehicle", "mobil")
    at = at or now_wib()
    p["is_open_now"] = is_open_at(p, at)
    p["is_peak_now"] = is_peak_at(p, at)
    p["open_late"] = is_open_late(p)
    p["zone"] = zone_of(p["lat"])
    p["peak_hint"] = peak_hint(p, at)
    return p


def zone_of(lat: float) -> str:
    """Kawasan kasar: utara (Lembang, Dago Pakar), kota, selatan (Soreang, Ciwidey)."""
    if lat > -6.87:
        return "utara"
    if lat < -6.98:
        return "selatan"
    return "kota"


def is_open_late(place: Dict[str, Any]) -> bool:
    o, c = hhmm_to_min(place["open_time"]), hhmm_to_min(place["close_time"])
    return c <= o or c >= LATE_CLOSE_MIN


def _fmt(hhmm: str) -> str:
    return hhmm.replace(":", ".")


def peak_hint(place: Dict[str, Any], at: datetime) -> Optional[str]:
    """Contoh: 'ramai pukul 12.00-13.00, disarankan datang 11.00'."""
    ranges = place.get("peak_hours", {}).get("weekend" if is_weekend(to_wib(at).date()) else "weekday", [])
    if not ranges:
        return None
    a, b = ranges[0]
    o = hhmm_to_min(place["open_time"])
    before = hhmm_to_min(a) - 60
    if before >= o:
        tip = f"disarankan datang {before // 60:02d}.{before % 60:02d}"
    else:
        tip = f"disarankan datang setelah {_fmt(b)}"
    others = ", ".join(f"{_fmt(x)}-{_fmt(y)}" for x, y in ranges[1:])
    extra = f" dan {others}" if others else ""
    return f"ramai pukul {_fmt(a)}-{_fmt(b)}{extra}, {tip}"


def is_open_at(place: Dict[str, Any], dt: datetime) -> bool:
    dt = to_wib(dt)
    if dt.weekday() in place.get("closed_days", []):
        return False
    m = minute_of_day(dt)
    o, c = hhmm_to_min(place["open_time"]), hhmm_to_min(place["close_time"])
    if c <= o:  # buka melewati tengah malam
        return m >= o or m < c
    return o <= m < c


def is_peak_at(place: Dict[str, Any], dt: datetime) -> bool:
    dt = to_wib(dt)
    ranges = place.get("peak_hours", {}).get("weekend" if is_weekend(dt.date()) else "weekday", [])
    m = minute_of_day(dt)
    return any(hhmm_to_min(a) <= m < hhmm_to_min(b) for a, b in ranges)


def list_places(
    db: sqlite3.Connection,
    category: Optional[str] = None,
    rain_friendly: Optional[bool] = None,
    halal: Optional[bool] = None,
    q: Optional[str] = None,
    corridor: Optional[str] = None,
    manager_id: Optional[int] = None,
    food_type: Optional[str] = None,
    price_max: Optional[int] = None,
    open_late: Optional[bool] = None,
    open_now: Optional[bool] = None,
) -> List[Dict[str, Any]]:
    sql, args = "SELECT * FROM places WHERE 1=1", []  # type: str, List[Any]
    if category:
        sql += " AND category = ?"
        args.append(category)
    if rain_friendly is not None:
        sql += " AND rain_friendly = ?"
        args.append(int(rain_friendly))
    if halal is not None:
        sql += " AND halal = ?"
        args.append(int(halal))
    if corridor:
        sql += " AND corridor_slug = ?"
        args.append(corridor)
    if manager_id is not None:
        sql += " AND manager_id = ?"
        args.append(manager_id)
    if food_type:
        sql += " AND food_type = ?"
        args.append(food_type)
    if price_max is not None:
        sql += " AND (price_level IS NULL OR price_level <= ?)"
        args.append(price_max)
    if q:
        sql += " AND (name LIKE ? OR description LIKE ? OR address LIKE ?)"
        args += [f"%{q}%"] * 3
    sql += " ORDER BY name"
    now = now_wib()
    out = [row_to_place(r, now) for r in db.execute(sql, args)]
    if open_late is not None:
        out = [p for p in out if p["open_late"] == open_late]
    if open_now is not None:
        out = [p for p in out if p["is_open_now"] == open_now]
    return out


def get_place(db: sqlite3.Connection, place_id: int) -> Optional[Dict[str, Any]]:
    row = db.execute("SELECT * FROM places WHERE id = ?", (place_id,)).fetchone()
    return row_to_place(row) if row else None


def require_place(db: sqlite3.Connection, place_id: int) -> Dict[str, Any]:
    p = get_place(db, place_id)
    if not p:
        raise PlaceError("tempat tidak ditemukan", 404)
    return p


def can_manage(user: Dict[str, Any], place: Dict[str, Any]) -> bool:
    if user["role"] == "admin":
        return True
    return user["role"] == "pengelola" and bool(user.get("verified")) and place.get("manager_id") == user["id"]


def _check_food(data: Dict[str, Any], current: Optional[Dict[str, Any]] = None) -> None:
    category = data.get("category") or (current or {}).get("category")
    food = data["food_type"] if "food_type" in data else (current or {}).get("food_type")
    if food and category != "kuliner":
        raise PlaceError("food_type hanya untuk kategori kuliner", 422)


def _check_refs(db: sqlite3.Connection, data: Dict[str, Any]) -> None:
    if data.get("corridor_slug") and not db.execute(
        "SELECT 1 FROM corridors WHERE slug = ?", (data["corridor_slug"],)
    ).fetchone():
        raise PlaceError("corridor_slug tidak dikenal", 422)
    if data.get("manager_id") is not None:
        row = db.execute("SELECT role FROM users WHERE id = ?", (data["manager_id"],)).fetchone()
        if not row or row["role"] != "pengelola":
            raise PlaceError("manager_id harus akun berperan pengelola", 422)


def _unique_slug(db: sqlite3.Connection, base: str) -> str:
    slug, i = base, 2
    while db.execute("SELECT 1 FROM places WHERE slug = ?", (slug,)).fetchone():
        slug, i = f"{base}-{i}", i + 1
    return slug


def _serialize(data: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(data)
    for f in JSON_FIELDS:
        if f in out and out[f] is not None:
            out[f] = json.dumps(out[f], ensure_ascii=False)
    for f in BOOL_FIELDS:
        if f in out and out[f] is not None:
            out[f] = int(out[f])
    return out


def create_place(db: sqlite3.Connection, data: Dict[str, Any], user: Dict[str, Any]) -> Dict[str, Any]:
    if user["role"] == "pengelola":
        data["manager_id"] = user["id"]  # pengelola otomatis jadi pengelola tempat yang dia buat
    _check_food(data)
    _check_refs(db, data)
    if data.get("slug"):
        if db.execute("SELECT 1 FROM places WHERE slug = ?", (data["slug"],)).fetchone():
            raise PlaceError("slug sudah dipakai", 409)
    else:
        data["slug"] = _unique_slug(db, slugify(data["name"]))
    now = iso_utc(utcnow())
    data.update(created_at=now, updated_at=now)
    row = _serialize(data)
    cols = ", ".join(row)
    cur = db.execute(f"INSERT INTO places({cols}) VALUES ({', '.join('?' * len(row))})", list(row.values()))
    emit(db, "TempatDiperbarui", "place", cur.lastrowid, {"place_id": cur.lastrowid, "change": "dibuat",
                                                          "fields": sorted(data)})
    db.commit()
    return get_place(db, cur.lastrowid)  # type: ignore[return-value]


def update_place(db: sqlite3.Connection, place_id: int, data: Dict[str, Any], user: Dict[str, Any]) -> Dict[str, Any]:
    place = require_place(db, place_id)
    if not can_manage(user, place):
        raise PlaceError("hanya admin atau pengelola tempat ini yang boleh mengubah", 403)
    data = {k: v for k, v in data.items() if v is not None or k in NULLABLE}
    if "manager_id" in data and user["role"] != "admin":
        raise PlaceError("hanya admin yang boleh mengganti pengelola", 403)
    if not data:
        return place
    _check_food(data, place)
    _check_refs(db, data)
    merged_open = data.get("open_time", place["open_time"])
    merged_close = data.get("close_time", place["close_time"])
    if merged_open == merged_close:
        raise PlaceError("jam buka dan tutup tidak boleh sama", 422)
    data["updated_at"] = iso_utc(utcnow())
    row = _serialize(data)
    sets = ", ".join(f"{k} = ?" for k in row)
    db.execute(f"UPDATE places SET {sets} WHERE id = ?", [*row.values(), place_id])
    emit(db, "TempatDiperbarui", "place", place_id, {"place_id": place_id, "change": "diubah",
                                                     "fields": sorted(k for k in data if k != "updated_at")})
    db.commit()
    return get_place(db, place_id)  # type: ignore[return-value]
