"""Adapter diuji dengan respons tiruan berbentuk sama dengan API aslinya (tanpa jaringan)."""
from datetime import date

import httpx

from app.adapters import osrm, weather
from app.config import settings


class _Resp:
    def __init__(self, data, status=200):
        self._data, self.status_code = data, status

    def json(self):
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("err", request=None, response=None)


def test_osrm_parses_and_backs_off(monkeypatch):
    monkeypatch.setattr(settings, "external_apis", True)
    monkeypatch.setattr(osrm, "_down_until", 0.0)
    osrm._cache.clear()
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _Resp(
        {"code": "Ok", "routes": [{"distance": 12481.1, "duration": 762.9}]}))
    r = osrm.route((-6.9025, 107.6188), (-6.8327, 107.6055))
    assert r and round(r.distance_km, 1) == 12.5 and round(r.duration_min, 1) == 12.7

    calls = []

    def boom(*a, **k):
        calls.append(1)
        raise httpx.ConnectError("down")

    monkeypatch.setattr(httpx, "get", boom)
    assert osrm.route((-6.9, 107.6), (-6.8, 107.5)) is None
    assert osrm.route((-6.91, 107.61), (-6.81, 107.51)) is None
    assert len(calls) == 1  # panggilan kedua dilewati circuit breaker
    monkeypatch.setattr(settings, "external_apis", False)


def test_weather_parses(monkeypatch):
    monkeypatch.setattr(settings, "external_apis", True)
    monkeypatch.setattr(weather, "_down_until", 0.0)
    weather._cache.clear()
    mm = [0.0] * 13 + [6.0] + [0.0] * 10
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _Resp(
        {"hourly": {"precipitation": mm, "precipitation_probability": [90] * 24}}))
    wx = weather.hourly((-6.9, 107.6), date(2026, 11, 28))
    assert wx and wx.at_hour(13) == (6.0, 90)
    monkeypatch.setattr(settings, "external_apis", False)
