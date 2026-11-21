"""Anti-corruption layer terhadap destinasi milik kelompok lain (Jelajah Nusantara K1 · Destination).

Core Bebas tidak memanggil API kelompok lain. Layanan integrasi atau aplikasi mengirim *snapshot* kecil
destinasi K1 (destination_id `dst_...`, nama, koordinat, jam buka, kategori, waktu pengambilan) di
dalam item rencana. Modul ini menerjemahkan snapshot itu menjadi "tempat" versi model Bebas supaya
bisa dijadwalkan dengan prediksi macet, cuaca, dan jam buka yang sama. Istilah K1 berhenti di sini.
"""
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from ..common import HHMM_PATTERN

# kategori K1 -> kategori Bebas (outdoor / indoor / landmark / kuliner)
CATEGORY_MAP = {
    "curug": "outdoor", "air_terjun": "outdoor", "pantai": "outdoor", "gunung": "outdoor", "danau": "outdoor",
    "hutan": "outdoor", "taman": "outdoor", "kebun": "outdoor", "goa": "outdoor", "bukit": "outdoor",
    "desa_adat": "landmark", "situs_sejarah": "landmark", "situs": "landmark", "candi": "landmark",
    "museum": "indoor", "galeri": "indoor",
    "kuliner_lokal": "kuliner", "kuliner": "kuliner",
}
# durasi kunjungan default per kategori K1 (menit), selaras dengan aturan K3
DEFAULT_DURATION = {"curug": 120, "air_terjun": 120, "pantai": 120, "gunung": 180, "situs_sejarah": 60,
                    "desa_adat": 90, "museum": 60, "kuliner_lokal": 60}
STALE_DAYS = 7
_HOURS = re.compile(r"^\s*(\d{2}:\d{2})\s*-\s*(\d{2}:\d{2})\s*$")
_HHMM = re.compile(HHMM_PATTERN)


def normalize_category(raw: Optional[str]) -> str:
    key = (raw or "").strip().lower().replace(" ", "_").replace("-", "_")
    return CATEGORY_MAP.get(key, "outdoor")  # tidak dikenal -> outdoor (paling hati-hati saat hujan)


def parse_hours(raw: Optional[str]) -> Optional[tuple]:
    if not raw:
        return None
    m = _HOURS.match(raw)
    if not m or not (_HHMM.match(m.group(1)) and _HHMM.match(m.group(2))):
        raise ValueError("opening_hours harus berbentuk HH:MM-HH:MM, mis. 07:00-16:00")
    return m.group(1), m.group(2)


def default_duration(raw_category: Optional[str]) -> int:
    key = (raw_category or "").strip().lower().replace(" ", "_").replace("-", "_")
    return DEFAULT_DURATION.get(key, 90)


def to_place(ref: str, snap: Dict[str, Any]) -> Dict[str, Any]:
    """Snapshot K1 -> dict tempat yang dipahami simulasi jadwal Bebas."""
    hours = parse_hours(snap.get("opening_hours")) or ("00:00", "23:59")
    category = normalize_category(snap.get("category"))
    rain = snap.get("rain_friendly")
    return {
        "id": None, "external_ref": ref, "name": snap["name"], "category": category,
        "source_category": snap.get("category"), "lat": snap["lat"], "lon": snap["lon"],
        "open_time": hours[0], "close_time": hours[1], "closed_days": [], "peak_hours": {},
        "rain_friendly": bool(rain) if rain is not None else category in ("indoor", "kuliner"),
        "avg_visit_minutes": default_duration(snap.get("category")),
        "captured_at": snap.get("captured_at"),
    }


def is_stale(snap: Dict[str, Any], now: Optional[datetime] = None) -> bool:
    raw = snap.get("captured_at")
    if not raw:
        return False
    try:
        ts = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return False
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return (now or datetime.now(timezone.utc)) - ts > timedelta(days=STALE_DAYS)
