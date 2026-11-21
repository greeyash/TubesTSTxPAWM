"""Tes fitur sesuai makalah (PRD) Kelompok Bebas."""
from datetime import date

from app.adapters.weather import HourlyWeather
from app.planning import service as planning_service

SAT = "2026-11-28"
BRAGA_ORIGIN = {"lat": -6.9175, "lon": 107.6191}


def _ids(client):
    return {p["slug"]: p["id"] for p in client.get("/api/places").json()}


def test_catalog_food_filters(client, admin):
    halal_cheap = client.get("/api/places", params={"category": "kuliner", "halal": True, "price_max": 1}).json()
    assert halal_cheap and all(p["halal"] and (p["price_level"] or 1) <= 1 for p in halal_cheap)
    late = client.get("/api/places", params={"open_late": True}).json()
    assert late and all(p["open_late"] for p in late)
    jaj = client.get("/api/places", params={"food_type": "jajanan"}).json()
    assert jaj and all(p["food_type"] == "jajanan" for p in jaj)
    cihapit = client.get(f"/api/places/{_ids(client)['pasar-cihapit']}").json()
    assert cihapit["signature_menu"] and cihapit["parking"]["vehicle"] == "motor"
    assert cihapit["peak_hint"].startswith("ramai pukul") and "disarankan datang" in cihapit["peak_hint"]
    bad = {"name": "Museum X", "category": "indoor", "lat": -6.9, "lon": 107.6, "open_time": "08:00",
           "close_time": "16:00", "food_type": "kafe"}
    assert client.post("/api/places", json=bad, headers=admin).status_code == 422


def test_zones(client):
    ids = _ids(client)
    assert client.get(f"/api/places/{ids['farmhouse-susu-lembang']}").json()["zone"] == "utara"
    assert client.get(f"/api/places/{ids['kawah-putih']}").json()["zone"] == "selatan"
    assert client.get(f"/api/places/{ids['gedung-sate']}").json()["zone"] == "kota"


def test_queue_status_and_events(client, admin, manager):
    pid = _ids(client)["kuliner-burangrang"]
    p = client.get(f"/api/places/{pid}").json()
    r = client.post(f"/api/places/{pid}/crowd-reports", json={"level": 5, "lat": p["lat"], "lon": p["lon"]}, headers=admin)
    assert r.status_code == 201
    st = client.get(f"/api/places/{pid}/crowd").json()
    assert st["queue_status"] in ("sedang", "antre_panjang")
    events = client.get("/api/events", params={"type": "StatusAntreanBerubah"}, headers=admin).json()
    assert any(e["payload"]["place_id"] == pid for e in events)
    client.patch(f"/api/places/{pid}", json={"signature_menu": ["mie kocok"]}, headers=admin)
    events = client.get("/api/events", params={"type": "TempatDiperbarui"}, headers=admin).json()
    assert any(e["aggregate_id"] == pid and "signature_menu" in e["payload"]["fields"] for e in events)
    assert client.get("/api/events", headers=manager).status_code == 403


def test_travel_confidence(client, tourist):
    d = client.get("/api/predict/travel-time", headers=tourist,
                   params={"from_place_id": 1, "to_place_id": 2, "depart_at": f"{SAT}T10:00:00"}).json()
    assert d["confidence"]["level"] in ("rendah", "sedang")  # tanpa OSRM & cuaca
    assert "jarak memakai cadangan garis lurus" in d["confidence"]["reasons"]


def test_meal_slot_inserted_along_route(client, tourist):
    ids = _ids(client)
    body = {"date": SAT, "start_time": "08:00", "origin": BRAGA_ORIGIN,
            "items": [{"place_id": ids["farmhouse-susu-lembang"]}, {"place_id": ids["floating-market-lembang"]},
                      {"place_id": ids["observatorium-bosscha"], "duration_minutes": 60}],
            "options": {"insert_lunch": True, "halal_only": True}}
    r = client.post("/api/plans", json=body, headers=tourist)
    assert r.status_code == 201, r.text
    meals = [s for s in r.json()["schedule"] if s["kind"] == "makan_siang"]
    assert len(meals) == 1
    meal = meals[0]
    assert meal["zone"] == "utara", meal  # searah: tidak putar balik ke kota
    assert "11:00" <= meal["start_visit_at"] <= "13:30"
    assert not any("slot" in w for w in meal["warnings"])


def test_lock_time(client, tourist):
    ids = _ids(client)
    body = {"date": SAT, "start_time": "08:00", "origin": BRAGA_ORIGIN, "optimize": True,
            "items": [{"place_id": ids["museum-geologi"], "locked_time": "13:00"},
                      {"place_id": ids["gedung-sate"]}, {"place_id": ids["jalan-braga"]}]}
    plan = client.post("/api/plans", json=body, headers=tourist).json()
    geo = next(s for s in plan["schedule"] if s["place_id"] == ids["museum-geologi"])
    assert geo["start_visit_at"] == "13:00" and geo["locked_time"] == "13:00"
    assert not any("terlambat" in w for w in geo["warnings"])
    assert plan["departure"]["recommended_start"]


def test_closed_place_gets_alternative(client, tourist):
    ids = _ids(client)  # Bosscha tutup Senin & Minggu
    body = {"date": "2026-11-29", "start_time": "09:00", "origin": BRAGA_ORIGIN,
            "items": [{"place_id": ids["observatorium-bosscha"]}]}
    plan = client.post("/api/plans", json=body, headers=tourist).json()
    sug = plan["suggestions"]
    assert sug and sug[0]["reason"] == "tutup" and sug[0]["alternatives"]


def test_north_south_warning(client, tourist):
    ids = _ids(client)
    body = {"date": SAT, "origin": BRAGA_ORIGIN,
            "items": [{"place_id": ids["farmhouse-susu-lembang"]}, {"place_id": ids["kawah-putih"]}]}
    plan = client.post("/api/plans", json=body, headers=tourist).json()
    assert any("tidak realistis" in w for w in plan["warnings"])


def test_rain_alternative(client, tourist, monkeypatch):
    rain = HourlyWeather(day=date(2026, 11, 28), precipitation_mm=tuple([8.0] * 24),
                         precipitation_probability=tuple([95] * 24))
    monkeypatch.setattr(planning_service.weather, "hourly", lambda point, day: rain if day == rain.day else None)
    ids = _ids(client)
    body = {"date": SAT, "start_time": "09:00", "origin": BRAGA_ORIGIN,
            "items": [{"place_id": ids["babakan-siliwangi"]}, {"place_id": ids["museum-geologi"]}]}
    plan = client.post("/api/plans", json=body, headers=tourist).json()
    sug = [s for s in plan["suggestions"] if s["place_id"] == ids["babakan-siliwangi"]]
    assert sug and sug[0]["reason"] == "hujan" and sug[0]["alternatives"]
    assert all(a["category"] in ("indoor", "landmark") for a in sug[0]["alternatives"])
    out = client.post(f"/api/plans/{plan['id']}/reorder", json={"apply_alternatives": True}, headers=tourist).json()
    assert ids["babakan-siliwangi"] not in [s["place_id"] for s in out["schedule"]]
    assert any("diganti" in r for r in out["reasons"])


def test_eat_now(client, tourist, admin):
    params = {"lat": -6.9050, "lon": 107.6250, "at": f"{SAT}T12:00:00", "radius_km": 4}
    d = client.get("/api/eat-now", params=params, headers=tourist).json()
    assert d["results"]
    scores = [r["score"] for r in d["results"]]
    assert scores == sorted(scores)
    # yang tampil dengan antre panjang hanya yang berasal dari perkiraan jam ramai, bukan laporan
    assert all(r["crowd_source"] == "perkiraan" for r in d["results"] if r["queue_status"] == "antre_panjang")
    # tempat yang dilaporkan antre panjang disembunyikan (tempat 24 jam supaya tes tidak bergantung jam)
    w = client.post("/api/places", headers=admin, json={
        "name": "Warung 24 Jam Uji", "category": "kuliner", "food_type": "makanan_berat", "lat": -6.9052,
        "lon": 107.6252, "open_time": "00:00", "close_time": "23:59"}).json()
    for i in range(3):
        e = f"antre{i}@test.local"
        client.post("/api/auth/register", json={"email": e, "name": "Antre", "password": "pw-12345"})
        tok = client.post("/api/auth/login", json={"email": e, "password": "pw-12345"}).json()["access_token"]
        client.post(f"/api/places/{w['id']}/crowd-reports", json={"level": 5, "lat": w["lat"], "lon": w["lon"]},
                    headers={"Authorization": f"Bearer {tok}"})
    now = {"lat": -6.9050, "lon": 107.6250, "radius_km": 4}
    d2 = client.get("/api/eat-now", params=now, headers=tourist).json()
    assert w["id"] not in [r["place_id"] for r in d2["results"]] and d2["skipped_long_queue"] >= 1
    d3 = client.get("/api/eat-now", params=dict(now, include_long_queue=True), headers=tourist).json()
    assert w["id"] in [r["place_id"] for r in d3["results"]]
    halal = client.get("/api/eat-now", params=dict(params, halal=True), headers=tourist).json()
    assert all(r["halal"] for r in halal["results"])


def test_visit_forecast_and_dashboard(client, tourist, manager, admin):
    ids = _ids(client)
    pid = ids["museum-sri-baduga"]
    body = {"date": SAT, "start_time": "09:00", "origin": BRAGA_ORIGIN, "items": [{"place_id": pid}]}
    client.post("/api/plans", json=body, headers=tourist)
    f = client.get(f"/api/places/{pid}/visit-forecast", params={"date": SAT}).json()
    assert f["total_planned_arrivals"] >= 1 and any(h["planned_arrivals"] for h in f["hours"])
    assert client.get(f"/api/places/{pid}/dashboard", headers=manager).status_code == 403
    me = client.get("/api/auth/me", headers=manager).json()
    client.patch(f"/api/places/{pid}", json={"manager_id": me["id"]}, headers=admin)
    d = client.get(f"/api/places/{pid}/dashboard", params={"date": SAT}, headers=manager).json()
    assert d["forecast"]["total_planned_arrivals"] >= 1 and "reports_today" in d


def test_public_new_endpoints(client, admin):
    key = client.post("/api/admin/api-keys", json={"client_name": "K05"}, headers=admin).json()["api_key"]
    h = {"X-API-Key": key}
    assert client.get("/api/public/places/1/visit-forecast", headers=h).status_code == 200
    assert client.get("/api/public/eat-now", params={"lat": -6.9, "lon": 107.62}, headers=h).status_code == 200
    ev = client.get("/api/public/feed", headers=h).json()
    assert all(e["type"] != "RencanaBerubah" for e in ev["events"])
