"""Rekomendasi seketika: mode "Mau makan sekarang" (subdomain Penjadwalan Kunjungan Adaptif).

Menampilkan tempat makan yang masih buka (minimal 30 menit lagi), dekat, jalannya tidak macet, dan
antreannya tidak panjang. Tempat disembunyikan hanya kalau laporan (bukan sekadar perkiraan jam ramai)
menyatakan antre panjang; perkiraan jam ramai cukup menaikkan skor. Skor = menit perjalanan + penalti antrean (sedang 10, antre panjang 30)
+ 10 kalau jalan padat. Makin kecil makin direkomendasikan.
"""
import sqlite3
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from ..adapters import weather
from ..common import LatLon, haversine_km
from ..crowd.service import crowd_status
from ..places.service import is_open_at, list_places
from ..prediction import service as pred

QUEUE_PEN = {"sepi": 0, "sedang": 10, "antre_panjang": 30}


def traffic_status(tf: float) -> str:
    return "lancar" if tf < 1.25 else "padat" if tf < 1.6 else "macet"


def eat_now(db: sqlite3.Connection, here: LatLon, at: datetime, radius_km: float = 5.0,
            price_max: Optional[int] = None, halal: Optional[bool] = None, food_type: Optional[str] = None,
            open_late: Optional[bool] = None, include_long_queue: bool = False, limit: int = 10) -> Dict[str, Any]:
    net = pred.load_network(db)
    wx = weather.hourly(here, at.date())
    wfn = lambda _p, d: wx if d == at.date() else None  # noqa: E731
    skipped = 0
    results = []
    for p in list_places(db, category="kuliner", halal=halal, food_type=food_type, price_max=price_max,
                         open_late=open_late):
        dist = haversine_km(here, (p["lat"], p["lon"]))
        if dist > radius_km or not is_open_at(p, at) or not is_open_at(p, at + timedelta(minutes=30)):
            continue
        crowd = crowd_status(db, p, at)
        reported = crowd["source"] != "perkiraan"
        if crowd["queue_status"] == "antre_panjang" and reported and not include_long_queue:
            skipped += 1
            continue
        results.append((p, dist, crowd))

    def score(p: Dict[str, Any], dist: float, crowd: Dict[str, Any], network: bool) -> Dict[str, Any]:
        leg = pred.plan_leg(net, here, (p["lat"], p["lon"]), use_network=network)
        est = pred.estimate(net, leg, at, weather_fn=wfn)
        ts = traffic_status(est["traffic_factor"])
        s = est["predicted_minutes"] + QUEUE_PEN[crowd["queue_status"]] + (10 if ts != "lancar" else 0)
        return {
            "place_id": p["id"], "name": p["name"], "food_type": p["food_type"], "price_level": p["price_level"],
            "halal": p["halal"], "signature_menu": p["signature_menu"], "distance_km": round(dist, 2),
            "travel_minutes": est["predicted_minutes"], "traffic_status": ts,
            "queue_status": crowd["queue_status"], "crowd_label": crowd["label"], "crowd_source": crowd["source"],
            "parking": p["parking"], "peak_hint": p["peak_hint"], "closes_at": p["close_time"],
            "open_late": p["open_late"], "photo": p.get("photo"), "confidence": est["confidence"]["level"],
            "routing": est["sources"]["routing"], "score": round(s, 1),
        }

    # urutkan cepat dengan garis lurus, lalu hitung ulang kandidat teratas dengan OSRM
    rough = sorted((score(p, d, c, False) for p, d, c in results), key=lambda r: r["score"])
    top_ids = {r["place_id"] for r in rough[:limit]}
    refined = [score(p, d, c, True) for p, d, c in results if p["id"] in top_ids]
    refined.sort(key=lambda r: r["score"])
    return {
        "at": at.isoformat(timespec="minutes"), "origin": {"lat": here[0], "lon": here[1]},
        "radius_km": radius_km, "skipped_long_queue": skipped, "results": refined,
    }
