"""Endpoint publik untuk kelompok lain. Semua wajib header X-API-Key.

Kontrak di sini dijaga stabil: perubahan internal konteks lain tidak boleh mengubah bentuk respons.
"""
import sqlite3
from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from ..common import HHMM_PATTERN
from ..crowd.schemas import CrowdStatusOut
from ..crowd.service import crowd_status
from ..db import get_db
from ..identity.deps import require_api_key
from ..places import service as places
from ..events import list_events
from ..places.schemas import Category, FoodType, PlaceOut
from ..planning import router as plan
from ..planning.schemas import EatNowOut, VisitForecast
from ..prediction import router as pred
from ..prediction.schemas import CorridorOut, DepartureWindowOut, TravelPrediction

router = APIRouter(prefix="/api/public", tags=["Public (X-API-Key)"], dependencies=[Depends(require_api_key)])


@router.get("/places", response_model=List[PlaceOut], summary="Daftar tempat")
def list_places(
    category: Optional[Category] = None,
    rain_friendly: Optional[bool] = None,
    halal: Optional[bool] = None,
    q: Optional[str] = Query(None, max_length=60),
    food_type: Optional[FoodType] = None,
    price_max: Optional[int] = Query(None, ge=1, le=4),
    open_late: Optional[bool] = None,
    open_now: Optional[bool] = None,
    db: sqlite3.Connection = Depends(get_db),
):
    return places.list_places(db, category, rain_friendly, halal, q, None, None, food_type, price_max,
                              open_late, open_now)


@router.get("/places/{place_id}", response_model=PlaceOut, summary="Detail tempat")
def get_place(place_id: int, db: sqlite3.Connection = Depends(get_db)):
    p = places.get_place(db, place_id)
    if not p:
        raise HTTPException(404, "tempat tidak ditemukan")
    return p


@router.get("/places/{place_id}/crowd", response_model=CrowdStatusOut, summary="Status keramaian tempat")
def get_crowd(place_id: int, db: sqlite3.Connection = Depends(get_db)):
    p = places.get_place(db, place_id)
    if not p:
        raise HTTPException(404, "tempat tidak ditemukan")
    return crowd_status(db, p)


@router.get("/corridors", response_model=List[CorridorOut], summary="Daftar koridor")
def list_corridors(db: sqlite3.Connection = Depends(get_db)):
    return pred.corridor_list(db)


@router.get("/predict/travel-time", response_model=TravelPrediction, summary="Prediksi waktu tempuh")
def travel_time(
    pts: pred.PointParams = Depends(),
    depart_at: Optional[datetime] = Query(None, description="ISO 8601, tanpa zona = WIB"),
    db: sqlite3.Connection = Depends(get_db),
):
    return pred.travel_time(pts, depart_at, db)


@router.get("/predict/departure-window", response_model=DepartureWindowOut, summary="Jendela berangkat terbaik")
def departure_window(
    pts: pred.PointParams = Depends(),
    date: Optional[date] = Query(None),
    earliest: str = Query("06:00", pattern=HHMM_PATTERN),
    latest: str = Query("12:00", pattern=HHMM_PATTERN),
    step: int = Query(15, ge=5, le=60),
    arrive_by: Optional[str] = Query(None, pattern=HHMM_PATTERN),
    db: sqlite3.Connection = Depends(get_db),
):
    return pred.window(pts, date, earliest, latest, step, arrive_by, db)


@router.get("/places/{place_id}/visit-forecast", response_model=VisitForecast,
            summary="Prediksi kepadatan kunjungan per jam (Open Host Service)")
def visit_forecast(place_id: int, date: Optional[date] = Query(None), db: sqlite3.Connection = Depends(get_db)):
    return plan.forecast_for(place_id, date, db)


@router.get("/eat-now", response_model=EatNowOut, summary='Tempat makan terdekat yang tidak macet dan tidak antre')
def eat_now(
    lat: float = Query(...),
    lon: float = Query(...),
    at: Optional[datetime] = Query(None),
    radius_km: float = Query(5.0, gt=0, le=30),
    price_max: Optional[int] = Query(None, ge=1, le=4),
    halal: Optional[bool] = None,
    food_type: Optional[FoodType] = None,
    open_late: Optional[bool] = None,
    include_long_queue: bool = False,
    limit: int = Query(10, ge=1, le=30),
    db: sqlite3.Connection = Depends(get_db),
):
    return plan.eat_now_query(lat, lon, at, radius_km, price_max, halal, food_type, open_late,
                              include_long_queue, limit, db)


@router.get("/events", summary="Domain event (Published Language): TempatDiperbarui, StatusAntreanBerubah")
def events(after: int = Query(0, ge=0, description="ambil event dengan id > after"),
           limit: int = Query(100, ge=1, le=500), db: sqlite3.Connection = Depends(get_db)):
    # RencanaBerubah memuat user_id, jadi tidak dibuka ke kelompok lain
    return list_events(db, after, ["TempatDiperbarui", "StatusAntreanBerubah"], limit)

