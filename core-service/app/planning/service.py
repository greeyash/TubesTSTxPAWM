"""Konteks Perencanaan Perjalanan: agregat Itinerary (Kunjungan, Slot Makan, Jendela Berangkat).

Di konteks ini tempat hanya dipandang sebagai titik kunjungan dengan durasi dan batas waktu.
Jadwal dihitung ulang setiap kali rencana dibaca, supaya prakiraan cuaca, faktor jam, dan laporan
keramaian terbaru ikut terpakai.

Biaya sebuah urutan (makin kecil makin baik):
  menit perjalanan + 0,5 x menit menunggu
  + 300 tiba saat tempat tutup / hari libur      + 120 kunjungan melewati jam tutup
  + 200 terlambat > 10 menit dari jam yang dikunci + 150 slot makan di luar jendela makan
  + 45  tempat tidak cocok hujan saat hujan >= 1 mm + 40 dilaporkan antre panjang (laporan langsung)
  + 20  tiba di jam ramai
Tempat yang kehujanan, tutup, atau dilaporkan antre panjang diberi saran alternatif yang searah.
<= 7 kunjungan dicoba semua permutasi; lebih dari itu greedy + 2-opt.
Slot makan disisipkan di posisi dan tempat kuliner yang menambah biaya paling sedikit,
sehingga yang terpilih otomatis yang searah rute.
"""
import itertools
import json
import sqlite3
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ..adapters import weather
from ..common import WIB, LatLon, at_time, haversine_km, iso_utc, min_to_hhmm, hhmm_to_min, now_wib, utcnow
from ..crowd.service import LABELS, crowd_status, estimate_level, queue_status
from ..events import emit
from ..places.service import get_place, is_open_at, is_peak_at, list_places, zone_of
from ..prediction import service as pred
from . import external

PEN_CLOSED, PEN_OVERTIME, PEN_LOCK, PEN_MEAL = 300, 120, 200, 150
PEN_RAIN, PEN_CROWDED, PEN_PEAK, WAIT_W = 45, 40, 20, 0.5
LOCK_SLACK_MIN = 10

# jendela makan: (mulai, akhir, durasi default, jenis makanan yang cocok)
MEALS: Dict[str, Tuple[str, str, int, Tuple[str, ...]]] = {
    "makan_siang": ("11:00", "13:30", 60, ("makanan_berat", "sentra_kuliner", "kafe")),
    "jajan_sore": ("15:00", "17:30", 30, ("jajanan", "kafe", "oleh_oleh", "sentra_kuliner")),
}
Stop = Dict[str, Any]  # {id?, place_id | ext_ref+ext_snapshot, duration_minutes, kind, locked_time}


class PlanError(Exception):
    def __init__(self, msg: str, code: int = 400):
        super().__init__(msg)
        self.code = code


# ---------- penyimpanan ----------

def _plan_row(db: sqlite3.Connection, plan_id: int) -> Dict[str, Any]:
    row = db.execute("SELECT * FROM plans WHERE id = ?", (plan_id,)).fetchone()
    if not row:
        raise PlanError("rencana tidak ditemukan", 404)
    d = dict(row)
    d["options"] = json.loads(d["options"] or "{}")
    return d


def require_access(db: sqlite3.Connection, plan_id: int, user: Dict[str, Any]) -> Dict[str, Any]:
    plan = _plan_row(db, plan_id)
    if plan["user_id"] != user["id"] and user["role"] != "admin":
        raise PlanError("bukan rencana milikmu", 403)
    return plan


def _stops(db: sqlite3.Connection, plan_id: int) -> List[Stop]:
    out = []
    for r in db.execute(
            "SELECT id, place_id, ext_ref, ext_snapshot, duration_minutes, kind, locked_time FROM plan_items"
            " WHERE plan_id = ? ORDER BY position, id", (plan_id,)):
        d = dict(r)
        d["ext_snapshot"] = json.loads(d["ext_snapshot"]) if d["ext_snapshot"] else None
        out.append(d)
    return out


def _stops_from_input(db: sqlite3.Connection, items: Sequence[Dict[str, Any]]) -> List[Stop]:
    out: List[Stop] = []
    seen = set()
    for it in items:
        ext = it.get("external")
        if ext:
            ref = ext["destination_id"]
            if ref in seen:
                raise PlanError(f"destinasi {ref} muncul dua kali", 422)
            seen.add(ref)
            try:
                place = external.to_place(ref, ext)
            except ValueError as e:
                raise PlanError(f"{ref}: {e}", 422)
            out.append({"place_id": None, "ext_ref": ref, "ext_snapshot": ext,
                        "duration_minutes": it.get("duration_minutes") or place["avg_visit_minutes"],
                        "kind": "kunjungan", "locked_time": it.get("locked_time")})
            continue
        p = get_place(db, it["place_id"])
        if not p:
            raise PlanError(f"tempat {it['place_id']} tidak ditemukan", 422)
        if p["id"] in seen:
            raise PlanError(f"tempat {p['name']} muncul dua kali", 422)
        seen.add(p["id"])
        out.append({"place_id": p["id"], "ext_ref": None, "ext_snapshot": None,
                    "duration_minutes": it.get("duration_minutes") or p["avg_visit_minutes"],
                    "kind": "kunjungan", "locked_time": it.get("locked_time")})
    _check_locks(out)
    return out


def _check_locks(stops: Sequence[Stop]) -> None:
    times = [s["locked_time"] for s in stops if s.get("locked_time")]
    if len(times) != len(set(times)):
        raise PlanError("dua tempat dikunci pada jam yang sama", 422)


def _save_stops(db: sqlite3.Connection, plan_id: int, stops: Sequence[Stop]) -> None:
    """Simpan urutan. Item lama mempertahankan id-nya, item baru (slot makan) diberi id baru."""
    keep = {s["id"] for s in stops if s.get("id")}
    existing = {r[0] for r in db.execute("SELECT id FROM plan_items WHERE plan_id = ?", (plan_id,))}
    for gone in existing - keep:
        db.execute("DELETE FROM plan_items WHERE id = ?", (gone,))
    for pos, s in enumerate(stops, start=1):
        snap = json.dumps(s["ext_snapshot"], ensure_ascii=False) if s.get("ext_snapshot") else None
        vals = (s.get("place_id"), s.get("ext_ref"), snap, pos, s["duration_minutes"], s["kind"], s.get("locked_time"))
        if s.get("id") in existing:
            db.execute("UPDATE plan_items SET place_id=?, ext_ref=?, ext_snapshot=?, position=?, duration_minutes=?,"
                       " kind=?, locked_time=? WHERE id = ?", (*vals, s["id"]))
        else:
            db.execute("INSERT INTO plan_items(plan_id, place_id, ext_ref, ext_snapshot, position, duration_minutes,"
                       " kind, locked_time) VALUES (?,?,?,?,?,?,?,?)", (plan_id, *vals))


def _check_date(s: str) -> date:
    try:
        return date.fromisoformat(s)
    except ValueError:
        raise PlanError("tanggal tidak valid", 422)


def _meal_kinds(options: Dict[str, Any]) -> List[str]:
    kinds = []
    if options.get("insert_lunch"):
        kinds.append("makan_siang")
    if options.get("insert_snack"):
        kinds.append("jajan_sore")
    return kinds


def _event(db: sqlite3.Connection, plan: Dict[str, Any], change: str) -> None:
    emit(db, "RencanaBerubah", "plan", plan["id"], {
        "plan_id": plan["id"], "user_id": plan["user_id"], "change": change,
        "date": plan["date"], "start_time": plan["start_time"],
    })


def create_plan(db: sqlite3.Connection, user: Dict[str, Any], data: Dict[str, Any]) -> int:
    _check_date(data["date"])
    stops = _stops_from_input(db, data["items"])
    options = data.get("options") or {}
    now = iso_utc(utcnow())
    cur = db.execute(
        "INSERT INTO plans(user_id,title,date,start_time,origin_lat,origin_lon,options,created_at,updated_at)"
        " VALUES (?,?,?,?,?,?,?,?,?)",
        (user["id"], data["title"], data["date"], data["start_time"], data["origin"]["lat"], data["origin"]["lon"],
         json.dumps(options), now, now),
    )
    plan = _plan_row(db, cur.lastrowid)
    ctx = Context(db, plan, use_network=False)
    if data.get("optimize"):
        stops = best_order(ctx, stops)
    stops = insert_meals(ctx, stops, _meal_kinds(options), options)
    _save_stops(db, plan["id"], stops)
    _event(db, plan, "dibuat")
    db.commit()
    return plan["id"]


def list_plans(db: sqlite3.Connection, user: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = db.execute(
        "SELECT p.*, (SELECT COUNT(*) FROM plan_items i WHERE i.plan_id = p.id) AS item_count"
        " FROM plans p WHERE user_id = ? ORDER BY date DESC, id DESC", (user["id"],))
    return [dict(r) for r in rows]


def update_plan(db: sqlite3.Connection, plan_id: int, data: Dict[str, Any]) -> None:
    plan = _plan_row(db, plan_id)
    sets: Dict[str, Any] = {}
    for k in ("title", "date", "start_time"):
        if data.get(k) is not None:
            sets[k] = data[k]
    if "date" in sets:
        _check_date(sets["date"])
    if data.get("origin"):
        sets["origin_lat"], sets["origin_lon"] = data["origin"]["lat"], data["origin"]["lon"]
    options = plan["options"]
    if data.get("options") is not None:
        options = {**options, **{k: v for k, v in data["options"].items() if v is not None}}
        sets["options"] = json.dumps(options)
    sets["updated_at"] = iso_utc(utcnow())
    db.execute(f"UPDATE plans SET {', '.join(k + ' = ?' for k in sets)} WHERE id = ?", [*sets.values(), plan_id])

    timing_changed = any(k in data and data[k] is not None for k in ("items", "date", "start_time", "origin", "options"))
    if timing_changed:
        visits = (_stops_from_input(db, data["items"]) if data.get("items")
                  else [s for s in _stops(db, plan_id) if s["kind"] == "kunjungan"])
        plan = _plan_row(db, plan_id)
        ctx = Context(db, plan, use_network=False)
        stops = insert_meals(ctx, visits, _meal_kinds(options), options)
        _save_stops(db, plan_id, stops)
    _event(db, _plan_row(db, plan_id), "diubah")
    db.commit()


def delete_plan(db: sqlite3.Connection, plan_id: int) -> None:
    plan = _plan_row(db, plan_id)
    db.execute("DELETE FROM plans WHERE id = ?", (plan_id,))
    _event(db, plan, "dihapus")
    db.commit()


# ---------- simulasi jadwal ----------

class Context:
    """Data yang dipakai berulang saat mensimulasikan banyak urutan."""

    def __init__(self, db: sqlite3.Connection, plan: Dict[str, Any], use_network: bool = True,
                 fetch_weather: bool = True):
        self.db = db
        self.day = date.fromisoformat(plan["date"])
        self.start = at_time(self.day, plan["start_time"])
        self.origin: LatLon = (plan["origin_lat"], plan["origin_lon"])
        self.net = pred.load_network(db)
        self.use_network = use_network
        self._places: Dict[int, Dict[str, Any]] = {}
        self._live: Dict[int, Optional[int]] = {}
        self._legs: Dict[Tuple[LatLon, LatLon], pred.Leg] = {}
        self.wx = weather.hourly(self.origin, self.day) if fetch_weather else None  # satu kawasan, satu panggilan
        self.now = now_wib()

    def place(self, place_id: int) -> Dict[str, Any]:
        if place_id not in self._places:
            self._places[place_id] = get_place(self.db, place_id)  # type: ignore[assignment]
        return self._places[place_id]

    def place_of(self, stop: Stop) -> Dict[str, Any]:
        """Tempat Bebas, atau terjemahan snapshot destinasi kelompok lain (ACL)."""
        if stop.get("ext_ref"):
            return external.to_place(stop["ext_ref"], stop["ext_snapshot"])
        return self.place(stop["place_id"])

    def live_level(self, place: Dict[str, Any]) -> Optional[int]:
        """Level dari laporan langsung (bukan perkiraan), hanya bermakna untuk kunjungan dekat waktu sekarang."""
        if place["id"] is None:
            return None  # destinasi eksternal: Bebas tidak punya laporan keramaiannya
        if place["id"] not in self._live:
            st = crowd_status(self.db, place, self.now)
            self._live[place["id"]] = st["level"] if st["source"] != "perkiraan" else None
        return self._live[place["id"]]

    def weather_fn(self, _point: LatLon, day: date):
        return self.wx if day == self.day else None

    def leg(self, a: LatLon, b: LatLon) -> pred.Leg:
        k = (a, b)
        if k not in self._legs:
            self._legs[k] = pred.plan_leg(self.net, a, b, use_network=self.use_network)
        return self._legs[k]

    def rain_at(self, t: datetime) -> Optional[float]:
        if self.wx is None or t.date() != self.day:
            return None
        return self.wx.at_hour(t.hour)[0]


def simulate(ctx: Context, stops: Sequence[Stop], start: Optional[datetime] = None,
             origin: Optional[LatLon] = None, detail: bool = False) -> Tuple[float, List[Dict[str, Any]], datetime]:
    t = start or ctx.start
    pos = origin or ctx.origin
    cost = 0.0
    rows: List[Dict[str, Any]] = []
    for idx, stop in enumerate(stops):
        place = ctx.place_of(stop)
        here: LatLon = (place["lat"], place["lon"])
        est = pred.estimate(ctx.net, ctx.leg(pos, here), t, weather_fn=ctx.weather_fn)
        travel = est["predicted_minutes"]
        arrive = t + timedelta(minutes=travel)
        warnings: List[str] = []
        start_visit = arrive
        wait = 0.0

        open_at = at_time(arrive.date(), place["open_time"])
        if arrive.weekday() in place["closed_days"]:
            cost += PEN_CLOSED
            warnings.append("tempat tutup pada hari ini")
        elif not is_open_at(place, arrive):
            if arrive < open_at:
                wait = (open_at - arrive).total_seconds() / 60
                start_visit = open_at
                warnings.append(f"tiba sebelum buka, menunggu {wait:.0f} menit")
            else:
                cost += PEN_CLOSED
                warnings.append("tiba setelah tempat tutup")

        if stop.get("locked_time"):
            locked = at_time(ctx.day, stop["locked_time"])
            if start_visit < locked:
                wait += (locked - start_visit).total_seconds() / 60
                start_visit = locked
            elif start_visit > locked + timedelta(minutes=LOCK_SLACK_MIN):
                late = (start_visit - locked).total_seconds() / 60
                cost += PEN_LOCK
                warnings.append(f"terlambat {late:.0f} menit dari jam yang dikunci {stop['locked_time']}")

        kind = stop.get("kind", "kunjungan")
        if kind in MEALS:
            ws, we, _, _ = MEALS[kind]
            sv = start_visit.hour * 60 + start_visit.minute
            if sv < hhmm_to_min(ws) - 15 or sv > hhmm_to_min(we):
                cost += PEN_MEAL
                warnings.append(f"slot {kind.replace('_', ' ')} di luar jam {ws}-{we}")

        depart = start_visit + timedelta(minutes=stop["duration_minutes"])
        close = place["close_time"]
        if close > place["open_time"] and is_open_at(place, start_visit) and \
                depart > at_time(start_visit.date(), close):
            cost += PEN_OVERTIME
            warnings.append(f"kunjungan melewati jam tutup {close}")
        if is_peak_at(place, start_visit):
            cost += PEN_PEAK
            warnings.append("tiba di jam ramai")
        live = ctx.live_level(place) if abs((start_visit - ctx.now).total_seconds()) <= 5400 else None
        if live is not None and live >= 4:
            cost += PEN_CROWDED
            warnings.append("dilaporkan antre panjang saat ini")
        if stop.get("ext_snapshot") and external.is_stale(stop["ext_snapshot"]):
            warnings.append("snapshot destinasi berumur > 7 hari, perlu disegarkan dari sumbernya")
        rain = ctx.rain_at(start_visit)
        if rain is not None and rain >= 1.0 and not place["rain_friendly"]:
            cost += PEN_RAIN
            warnings.append(f"diprediksi hujan {rain:.1f} mm/jam, tempat tidak cocok saat hujan")
        cost += travel + WAIT_W * wait

        if detail:
            level = live if live is not None else estimate_level(place, start_visit)
            rows.append({
                "item_id": stop.get("id"), "position": idx + 1, "kind": kind, "locked_time": stop.get("locked_time"),
                "place_id": place["id"], "external_ref": place.get("external_ref"),
                "place_name": place["name"], "category": place["category"],
                "zone": zone_of(place["lat"]), "travel_minutes": round(travel, 1),
                "travel_confidence": est["confidence"]["level"],
                "arrive_at": arrive.strftime("%H:%M"), "start_visit_at": start_visit.strftime("%H:%M"),
                "depart_at": depart.strftime("%H:%M"), "duration_minutes": stop["duration_minutes"],
                "wait_minutes": round(wait, 1), "crowd_estimate": level, "crowd_label": LABELS[level],
                "queue_status": queue_status(level), "rain_mm": rain,
                "photo_url": (place.get("photo") or {}).get("url"), "warnings": warnings,
                "_routing": est["sources"]["routing"],
            })
        t, pos = depart, here
    return cost, rows, t


def _summary(cost: float, rows: List[Dict[str, Any]], end: datetime) -> Dict[str, Any]:
    return {
        "end_at": end.strftime("%H:%M"),
        "total_travel_minutes": round(sum(r["travel_minutes"] for r in rows), 1),
        "total_wait_minutes": round(sum(r["wait_minutes"] for r in rows), 1),
        "warning_count": sum(len(r["warnings"]) for r in rows),
        "score": round(cost, 1),
    }


def plan_warnings(ctx: Context, rows: List[Dict[str, Any]], end: datetime) -> List[str]:
    out = []
    north = [r["place_name"] for r in rows if r["zone"] == "utara"]
    south = [r["place_name"] for r in rows if r["zone"] == "selatan"]
    if north and south:
        out.append(f"Kombinasi kawasan utara ({', '.join(north)}) dan selatan ({', '.join(south)}) "
                   "tidak realistis untuk satu hari: jaraknya jauh dan keduanya rawan macet akhir pekan.")
    if end.date() > ctx.day or end.hour >= 22:
        out.append(f"Rencana baru selesai pukul {end.strftime('%H:%M')}, pertimbangkan mengurangi tempat.")
    return out


def recommend_start(ctx: Context, stops: Sequence[Stop], base_cost: float) -> Dict[str, Any]:
    """Jendela Berangkat untuk itinerary: jam mulai dengan biaya terkecil (-60..+120 menit)."""
    best_t, best_c = ctx.start, base_cost
    for off in range(-60, 121, 15):
        t = ctx.start + timedelta(minutes=off)
        if t.date() != ctx.day:
            continue
        c = simulate(ctx, stops, start=t)[0]
        if c < best_c - 5:  # harus lebih baik secara berarti
            best_t, best_c = t, c
    planned = ctx.start.strftime("%H:%M")
    rec = best_t.strftime("%H:%M")
    note = ("jam berangkat yang direncanakan sudah yang terbaik" if rec == planned else
            f"berangkat pukul {rec} lebih baik daripada {planned} (biaya turun {base_cost - best_c:.0f})")
    return {"planned_start": planned, "recommended_start": rec, "cost_saving": round(base_cost - best_c, 1),
            "note": note}


def build_plan_out(db: sqlite3.Connection, plan_id: int) -> Dict[str, Any]:
    plan = _plan_row(db, plan_id)
    stops = _stops(db, plan_id)
    ctx = Context(db, plan)
    cost, rows, end = simulate(ctx, stops, detail=True)
    routing = sorted({r.pop("_routing") for r in rows}) or ["-"]
    return {
        "id": plan["id"], "user_id": plan["user_id"], "title": plan["title"], "date": plan["date"],
        "start_time": plan["start_time"], "origin": {"lat": plan["origin_lat"], "lon": plan["origin_lon"]},
        "options": plan["options"], "created_at": plan["created_at"], "updated_at": plan["updated_at"],
        "schedule": rows, "summary": _summary(cost, rows, end),
        "warnings": plan_warnings(ctx, rows, end),
        "departure": recommend_start(ctx, stops, cost),
        "suggestions": suggest_alternatives(ctx, stops, rows),
        "sources": {"routing": ",".join(routing), "weather": ctx.wx.source if ctx.wx else "tidak-tersedia"},
    }


# ---------- optimasi urutan & slot makan ----------

def best_order(ctx: Context, stops: List[Stop], start: Optional[datetime] = None,
               origin: Optional[LatLon] = None) -> List[Stop]:
    if len(stops) <= 1:
        return list(stops)
    cost = lambda o: simulate(ctx, o, start, origin)[0]  # noqa: E731
    if len(stops) <= 7:
        return list(min(itertools.permutations(stops), key=cost))
    order: List[Stop] = []
    rest = list(stops)
    while rest:  # greedy
        nxt = min(rest, key=lambda s: cost(order + [s]))
        order.append(nxt)
        rest.remove(nxt)
    best, improved = cost(order), True
    while improved:  # 2-opt
        improved = False
        for i in range(len(order) - 1):
            for j in range(i + 1, len(order)):
                cand = order[:i] + order[i:j + 1][::-1] + order[j + 1:]
                c = cost(cand)
                if c < best - 1e-6:
                    order, best, improved = cand, c, True
    return order


def _meal_candidates(ctx: Context, kind: str, prefs: Dict[str, Any], used: set,
                     anchors: List[LatLon]) -> List[Dict[str, Any]]:
    foods = MEALS[kind][3]
    cands = [p for p in list_places(ctx.db, category="kuliner",
                                    halal=True if prefs.get("halal_only") else None,
                                    price_max=prefs.get("price_max"))
             if p["id"] not in used and (p["food_type"] in foods or p["food_type"] is None)]
    # ambil yang paling dekat dengan rute supaya pencarian cepat
    cands.sort(key=lambda p: min(haversine_km((p["lat"], p["lon"]), a) for a in anchors))
    return cands[:8]


def insert_meals(ctx: Context, stops: List[Stop], kinds: List[str], prefs: Dict[str, Any],
                 start: Optional[datetime] = None, origin: Optional[LatLon] = None) -> List[Stop]:
    """Sisipkan slot makan pada posisi dan tempat yang menambah biaya paling kecil (= paling searah)."""
    stops = [s for s in stops if s["kind"] == "kunjungan" or s["kind"] not in kinds]
    for kind in kinds:
        if any(s["kind"] == kind for s in stops):
            continue
        used = {s["place_id"] for s in stops if s.get("place_id")}
        anchors = [origin or ctx.origin] + [_ll(ctx.place_of(s)) for s in stops]
        best: Optional[Tuple[float, List[Stop]]] = None
        for cand in _meal_candidates(ctx, kind, prefs, used, anchors):
            meal = {"place_id": cand["id"], "ext_ref": None, "ext_snapshot": None, "kind": kind, "locked_time": None,
                    "duration_minutes": min(MEALS[kind][2], cand["avg_visit_minutes"])}
            for pos in range(len(stops) + 1):
                trial = stops[:pos] + [meal] + stops[pos:]
                c = simulate(ctx, trial, start, origin)[0]
                if best is None or c < best[0]:
                    best = (c, trial)
        if best:
            stops = best[1]
    return stops


# ---------- alternatif saat hujan / antre panjang ----------

WISATA = ("outdoor", "indoor", "landmark")


def suggest_alternatives(ctx: Context, stops: Sequence[Stop], rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    in_plan = {s["place_id"] for s in stops if s.get("place_id")}
    pool = list_places(ctx.db)
    for i, row in enumerate(rows):
        rain = any("hujan" in w for w in row["warnings"])
        crowded = any("antre panjang" in w for w in row["warnings"])
        closed = any("tutup" in w and "jam tutup" not in w for w in row["warnings"])
        if not (rain or crowded or closed):
            continue
        place = ctx.place_of(stops[i])
        prev = ctx.origin if i == 0 else _ll(ctx.place_of(stops[i - 1]))
        nxt = _ll(ctx.place_of(stops[i + 1])) if i + 1 < len(rows) else None
        here = _ll(place)
        base = haversine_km(prev, here) + (haversine_km(here, nxt) if nxt else 0)
        visit_at = at_time(ctx.day, row["start_visit_at"])
        alts = []
        for c in pool:
            if c["id"] in in_plan or not is_open_at(c, visit_at):
                continue
            same_group = (c["category"] in WISATA) == (place["category"] in WISATA)
            if not same_group:
                continue
            if rain and not c["rain_friendly"]:
                continue
            if rain and place["category"] in WISATA and c["category"] == "outdoor":
                continue
            if (crowded or closed) and not rain and c["category"] != place["category"]:
                continue
            ll = _ll(c)
            detour = haversine_km(prev, ll) + (haversine_km(ll, nxt) if nxt else 0) - base
            if detour <= 10:
                alts.append({"place_id": c["id"], "name": c["name"], "category": c["category"],
                             "detour_km": round(detour, 1)})
        alts.sort(key=lambda a: a["detour_km"])
        out.append({"item_id": row["item_id"], "place_id": place["id"], "external_ref": place.get("external_ref"),
                    "place_name": place["name"],
                    "reason": "tutup" if closed else "hujan" if rain else "antre_panjang",
                    "alternatives": alts[:3]})
    return out


def _ll(p: Dict[str, Any]) -> LatLon:
    return (p["lat"], p["lon"])


# ---------- susun ulang ----------

def reorder(db: sqlite3.Connection, plan_id: int, strategy: str, manual: Optional[List[int]],
            from_time: Optional[str], apply_alternatives: bool = False) -> Dict[str, Any]:
    plan = _plan_row(db, plan_id)
    before = build_plan_out(db, plan_id)
    stops = _stops(db, plan_id)
    ids = [s["id"] for s in stops]
    replaced: List[str] = []

    if apply_alternatives:
        by_item = {s["item_id"]: s for s in before["suggestions"] if s["alternatives"]}
        for s in stops:
            sug = by_item.get(s["id"])
            if sug:
                alt = sug["alternatives"][0]
                s["place_id"], s["ext_ref"], s["ext_snapshot"] = alt["place_id"], None, None
                s["duration_minutes"] = get_place(db, alt["place_id"])["avg_visit_minutes"]
                why = {"hujan": "hujan", "antre_panjang": "antre panjang", "tutup": "tutup"}[sug["reason"]]
                replaced.append(f"{sug['place_name']} diganti {alt['name']} karena {why} "
                                f"(memutar {alt['detour_km']} km)")

    if strategy == "manual":
        if not manual or sorted(manual) != sorted(ids):
            raise PlanError("order harus berisi semua item_id rencana ini tepat satu kali", 422)
        by_id = {s["id"]: s for s in stops}
        new_stops = [by_id[i] for i in manual]
    else:
        ctx = Context(db, plan, use_network=False)  # cepat: tanpa OSRM saat mencoba banyak urutan
        locked_prefix: List[Stop] = []
        start, origin = None, None
        if from_time:
            # yang sudah selesai sebelum from_time dikunci; sisanya disusun ulang dari lokasi terakhir
            cut = at_time(ctx.day, from_time)
            for row, s in zip(before["schedule"], stops):
                if at_time(ctx.day, row["depart_at"]) <= cut:
                    locked_prefix.append(s)
                else:
                    break
            if locked_prefix:
                origin = _ll(ctx.place_of(locked_prefix[-1]))
            start = cut
        rest = stops[len(locked_prefix):]
        done_meals = {s["kind"] for s in locked_prefix}
        kinds = [k for k in _meal_kinds(plan["options"]) if k not in done_meals]
        visits = [s for s in rest if s["kind"] == "kunjungan"]
        kept_meals = [s for s in rest if s["kind"] != "kunjungan" and s["kind"] not in kinds]
        ordered = best_order(ctx, visits + kept_meals, start, origin)
        new_stops = locked_prefix + insert_meals(ctx, ordered, kinds, plan["options"], start, origin)

    sig = lambda ss: [(s.get("id"), s.get("place_id"), s.get("ext_ref")) for s in ss]  # noqa: E731
    changed = sig(new_stops) != sig(_stops(db, plan_id))
    if changed:
        _save_stops(db, plan_id, new_stops)
        db.execute("UPDATE plans SET updated_at = ? WHERE id = ?", (iso_utc(utcnow()), plan_id))
        _event(db, plan, "disusun_ulang")
        db.commit()
    after = build_plan_out(db, plan_id)
    reasons = replaced + (_reasons(before, after) if changed else ["urutan sekarang sudah yang terbaik menurut model"])
    return {**after, "before": before["summary"], "changed": changed, "reasons": reasons}


def _reasons(before: Dict[str, Any], after: Dict[str, Any]) -> List[str]:
    b, a = before["summary"], after["summary"]
    out = []
    dt = b["total_travel_minutes"] - a["total_travel_minutes"]
    if abs(dt) >= 1:
        out.append(f"total perjalanan {'berkurang' if dt > 0 else 'bertambah'} {abs(dt):.0f} menit")
    dw = b["warning_count"] - a["warning_count"]
    if dw > 0:
        out.append(f"peringatan berkurang {dw} (tutup/ramai/hujan/jam kunci)")
    rain_before = {r["place_id"] for r in before["schedule"] if any("hujan" in w for w in r["warnings"])}
    for r in after["schedule"]:
        if r["place_id"] in rain_before and not any("hujan" in w for w in r["warnings"]):
            out.append(f"{r['place_name']} dipindah ke {r['start_visit_at']} untuk menghindari hujan")
    out.append(f"selesai pukul {a['end_at']} (sebelumnya {b['end_at']})")
    return out


# ---------- prediksi kedatangan dari itinerary tersimpan ----------

def planned_arrivals(db: sqlite3.Connection, place_id: int, day: date) -> Dict[int, int]:
    """Jumlah kedatangan per jam ke sebuah tempat, dihitung dari itinerary yang disimpan pengguna."""
    counts: Dict[int, int] = {}
    plan_ids = [r[0] for r in db.execute(
        "SELECT DISTINCT p.id FROM plans p JOIN plan_items i ON i.plan_id = p.id"
        " WHERE p.date = ? AND i.place_id = ?", (day.isoformat(), place_id))]
    for pid in plan_ids:
        plan = _plan_row(db, pid)
        ctx = Context(db, plan, use_network=False, fetch_weather=False)
        _, rows, _ = simulate(ctx, _stops(db, pid), detail=True)
        for r in rows:
            if r["place_id"] == place_id:
                h = int(r["start_visit_at"][:2])
                counts[h] = counts.get(h, 0) + 1
    return counts


def visit_forecast(db: sqlite3.Connection, place: Dict[str, Any], day: date) -> Dict[str, Any]:
    """Prediksi kepadatan kunjungan per jam (Open Host Service untuk kelompok lain)."""
    arrivals = planned_arrivals(db, place["id"], day)
    hours = []
    for h in range(24):
        t = datetime(day.year, day.month, day.day, h, 30, tzinfo=WIB)
        if not is_open_at(place, t):
            continue
        n = arrivals.get(h, 0)
        base = estimate_level(place, t)
        level = min(5, base + (1 if n >= 3 else 0) + (1 if n >= 8 else 0))
        hours.append({"hour": min_to_hhmm(h * 60), "planned_arrivals": n, "level": level,
                      "label": LABELS[level], "queue_status": queue_status(level)})
    busiest = max(hours, key=lambda x: (x["level"], x["planned_arrivals"]), default=None)
    return {"place_id": place["id"], "place_name": place["name"], "date": day.isoformat(),
            "total_planned_arrivals": sum(arrivals.values()), "hours": hours,
            "busiest_hour": busiest["hour"] if busiest else None}
