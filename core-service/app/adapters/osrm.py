"""Anti-corruption layer untuk OSRM.

Konteks lain hanya melihat `Route` (jarak km, durasi menit lancar). Format JSON OSRM, URL, dan
error jaringan tidak bocor ke luar adapter ini. Kalau OSRM gagal, fungsi mengembalikan None dan
pemanggil memakai cadangan jarak garis lurus.
"""
import logging
import threading
import time
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import httpx

from ..common import LatLon
from ..config import settings

log = logging.getLogger("bebas.osrm")


@dataclass(frozen=True)
class Route:
    distance_km: float
    duration_min: float
    source: str = "osrm"


_cache: Dict[Tuple[float, float, float, float], Optional[Route]] = {}
_lock = threading.Lock()
_MAX_CACHE = 2000
_BACKOFF_S = 60
_down_until = 0.0  # circuit breaker: setelah gagal, lewati OSRM selama _BACKOFF_S


def _key(a: LatLon, b: LatLon) -> Tuple[float, float, float, float]:
    return (round(a[0], 4), round(a[1], 4), round(b[0], 4), round(b[1], 4))


def route(a: LatLon, b: LatLon) -> Optional[Route]:
    global _down_until
    if not settings.external_apis or time.time() < _down_until:
        return None
    k = _key(a, b)
    with _lock:
        if k in _cache:
            return _cache[k]
    url = f"{settings.osrm_url}/route/v1/driving/{a[1]},{a[0]};{b[1]},{b[0]}"
    result: Optional[Route] = None
    try:
        resp = httpx.get(url, params={"overview": "false"}, timeout=settings.http_timeout,
                         headers={"User-Agent": settings.user_agent})
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") == "Ok" and data.get("routes"):
            r = data["routes"][0]
            result = Route(distance_km=r["distance"] / 1000.0, duration_min=r["duration"] / 60.0)
    except (httpx.HTTPError, ValueError, KeyError) as e:
        log.warning("OSRM gagal (%s), pakai cadangan garis lurus selama %ds", e, _BACKOFF_S)
        _down_until = time.time() + _BACKOFF_S
        return None  # jangan cache kegagalan
    with _lock:
        if len(_cache) >= _MAX_CACHE:
            _cache.clear()
        _cache[k] = result
    return result
