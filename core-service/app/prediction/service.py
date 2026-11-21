"""Konteks Prediksi: koridor, faktor jam, waktu tempuh, dan jendela berangkat.

Model waktu tempuh:
  menit = waktu_lancar x faktor_lalu_lintas(jam, hari) x faktor_cuaca(hujan)

  * waktu_lancar   : durasi OSRM; kalau OSRM tidak tersedia, jarak garis lurus x 1,3 dibagi kecepatan dasar
                     (kecepatan koridor untuk bagian yang melewati koridor, 30 km/jam untuk sisanya).
  * faktor lalu lintas : rata-rata berbobot faktor jam setiap koridor yang dilewati (bobot = porsi
                     perjalanan di koridor itu), sisanya memakai profil jalan kota umum. Faktor
                     diinterpolasi linear antarjam dan dihitung di titik tengah perjalanan.
  * faktor cuaca   : dari kategori dampak hujan hasil ACL cuaca:
                     lebat (>= 5 mm/jam) x1,30; sedang (>= 1 mm) x1,18; ringan (>= 0,2 mm / peluang >= 80%) x1,08.
  * tingkat keyakinan: 0..1, turun kalau routing memakai cadangan, prakiraan cuaca tidak tersedia,
                     waktu berangkat jauh di depan, atau sedang hujan. >= 0,75 tinggi, >= 0,55 sedang.
"""
import json
import math
import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple

from ..adapters import osrm, weather
from ..adapters.weather import HourlyWeather, RainImpact
from ..common import LatLon, at_time, now_wib, haversine_km, is_weekend, point_segment_km, to_wib

DETOUR = 1.3          # jalan sebenarnya ~30% lebih panjang dari garis lurus
NEAR_KM = 1.5         # koridor dianggap dilewati kalau berjarak <= 1,5 km dari rute
DEFAULT_SPEED = 30.0

WeatherFn = Callable[[LatLon, date], Optional[HourlyWeather]]


class PredictionError(Exception):
    def __init__(self, msg: str, code: int = 400):
        super().__init__(msg)
        self.code = code


@dataclass
class Corridor:
    id: int
    slug: str
    name: str
    start: LatLon
    end: LatLon
    length_km: float
    base_speed_kmh: float
    factors: Dict[str, List[float]]
    notes: Optional[str] = None


@dataclass
class Network:
    corridors: List[Corridor]
    default_speed: float
    default_factors: Dict[str, List[float]]


@dataclass
class Leg:
    a: LatLon
    b: LatLon
    distance_km: float
    osrm_minutes: Optional[float]
    routing_source: str
    shares: List[Tuple[Corridor, float]] = field(default_factory=list)


# ---------- data ----------

def _corridor(row: sqlite3.Row) -> Corridor:
    return Corridor(row["id"], row["slug"], row["name"], (row["start_lat"], row["start_lon"]),
                    (row["end_lat"], row["end_lon"]), row["length_km"], row["base_speed_kmh"],
                    json.loads(row["factors"]), row["notes"])


def load_network(db: sqlite3.Connection) -> Network:
    corridors = [_corridor(r) for r in db.execute("SELECT * FROM corridors ORDER BY id")]
    meta = db.execute("SELECT value FROM meta WHERE key = 'default_profile'").fetchone()
    prof = json.loads(meta["value"]) if meta else {"base_speed_kmh": DEFAULT_SPEED, "factors": {
        "weekday": [1.0] * 24, "weekend": [1.0] * 24}}
    return Network(corridors, float(prof["base_speed_kmh"]), prof["factors"])


def corridor_out(c: Corridor) -> Dict[str, Any]:
    return {"id": c.id, "slug": c.slug, "name": c.name,
            "start": {"lat": c.start[0], "lon": c.start[1]}, "end": {"lat": c.end[0], "lon": c.end[1]},
            "length_km": c.length_km, "base_speed_kmh": c.base_speed_kmh, "factors": c.factors, "notes": c.notes}


# ---------- geometri koridor ----------

def _project_t(p: LatLon, a: LatLon, b: LatLon) -> float:
    lat0 = math.radians((a[0] + b[0]) / 2)
    ax, ay = math.radians(a[1]) * math.cos(lat0), math.radians(a[0])
    bx, by = math.radians(b[1]) * math.cos(lat0), math.radians(b[0])
    px, py = math.radians(p[1]) * math.cos(lat0), math.radians(p[0])
    dx, dy = bx - ax, by - ay
    seg2 = dx * dx + dy * dy
    if seg2 == 0:
        return 0.0
    return max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / seg2))


def corridor_shares(net: Network, a: LatLon, b: LatLon) -> List[Tuple[Corridor, float]]:
    """Porsi perjalanan a->b yang melewati tiap koridor (0..1)."""
    shares = []
    straight = haversine_km(a, b)
    for c in net.corridors:
        gap = min(point_segment_km(a, c.start, c.end), point_segment_km(b, c.start, c.end),
                  point_segment_km(c.start, a, b), point_segment_km(c.end, a, b))
        if gap > NEAR_KM:
            continue
        if straight < 0.05:
            ratio = 1.0
        else:
            ratio = abs(_project_t(c.end, a, b) - _project_t(c.start, a, b))
            # perjalanan pendek di dalam koridor: kedua ujung dekat koridor -> seluruhnya di koridor
            if point_segment_km(a, c.start, c.end) <= NEAR_KM and point_segment_km(b, c.start, c.end) <= NEAR_KM:
                ratio = max(ratio, min(1.0, c.length_km / max(straight * DETOUR, 0.1)))
        if ratio >= 0.05:
            shares.append((c, ratio))
    total = sum(r for _, r in shares)
    if total > 1.0:
        shares = [(c, r / total) for c, r in shares]
    return shares


def plan_leg(net: Network, a: LatLon, b: LatLon, use_network: bool = True) -> Leg:
    r = osrm.route(a, b) if use_network else None
    shares = corridor_shares(net, a, b)
    if r:
        return Leg(a, b, r.distance_km, r.duration_min, "osrm", shares)
    return Leg(a, b, haversine_km(a, b) * DETOUR, None, "garis-lurus", shares)


# ---------- faktor ----------

def factor_at(factors: Dict[str, List[float]], when: datetime) -> float:
    when = to_wib(when)
    table = factors["weekend" if is_weekend(when.date()) else "weekday"]
    h = when.hour + when.minute / 60.0
    lo = int(h) % 24
    hi = (lo + 1) % 24
    frac = h - int(h)
    return table[lo] * (1 - frac) + table[hi] * frac


def free_flow_minutes(net: Network, leg: Leg) -> float:
    if leg.osrm_minutes is not None:
        return max(leg.osrm_minutes, 1.0)
    rest = 1.0 - sum(r for _, r in leg.shares)
    hours = rest * leg.distance_km / net.default_speed
    hours += sum(r * leg.distance_km / c.base_speed_kmh for c, r in leg.shares)
    return max(hours * 60.0, 1.0)


def traffic_factor(net: Network, leg: Leg, when: datetime) -> Tuple[float, List[Dict[str, Any]]]:
    rest = 1.0 - sum(r for _, r in leg.shares)
    f = rest * factor_at(net.default_factors, when)
    detail = []
    for c, r in leg.shares:
        cf = factor_at(c.factors, when)
        f += r * cf
        detail.append({"slug": c.slug, "name": c.name, "share": round(r, 2), "factor": round(cf, 2)})
    return f, detail


RAIN_FACTOR = {"tidak_ada": 1.0, "ringan": 1.08, "sedang": 1.18, "lebat": 1.30}


def weather_factor(wx: Optional[HourlyWeather], when: datetime) -> Tuple[float, Optional[RainImpact]]:
    when = to_wib(when)
    if wx is None or wx.day != when.date():
        return 1.0, None
    impact = wx.impact_at(when.hour)
    return RAIN_FACTOR[impact.category], impact


def confidence(leg: Leg, depart: datetime, wx: Optional[HourlyWeather], impact: Optional[RainImpact]) -> Dict[str, Any]:
    score, reasons = 0.9, []
    if leg.routing_source != "osrm":
        score -= 0.2
        reasons.append("jarak memakai cadangan garis lurus")
    if wx is None:
        score -= 0.1
        reasons.append("prakiraan cuaca tidak tersedia")
    ahead_h = (to_wib(depart) - now_wib()).total_seconds() / 3600
    if ahead_h > 72:
        score -= 0.1
        reasons.append("berangkat lebih dari 3 hari lagi")
    if impact and impact.category in ("sedang", "lebat"):
        score -= 0.1
        reasons.append("hujan membuat waktu tempuh lebih tidak pasti")
    if not leg.shares:
        score -= 0.05
        reasons.append("rute di luar koridor yang dikalibrasi")
    score = round(max(0.1, min(1.0, score)), 2)
    level = "tinggi" if score >= 0.75 else "sedang" if score >= 0.55 else "rendah"
    return {"score": score, "level": level, "reasons": reasons}


def _midpoint(a: LatLon, b: LatLon) -> LatLon:
    return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)


def estimate(net: Network, leg: Leg, depart: datetime, weather_fn: Optional[WeatherFn] = weather.hourly) -> Dict[str, Any]:
    depart = to_wib(depart)
    wx = weather_fn(_midpoint(leg.a, leg.b), depart.date()) if weather_fn else None
    ff = free_flow_minutes(net, leg)
    tf, _ = traffic_factor(net, leg, depart)
    wf, _ = weather_factor(wx, depart)
    # hitung ulang di titik tengah perjalanan supaya perjalanan panjang lebih akurat
    mid = depart + timedelta(minutes=ff * tf * wf / 2)
    tf, detail = traffic_factor(net, leg, mid)
    wf, impact = weather_factor(wx, mid)
    minutes = ff * tf * wf
    return {
        "distance_km": round(leg.distance_km, 2),
        "free_flow_minutes": round(ff, 1),
        "traffic_factor": round(tf, 2),
        "weather_factor": round(wf, 2),
        "predicted_minutes": round(minutes, 1),
        "depart_at": depart.isoformat(timespec="minutes"),
        "arrive_at": (depart + timedelta(minutes=minutes)).isoformat(timespec="minutes"),
        "corridors": detail,
        "weather": {
            "precipitation_mm": impact.precipitation_mm if impact else None,
            "precipitation_probability": impact.probability if impact else None,
            "rain_impact": impact.category if impact else None,
        },
        "confidence": confidence(leg, depart, wx, impact),
        "sources": {"routing": leg.routing_source, "weather": wx.source if wx else "tidak-tersedia"},
    }


# ---------- use case ----------

def predict_travel(db: sqlite3.Connection, a: LatLon, b: LatLon, depart: datetime) -> Dict[str, Any]:
    net = load_network(db)
    leg = plan_leg(net, a, b)
    return estimate(net, leg, depart)


def departure_window(db: sqlite3.Connection, a: LatLon, b: LatLon, day: date, earliest: str, latest: str,
                     step: int = 15, arrive_by: Optional[str] = None) -> Dict[str, Any]:
    start, end = at_time(day, earliest), at_time(day, latest)
    if end <= start:
        raise PredictionError("latest harus setelah earliest", 422)
    if (end - start) / timedelta(minutes=step) > 96:
        raise PredictionError("terlalu banyak slot, perbesar step atau persempit rentang", 422)
    deadline = at_time(day, arrive_by) if arrive_by else None

    net = load_network(db)
    leg = plan_leg(net, a, b)
    slots = []
    t = start
    while t <= end:
        e = estimate(net, leg, t)
        arrive = datetime.fromisoformat(e["arrive_at"])
        slots.append({
            "depart_at": t.strftime("%H:%M"), "arrive_at": arrive.strftime("%H:%M"),
            "minutes": e["predicted_minutes"], "traffic_factor": e["traffic_factor"],
            "weather_factor": e["weather_factor"],
            "confidence": e["confidence"]["level"],
            "on_time": None if deadline is None else arrive <= deadline,
        })
        t += timedelta(minutes=step)

    candidates = [s for s in slots if s["on_time"] is not False]
    notes = []
    if not candidates:
        notes.append("tidak ada jam berangkat yang tiba sebelum arrive_by; pilih rentang lebih pagi")
        candidates = slots
    best_min = min(s["minutes"] for s in candidates)
    if deadline is not None:
        # dengan tenggat: berangkat paling akhir yang waktunya masih <= 110% dari tercepat
        best = [s for s in candidates if s["minutes"] <= best_min * 1.10][-1]
    else:
        best = min(candidates, key=lambda s: s["minutes"])

    # jendela rekomendasi: slot berurutan di sekitar `best` yang <= 110% dari tercepat
    idx = slots.index(best)
    lo = hi = idx
    ok = lambda s: s["minutes"] <= best_min * 1.10 and s["on_time"] is not False  # noqa: E731
    while lo > 0 and ok(slots[lo - 1]):
        lo -= 1
    while hi < len(slots) - 1 and ok(slots[hi + 1]):
        hi += 1
    avoid = _ranges([s for s in slots if s["minutes"] >= best_min * 1.35])
    worst = max(slots, key=lambda s: s["minutes"])
    if worst["minutes"] > best_min * 1.2:
        notes.append(f"berangkat {worst['depart_at']} paling lama ({worst['minutes']:.0f} menit), "
                     f"selisih {worst['minutes'] - best_min:.0f} menit dari yang tercepat")

    first = estimate(net, leg, start)
    return {
        "date": day.isoformat(),
        "distance_km": round(leg.distance_km, 2),
        "corridors": first["corridors"],
        "sources": first["sources"],
        "best": best,
        "recommended_window": {"start": slots[lo]["depart_at"], "end": slots[hi]["depart_at"],
                               "max_minutes": max(s["minutes"] for s in slots[lo:hi + 1])},
        "avoid": avoid,
        "slots": slots,
        "notes": notes,
    }


def _ranges(slots: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    for s in slots:
        if out and _gap_ok(out[-1]["end"], s["depart_at"]):
            out[-1]["end"] = s["depart_at"]
        else:
            out.append({"start": s["depart_at"], "end": s["depart_at"]})
    return out


def _gap_ok(prev: str, cur: str) -> bool:
    ph, pm = map(int, prev.split(":"))
    ch, cm = map(int, cur.split(":"))
    return 0 < (ch * 60 + cm) - (ph * 60 + pm) <= 30


def corridor_factors(net: Network, slug: str, day: date) -> Dict[str, Any]:
    c = next((c for c in net.corridors if c.slug == slug), None)
    if not c:
        raise PredictionError("koridor tidak ditemukan", 404)
    kind = "weekend" if is_weekend(day) else "weekday"
    table = c.factors[kind]
    return {
        "slug": c.slug, "name": c.name, "date": day.isoformat(), "day_type": kind,
        "hours": [{"hour": f"{h:02d}:00", "factor": table[h],
                   "minutes": round(c.length_km / c.base_speed_kmh * 60 * table[h], 1)} for h in range(24)],
    }


