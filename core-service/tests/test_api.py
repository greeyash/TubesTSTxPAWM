def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_seed_loaded(client):
    assert len(client.get("/api/places").json()) >= 25
    assert len(client.get("/api/corridors").json()) >= 6


def test_register_rules(client):
    r = client.post("/api/auth/register", json={"email": "x@test.local", "name": "Xena", "password": "pw-12345", "role": "admin"})
    assert r.status_code == 422  # admin tidak bisa daftar sendiri
    client.post("/api/auth/register", json={"email": "dup@test.local", "name": "Dian", "password": "pw-12345"})
    r = client.post("/api/auth/register", json={"email": "DUP@test.local", "name": "Dian", "password": "pw-12345"})
    assert r.status_code == 409
    assert client.post("/api/auth/login", json={"email": "dup@test.local", "password": "salah-123"}).status_code == 401


def test_me_requires_token(client, tourist):
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me", headers=tourist).json()["role"] == "wisatawan"


def test_place_filters(client):
    rain = client.get("/api/places", params={"rain_friendly": True}).json()
    assert rain and all(p["rain_friendly"] for p in rain)
    kul = client.get("/api/places", params={"category": "kuliner"}).json()
    assert kul and all(p["category"] == "kuliner" for p in kul)


PLACE = {
    "name": "Kebun Uji", "category": "outdoor", "lat": -6.85, "lon": 107.62,
    "open_time": "08:00", "close_time": "17:00", "peak_hours": {"weekend": [["09:00", "11:00"]]},
    "parking": {"type": "terbatas", "capacity": 20},
}


def test_place_permissions(client, tourist, manager, admin):
    assert client.post("/api/places", json=PLACE, headers=tourist).status_code == 403
    r = client.post("/api/places", json=PLACE, headers=manager)
    assert r.status_code == 201, r.text
    place = r.json()
    assert place["manager_id"] is not None and place["slug"] == "kebun-uji"
    r = client.patch(f"/api/places/{place['id']}", json={"ticket_price": 15000}, headers=manager)
    assert r.status_code == 200 and r.json()["ticket_price"] == 15000
    # pengelola lain / tempat orang lain
    assert client.patch("/api/places/1", json={"ticket_price": 1}, headers=manager).status_code == 403
    assert client.patch("/api/places/1", json={"ticket_price": 1}, headers=admin).status_code == 200
    bad = dict(PLACE, open_time="25:00")
    assert client.post("/api/places", json=bad, headers=admin).status_code == 422


def test_crowd_reports_and_validation(client, tourist, manager, admin):
    place = client.get("/api/places/2").json()
    # lokasi jauh -> ditolak
    r = client.post("/api/places/2/crowd-reports", json={"level": 3, "lat": -6.0, "lon": 107.0}, headers=tourist)
    assert r.status_code == 201 and r.json()["status"] == "rejected"
    # cooldown
    r = client.post("/api/places/2/crowd-reports", json={"level": 3}, headers=tourist)
    assert r.status_code == 429
    # admin -> valid bobot 2
    r = client.post("/api/places/2/crowd-reports", json={"level": 5, "lat": place["lat"], "lon": place["lon"]}, headers=admin)
    assert r.json()["status"] == "valid" and r.json()["weight"] == 2.0
    s = client.get("/api/places/2/crowd").json()
    assert s["report_count"] == 1 and s["source"] in ("laporan", "campuran") and s["score"] > 1
    # moderasi oleh pengelola yang bukan pengelola tempat -> 403
    rid = r.json()["id"]
    assert client.patch(f"/api/crowd-reports/{rid}", json={"status": "rejected"}, headers=manager).status_code == 403
    assert client.patch(f"/api/crowd-reports/{rid}", json={"status": "rejected"}, headers=admin).json()["weight"] == 0


def test_crowd_outlier_flagged(client):
    heads = []
    for i in range(4):
        e = f"lap{i}@test.local"
        client.post("/api/auth/register", json={"email": e, "name": "Lapor", "password": "pw-12345"})
        tok = client.post("/api/auth/login", json={"email": e, "password": "pw-12345"}).json()["access_token"]
        heads.append({"Authorization": f"Bearer {tok}"})
    for h in heads[:3]:
        assert client.post("/api/places/3/crowd-reports", json={"level": 1}, headers=h).json()["status"] == "valid"
    assert client.post("/api/places/3/crowd-reports", json={"level": 5}, headers=heads[3]).json()["status"] == "flagged"


def test_travel_time_fallback(client, tourist):
    params = {"from_lat": -6.9025, "from_lon": 107.6188, "to_place_id": 1, "depart_at": "2026-11-28T10:00:00"}
    assert client.get("/api/predict/travel-time", params=params).status_code == 401
    r = client.get("/api/predict/travel-time", params=params, headers=tourist)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["sources"]["routing"] == "garis-lurus"
    assert d["predicted_minutes"] > d["free_flow_minutes"]  # Sabtu 10.00 macet
    assert any(c["slug"] == "setiabudi-lembang" for c in d["corridors"])
    early = client.get("/api/predict/travel-time", headers=tourist,
                       params=dict(params, depart_at="2026-11-28T05:00:00")).json()
    assert early["predicted_minutes"] < d["predicted_minutes"]


def test_corridor_factor_example(client):
    d = client.get("/api/corridors/setiabudi-lembang/factors", params={"date": "2026-11-28"}).json()
    f = {h["hour"]: h["factor"] for h in d["hours"]}
    assert d["day_type"] == "weekend"
    assert (f["06:00"], f["08:00"], f["10:00"], f["13:00"], f["16:00"]) == (1.0, 1.4, 1.8, 1.5, 1.9)


def test_departure_window(client, tourist):
    params = {"from_lat": -6.9025, "from_lon": 107.6188, "to_place_id": 1, "date": "2026-11-28",
              "earliest": "05:00", "latest": "12:00"}
    d = client.get("/api/predict/departure-window", params=params, headers=tourist).json()
    assert d["best"]["depart_at"] <= "07:00"
    assert d["recommended_window"]["start"] <= d["best"]["depart_at"] <= d["recommended_window"]["end"]
    assert d["avoid"]
    d2 = client.get("/api/predict/departure-window", headers=tourist,
                    params=dict(params, earliest="06:00", latest="10:00", arrive_by="08:30")).json()
    assert d2["best"]["on_time"] is True


def test_plan_lifecycle(client, tourist, admin):
    body = {
        "date": "2026-11-28", "start_time": "08:00", "origin": {"lat": -6.9175, "lon": 107.6191},
        # Braga Culinary Night (buka 17.00) sengaja ditaruh pertama
        "items": [{"place_id": pid} for pid in _ids(client, ["braga-culinary-night", "museum-geologi", "tebing-keraton"])],
    }
    r = client.post("/api/plans", json=body, headers=tourist)
    assert r.status_code == 201, r.text
    plan = r.json()
    assert plan["schedule"][0]["warnings"]
    r = client.post(f"/api/plans/{plan['id']}/reorder", json={"strategy": "optimize"}, headers=tourist)
    out = r.json()
    assert out["changed"] and out["summary"]["score"] < out["before"]["score"]
    assert out["schedule"][-1]["place_name"] == "Braga Culinary Night"
    ids = [s["item_id"] for s in out["schedule"]][::-1]
    r = client.post(f"/api/plans/{plan['id']}/reorder", json={"strategy": "manual", "order": ids}, headers=tourist)
    assert [s["item_id"] for s in r.json()["schedule"]] == ids
    r = client.patch(f"/api/plans/{plan['id']}", json={"start_time": "07:00", "title": "Sabtu"}, headers=tourist)
    assert r.json()["title"] == "Sabtu"
    assert len(client.get("/api/plans", headers=tourist).json()) == 1
    # orang lain tidak bisa melihat
    other = client.post("/api/auth/login", json={"email": "dup@test.local", "password": "pw-12345"}).json()["access_token"]
    assert client.get(f"/api/plans/{plan['id']}", headers={"Authorization": f"Bearer {other}"}).status_code == 403
    assert client.get(f"/api/plans/{plan['id']}", headers=admin).status_code == 200
    assert client.delete(f"/api/plans/{plan['id']}", headers=tourist).status_code == 204


def test_public_api_key(client, admin, tourist):
    assert client.get("/api/public/places").status_code == 401
    assert client.post("/api/admin/api-keys", json={"client_name": "K03"}, headers=tourist).status_code == 403
    r = client.post("/api/admin/api-keys", json={"client_name": "K03"}, headers=admin)
    key = r.json()["api_key"]
    h = {"X-API-Key": key}
    page = client.get("/api/public/places", headers=h).json()
    assert page["total"] >= 25 and page["page"] == 1 and len(page["data"]) == 20
    assert client.get("/api/public/places/1/crowd", headers=h).status_code == 200
    r = client.get("/api/public/predict/travel-time", headers=h, params={"from_place_id": 1, "to_place_id": 2})
    assert r.status_code == 200
    keys = client.get("/api/admin/api-keys", headers=admin).json()
    assert keys[0]["request_count"] == 3 and "api_key" not in keys[0]
    client.delete(f"/api/admin/api-keys/{keys[0]['id']}", headers=admin)
    assert client.get("/api/public/places", headers=h).status_code == 401


def _ids(client, slugs):
    by_slug = {p["slug"]: p["id"] for p in client.get("/api/places").json()}
    return [by_slug[s] for s in slugs]


def test_api_key_rate_limit(client, admin, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "api_key_rate_per_min", 2)
    key = client.post("/api/admin/api-keys", json={"client_name": "K-limit"}, headers=admin).json()["api_key"]
    h = {"X-API-Key": key}
    assert client.get("/api/public/corridors", headers=h).status_code == 200
    assert client.get("/api/public/corridors", headers=h).status_code == 200
    r = client.get("/api/public/corridors", headers=h)
    assert r.status_code == 429 and "Retry-After" in r.headers


def test_api_root(client):
    r = client.get("/api")
    assert r.status_code == 200 and r.json()["docs"] == "/docs"
