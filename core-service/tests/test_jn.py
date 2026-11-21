"""Tes kesiapan integrasi dengan ekosistem Jelajah Nusantara."""
from datetime import datetime, timedelta, timezone

SAT = "2026-11-28"
ORIGIN = {"lat": -6.9175, "lon": 107.6191}
CURUG = {"destination_id": "dst_12", "name": "Curug Uji", "lat": -6.8350, "lon": 107.6620,
         "opening_hours": "07:00-16:00", "category": "curug", "captured_at": "2026-11-20T08:00:00Z"}


def test_plan_with_k1_snapshot(client, tourist):
    body = {"date": SAT, "start_time": "08:00", "origin": ORIGIN, "optimize": True,
            "items": [{"external": CURUG}, {"place_id": 1}]}
    r = client.post("/api/plans", json=body, headers=tourist)
    assert r.status_code == 201, r.text
    plan = r.json()
    ext = next(s for s in plan["schedule"] if s["external_ref"] == "dst_12")
    assert ext["place_id"] is None and ext["category"] == "outdoor" and ext["duration_minutes"] == 120
    assert ext["place_name"] == "Curug Uji" and ext["travel_minutes"] > 0
    # tersimpan dan terbaca ulang
    again = client.get(f"/api/plans/{plan['id']}", headers=tourist).json()
    assert any(s["external_ref"] == "dst_12" for s in again["schedule"])
    # susun ulang manual tetap bekerja dengan item eksternal
    order = [s["item_id"] for s in again["schedule"]][::-1]
    out = client.post(f"/api/plans/{plan['id']}/reorder", json={"strategy": "manual", "order": order}, headers=tourist)
    assert [s["item_id"] for s in out.json()["schedule"]] == order


def test_snapshot_validation_and_staleness(client, tourist):
    both = {"date": SAT, "origin": ORIGIN, "items": [{"place_id": 1, "external": CURUG}]}
    r = client.post("/api/plans", json=both, headers=tourist)
    assert r.status_code == 422 and r.json()["error"] == "VALIDATION_ERROR"
    bad_hours = {"date": SAT, "origin": ORIGIN, "items": [{"external": dict(CURUG, opening_hours="pagi")}]}
    assert client.post("/api/plans", json=bad_hours, headers=tourist).status_code == 422
    outside = {"date": SAT, "origin": ORIGIN, "items": [{"external": dict(CURUG, lat=40.0)}]}
    assert client.post("/api/plans", json=outside, headers=tourist).status_code == 422
    old = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    plan = client.post("/api/plans", headers=tourist, json={
        "date": SAT, "origin": ORIGIN, "items": [{"external": dict(CURUG, captured_at=old)}]}).json()
    assert any("perlu disegarkan" in w for w in plan["schedule"][0]["warnings"])


def test_batch_endpoints(client, admin):
    r = client.get("/api/crowd", params={"place_ids": "1,2,9999"}).json()
    assert [d["place_id"] for d in r["data"]] == [1, 2] and r["missing_ids"] == [9999]
    f = client.get("/api/visit-forecast", params={"place_ids": "1,3", "date": SAT}).json()
    assert len(f["data"]) == 2 and f["date"] == SAT
    bad = client.get("/api/crowd", params={"place_ids": "a,b"})
    assert bad.status_code == 422 and bad.json()["error"] == "VALIDATION_ERROR"
    key = client.post("/api/admin/api-keys", json={"client_name": "jn-rute"}, headers=admin).json()["api_key"]
    h = {"X-API-Key": key}
    assert len(client.get("/api/public/crowd", params={"ids": "1,2"}, headers=h).json()["data"]) == 2
    assert client.get("/api/public/visit-forecast", params={"ids": "1"}, headers=h).status_code == 200


def test_error_format(client):
    r = client.get("/api/places/99999")
    assert r.status_code == 404 and r.json() == {"error": "NOT_FOUND", "message": "tempat tidak ditemukan"}
    r = client.get("/api/auth/me")
    assert r.status_code == 401 and r.json()["error"] == "UNAUTHORIZED"


def test_feed_format(client, admin):
    client.patch("/api/places/5", json={"ticket_price": 26000}, headers=admin)
    f = client.get("/api/feed", params={"since": 0}).json()
    assert f["events"] and set(f["events"][0]) == {"seq", "type", "occurred_at", "data"}
    assert all(e["type"] in ("TempatDiperbarui", "StatusAntreanBerubah") for e in f["events"])
    nxt = client.get("/api/feed", params={"since": f["next_since"]}).json()
    assert nxt["events"] == [] and nxt["next_since"] == f["next_since"]
