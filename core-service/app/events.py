"""Domain event (Published Language) yang dicatat ke tabel domain_events (outbox).

Event yang diterbitkan, sesuai peta konteks di makalah:
  * TempatDiperbarui      (Katalog Tempat -> Perencanaan)
  * StatusAntreanBerubah  (Keramaian & Antrean -> Perencanaan)
  * RencanaBerubah        (Perencanaan -> Notifikasi, dikerjakan di Tugas 3)

Konsumen membaca lewat GET /api/feed?since=<seq> (format feed Jelajah Nusantara, publik) atau
GET /api/events (admin, semua tipe). Notifikasi push (FCM) belum dibangun.
"""
import json
import sqlite3
from typing import Any, Dict, List, Optional

from .common import iso_utc, utcnow

EVENT_TYPES = ("TempatDiperbarui", "StatusAntreanBerubah", "RencanaBerubah")
PUBLIC_TYPES = ["TempatDiperbarui", "StatusAntreanBerubah"]  # RencanaBerubah memuat user_id -> tidak publik


def emit(db: sqlite3.Connection, type_: str, aggregate: str, aggregate_id: int, payload: Dict[str, Any]) -> None:
    """Dipanggil di dalam transaksi pemanggil; commit dilakukan pemanggil."""
    db.execute(
        "INSERT INTO domain_events(type, aggregate, aggregate_id, payload, occurred_at) VALUES (?,?,?,?,?)",
        (type_, aggregate, aggregate_id, json.dumps(payload, ensure_ascii=False), iso_utc(utcnow())),
    )


def list_events(db: sqlite3.Connection, after: int = 0, types: Optional[List[str]] = None,
                limit: int = 100) -> List[Dict[str, Any]]:
    sql, args = "SELECT * FROM domain_events WHERE id > ?", [after]  # type: str, List[Any]
    if types:
        sql += f" AND type IN ({','.join('?' * len(types))})"
        args += types
    sql += " ORDER BY id LIMIT ?"
    args.append(limit)
    out = []
    for r in db.execute(sql, args):
        d = dict(r)
        d["payload"] = json.loads(d["payload"])
        out.append(d)
    return out


def feed(db: sqlite3.Connection, since: int = 0, limit: int = 50) -> Dict[str, Any]:
    """Format feed bersama: {"events": [{"seq", "type", "occurred_at", "data"}], "next_since"}."""
    rows = list_events(db, since, PUBLIC_TYPES, limit)
    events = [{"seq": r["id"], "type": r["type"], "occurred_at": r["occurred_at"], "data": r["payload"]} for r in rows]
    return {"events": events, "next_since": events[-1]["seq"] if events else since}
