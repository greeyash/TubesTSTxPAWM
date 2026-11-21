"""Utilitas bersama: zona waktu WIB, jarak geografis, format jam."""
import math
import re
from datetime import date, datetime, timedelta, timezone
from typing import Tuple

WIB = timezone(timedelta(hours=7), "WIB")
HHMM_PATTERN = r"^([01]\d|2[0-3]):[0-5]\d$"
_HHMM = re.compile(HHMM_PATTERN)
EARTH_R_KM = 6371.0

LatLon = Tuple[float, float]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def now_wib() -> datetime:
    return datetime.now(WIB)


def iso_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def to_wib(dt: datetime) -> datetime:
    """Datetime tanpa zona dianggap WIB."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=WIB)
    return dt.astimezone(WIB)


def hhmm_to_min(s: str) -> int:
    if not _HHMM.match(s):
        raise ValueError(f"format jam harus HH:MM, dapat {s!r}")
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def min_to_hhmm(m: float) -> str:
    m = int(round(m)) % (24 * 60)
    return f"{m // 60:02d}:{m % 60:02d}"


def at_time(d: date, hhmm: str) -> datetime:
    mins = hhmm_to_min(hhmm)
    return datetime(d.year, d.month, d.day, mins // 60, mins % 60, tzinfo=WIB)


def minute_of_day(dt: datetime) -> int:
    dt = to_wib(dt)
    return dt.hour * 60 + dt.minute


def is_weekend(d: date) -> bool:
    return d.weekday() >= 5


def haversine_km(a: LatLon, b: LatLon) -> float:
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_R_KM * math.asin(math.sqrt(h))


def point_segment_km(p: LatLon, a: LatLon, b: LatLon) -> float:
    """Jarak titik p ke ruas a-b (proyeksi equirectangular, cukup akurat untuk skala kota)."""
    lat0 = math.radians((a[0] + b[0] + p[0]) / 3)

    def xy(q: LatLon) -> Tuple[float, float]:
        return (math.radians(q[1]) * math.cos(lat0) * EARTH_R_KM, math.radians(q[0]) * EARTH_R_KM)

    px, py = xy(p)
    ax, ay = xy(a)
    bx, by = xy(b)
    dx, dy = bx - ax, by - ay
    seg2 = dx * dx + dy * dy
    t = 0.0 if seg2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / seg2))
    cx, cy = ax + t * dx, ay + t * dy
    return math.hypot(px - cx, py - cy)


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s or "tempat"
