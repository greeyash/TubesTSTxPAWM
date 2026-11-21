"""Anti-corruption layer untuk prakiraan cuaca (Open-Meteo).

Makalah menyebut BMKG. Untuk Tugas 2 dipakai Open-Meteo karena tidak perlu kode wilayah adm4 dan
mengembalikan prakiraan per jam. Karena semua istilah penyedia berhenti di adapter ini, mengganti
ke BMKG cukup dengan menulis ulang file ini.

Konteks lain hanya menerima `HourlyWeather` dan `RainImpact` (kategori dampak hujan). Kegagalan jaringan
atau tanggal di luar jangkauan prakiraan (lebih dari 16 hari) menghasilkan None, dan prediksi
berjalan tanpa faktor cuaca.
"""
import logging
import threading
import time
from dataclasses import dataclass
from datetime import date
from typing import Dict, Optional, Tuple

import httpx

from ..common import LatLon
from ..config import settings

log = logging.getLogger("bebas.weather")
_TTL_S = 30 * 60
_BACKOFF_S = 60
_down_until = 0.0


@dataclass(frozen=True)
class HourlyWeather:
    day: date
    precipitation_mm: Tuple[float, ...]  # 24 nilai, indeks = jam WIB
    precipitation_probability: Tuple[int, ...]
    source: str = "open-meteo"

    def at_hour(self, hour: int) -> Tuple[float, int]:
        return self.precipitation_mm[hour], self.precipitation_probability[hour]

    def impact_at(self, hour: int) -> "RainImpact":
        """Terjemahan ACL: curah hujan penyedia -> kategori dampak hujan terhadap kecepatan."""
        mm, prob = self.at_hour(hour)
        if mm >= 5:
            cat = "lebat"
        elif mm >= 1:
            cat = "sedang"
        elif mm >= 0.2 or prob >= 80:
            cat = "ringan"
        else:
            cat = "tidak_ada"
        return RainImpact(cat, mm, prob)


@dataclass(frozen=True)
class RainImpact:
    """Bahasa internal: kategori dampak hujan. Model prediksi hanya mengenal ini."""
    category: str  # tidak_ada | ringan | sedang | lebat
    precipitation_mm: float
    probability: int


_cache: Dict[Tuple[float, float, str], Tuple[float, Optional[HourlyWeather]]] = {}
_lock = threading.Lock()


def hourly(point: LatLon, day: date) -> Optional[HourlyWeather]:
    global _down_until
    if not settings.external_apis or time.time() < _down_until:
        return None
    # dibulatkan 0,1 derajat (~11 km): satu panggilan cukup untuk satu kawasan
    k = (round(point[0], 1), round(point[1], 1), day.isoformat())
    with _lock:
        hit = _cache.get(k)
        if hit and time.time() - hit[0] < _TTL_S:
            return hit[1]
    result: Optional[HourlyWeather] = None
    try:
        resp = httpx.get(
            settings.open_meteo_url,
            params={
                "latitude": k[0], "longitude": k[1],
                "hourly": "precipitation,precipitation_probability",
                "timezone": "Asia/Jakarta",
                "start_date": day.isoformat(), "end_date": day.isoformat(),
            },
            timeout=settings.http_timeout,
            headers={"User-Agent": settings.user_agent},
        )
        if resp.status_code == 400:  # tanggal di luar jangkauan prakiraan
            log.info("Open-Meteo: tanggal %s di luar jangkauan", day)
        else:
            resp.raise_for_status()
            h = resp.json()["hourly"]
            mm = [float(x or 0.0) for x in h["precipitation"]][:24]
            prob = [int(x or 0) for x in h.get("precipitation_probability", [0] * 24)][:24]
            if len(mm) == 24:
                result = HourlyWeather(day=day, precipitation_mm=tuple(mm),
                                       precipitation_probability=tuple(prob + [0] * (24 - len(prob))))
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as e:
        log.warning("Open-Meteo gagal (%s), prediksi tanpa cuaca selama %ds", e, _BACKOFF_S)
        _down_until = time.time() + _BACKOFF_S
        return None
    with _lock:
        _cache[k] = (time.time(), result)
    return result
