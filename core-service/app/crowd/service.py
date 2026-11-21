"""Konteks Keramaian: laporan dari pengguna, aturan validasi, dan status keramaian.

Aturan validasi laporan:
  1. Satu pengguna hanya boleh melapor satu kali per tempat dalam CROWD_COOLDOWN_MINUTES (default 30).
  2. Kalau pelapor menyertakan lokasi dan jaraknya > CROWD_MAX_DISTANCE_KM dari tempat -> ditolak (rejected).
  3. Laporan dari pengelola tempat itu atau admin -> valid, bobot 2.0.
  4. Wisatawan dengan lokasi dekat -> bobot 1.0; tanpa lokasi -> bobot 0.6.
  5. Pelapor yang sudah punya >= 5 laporan valid -> bobot x1.2 (reputasi).
  6. Pencilan: kalau ada >= 3 laporan valid 60 menit terakhir dan selisih dengan mediannya >= 3 level
     -> ditandai (flagged), bobot 0.2. Pengelola/admin bisa memvalidasi atau menolak manual.

Status keramaian = rata-rata berbobot laporan 90 menit terakhir dengan peluruhan waktu (half-life ~31 menit).
Kalau laporan sedikit, dicampur dengan perkiraan dari jam ramai tempat; kalau tidak ada laporan, pakai perkiraan saja.
"""
import math
import sqlite3
from datetime import datetime, timedelta, timezone
from statistics import median
from typing import Any, Dict, List, Optional

from ..common import haversine_km, iso_utc, now_wib, to_wib, utcnow
from ..config import settings
from ..events import emit
from ..places.service import get_place, is_open_at, is_peak_at

LABELS = {1: "sepi", 2: "sedang", 3: "ramai", 4: "sangat ramai", 5: "penuh sesak"}
# status antrean versi makalah: sepi / sedang / antre panjang
QUEUE = {1: "sepi", 2: "sepi", 3: "sedang", 4: "antre_panjang", 5: "antre_panjang"}


def queue_status(level: int) -> str:
    return QUEUE[level]
WINDOW_MIN = 90
DECAY_MIN = 45.0


class CrowdError(Exception):
    def __init__(self, msg: str, code: int = 400):
        super().__init__(msg)
        self.code = code


def _report_out(row: sqlite3.Row, distance: Optional[float] = None) -> Dict[str, Any]:
    d = dict(row)
    d.pop("reporter_lat", None)
    d.pop("reporter_lon", None)
    d["distance_km"] = None if distance is None else round(distance, 2)
    return d


def submit_report(db: sqlite3.Connection, place: Dict[str, Any], user: Dict[str, Any], level: int,
                  note: Optional[str], lat: Optional[float], lon: Optional[float]) -> Dict[str, Any]:
    now = utcnow()
    cooldown_from = iso_utc(now - timedelta(minutes=settings.crowd_cooldown_minutes))
    if db.execute(
        "SELECT 1 FROM crowd_reports WHERE place_id = ? AND user_id = ? AND created_at >= ?",
        (place["id"], user["id"], cooldown_from),
    ).fetchone():
        raise CrowdError(f"kamu sudah melapor tempat ini dalam {settings.crowd_cooldown_minutes} menit terakhir", 429)
    if (lat is None) != (lon is None):
        raise CrowdError("lat dan lon harus diisi berdua", 422)

    distance = haversine_km((lat, lon), (place["lat"], place["lon"])) if lat is not None else None
    is_manager = user["role"] == "admin" or (
        user["role"] == "pengelola" and user.get("verified") and place.get("manager_id") == user["id"])
    before = crowd_status(db, place)["level"]

    if distance is not None and distance > settings.crowd_max_distance_km and not is_manager:
        status, weight, reason = "rejected", 0.0, f"lokasi pelapor {distance:.1f} km dari tempat"
    elif is_manager:
        status, weight, reason = "valid", 2.0, "laporan pengelola/admin"
    else:
        status = "valid"
        weight, reason = (1.0, "lokasi terverifikasi") if distance is not None else (0.6, "tanpa lokasi")
        past_valid = db.execute(
            "SELECT COUNT(*) FROM crowd_reports WHERE user_id = ? AND status = 'valid'", (user["id"],)
        ).fetchone()[0]
        if past_valid >= 5:
            weight *= 1.2
            reason += ", pelapor tepercaya"
        recent = [r[0] for r in db.execute(
            "SELECT level FROM crowd_reports WHERE place_id = ? AND status = 'valid' AND created_at >= ?",
            (place["id"], iso_utc(now - timedelta(minutes=60))),
        )]
        if len(recent) >= 3 and abs(level - median(recent)) >= 3:
            status, weight = "flagged", 0.2
            reason = f"berbeda jauh dari laporan lain (median {median(recent):g})"

    cur = db.execute(
        "INSERT INTO crowd_reports(place_id,user_id,level,note,reporter_lat,reporter_lon,status,weight,reason,created_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?)",
        (place["id"], user["id"], level, note, lat, lon, status, round(weight, 2), reason, iso_utc(now)),
    )
    _emit_if_changed(db, place, before)
    db.commit()
    row = db.execute("SELECT * FROM crowd_reports WHERE id = ?", (cur.lastrowid,)).fetchone()
    return _report_out(row, distance)


def list_reports(db: sqlite3.Connection, place_id: int, limit: int = 50) -> List[Dict[str, Any]]:
    rows = db.execute(
        "SELECT * FROM crowd_reports WHERE place_id = ? ORDER BY created_at DESC, id DESC LIMIT ?", (place_id, limit)
    )
    return [_report_out(r) for r in rows]


def get_report(db: sqlite3.Connection, report_id: int) -> Optional[sqlite3.Row]:
    return db.execute("SELECT * FROM crowd_reports WHERE id = ?", (report_id,)).fetchone()


def moderate(db: sqlite3.Connection, report_id: int, status: str) -> Dict[str, Any]:
    row = get_report(db, report_id)
    if not row:
        raise CrowdError("laporan tidak ditemukan", 404)
    place = get_place(db, row["place_id"])
    before = crowd_status(db, place)["level"] if place else None
    weight = max(row["weight"], 1.0) if status == "valid" else 0.0
    db.execute("UPDATE crowd_reports SET status = ?, weight = ?, reason = ? WHERE id = ?",
               (status, weight, f"dimoderasi: {status}", report_id))
    if place and before is not None:
        _emit_if_changed(db, place, before)
    db.commit()
    return _report_out(get_report(db, report_id))  # type: ignore[arg-type]


def _emit_if_changed(db: sqlite3.Connection, place: Dict[str, Any], before: int) -> None:
    after = crowd_status(db, place)
    if after["level"] != before:
        emit(db, "StatusAntreanBerubah", "place", place["id"], {
            "place_id": place["id"], "level_sebelum": before, "level": after["level"],
            "queue_status": after["queue_status"], "source": after["source"], "at": after["at"],
        })


def estimate_level(place: Dict[str, Any], at: datetime) -> int:
    """Perkiraan tanpa laporan: berdasarkan jam buka dan jam ramai tempat."""
    if not is_open_at(place, at):
        return 1
    return 4 if is_peak_at(place, at) else 2


def crowd_status(db: sqlite3.Connection, place: Dict[str, Any], at: Optional[datetime] = None) -> Dict[str, Any]:
    at = to_wib(at) if at else now_wib()
    at_utc = at.astimezone(timezone.utc)
    since = iso_utc(at_utc - timedelta(minutes=WINDOW_MIN))
    rows = db.execute(
        "SELECT level, weight, created_at FROM crowd_reports"
        " WHERE place_id = ? AND status IN ('valid','flagged') AND created_at >= ? AND created_at <= ?",
        (place["id"], since, iso_utc(at_utc)),
    ).fetchall()

    estimate = estimate_level(place, at)
    num = den = 0.0
    for r in rows:
        age = (at_utc - datetime.fromisoformat(r["created_at"])).total_seconds() / 60
        w = r["weight"] * math.exp(-max(age, 0) / DECAY_MIN)
        num += w * r["level"]
        den += w
    confidence = round(min(1.0, den / 3.0), 2)
    notes = []
    if den < 0.05:
        score, source = float(estimate), "perkiraan"
        notes.append("belum ada laporan terbaru, memakai perkiraan dari jam ramai")
    else:
        reported = num / den
        score = confidence * reported + (1 - confidence) * estimate
        source = "laporan" if confidence >= 1.0 else "campuran"
    if not is_open_at(place, at):
        notes.append("tempat sedang tutup")
    level = max(1, min(5, int(round(score))))
    return {
        "place_id": place["id"], "place_name": place["name"], "level": level, "label": LABELS[level],
        "queue_status": queue_status(level),
        "score": round(score, 2), "source": source, "confidence": confidence if den >= 0.05 else 0.0,
        "report_count": len(rows), "window_minutes": WINDOW_MIN,
        "is_open": is_open_at(place, at), "is_peak": is_peak_at(place, at),
        "at": at.isoformat(timespec="minutes"), "notes": notes,
    }
