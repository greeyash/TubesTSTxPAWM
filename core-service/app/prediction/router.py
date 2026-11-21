import sqlite3
from datetime import date, datetime
from typing import List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query

from ..common import HHMM_PATTERN, now_wib, to_wib
from ..db import get_db
from ..identity.deps import get_current_user
from ..places.service import get_place
from . import service
from .schemas import CorridorFactorsOut, CorridorOut, DepartureWindowOut, Endpoint, TravelPrediction

router = APIRouter(prefix="/api", tags=["Prediction"])


def resolve_point(db: sqlite3.Connection, lat: Optional[float], lon: Optional[float],
                  place_id: Optional[int], label: str) -> Tuple[Tuple[float, float], Endpoint]:
    if place_id is not None:
        p = get_place(db, place_id)
        if not p:
            raise HTTPException(404, f"{label}: tempat {place_id} tidak ditemukan")
        return (p["lat"], p["lon"]), Endpoint(lat=p["lat"], lon=p["lon"], name=p["name"])
    if lat is None or lon is None:
        raise HTTPException(422, f"{label}: isi {label}_place_id, atau {label}_lat dan {label}_lon")
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise HTTPException(422, f"{label}: koordinat tidak valid")
    return (lat, lon), Endpoint(lat=lat, lon=lon)


class PointParams:
    def __init__(
        self,
        from_place_id: Optional[int] = Query(None, description="ID tempat asal (atau pakai from_lat/from_lon)"),
        from_lat: Optional[float] = Query(None, examples=[-6.9025]),
        from_lon: Optional[float] = Query(None, examples=[107.6188]),
        to_place_id: Optional[int] = Query(None, description="ID tempat tujuan (atau pakai to_lat/to_lon)"),
        to_lat: Optional[float] = Query(None, examples=[-6.8117]),
        to_lon: Optional[float] = Query(None, examples=[107.6178]),
    ):
        self.from_place_id, self.from_lat, self.from_lon = from_place_id, from_lat, from_lon
        self.to_place_id, self.to_lat, self.to_lon = to_place_id, to_lat, to_lon

    def resolve(self, db: sqlite3.Connection):
        a, ea = resolve_point(db, self.from_lat, self.from_lon, self.from_place_id, "from")
        b, eb = resolve_point(db, self.to_lat, self.to_lon, self.to_place_id, "to")
        return a, ea, b, eb


def travel_time(pts: PointParams, depart_at: Optional[datetime], db: sqlite3.Connection):
    a, ea, b, eb = pts.resolve(db)
    out = service.predict_travel(db, a, b, to_wib(depart_at) if depart_at else now_wib())
    return {"origin": ea, "destination": eb, **out}


def window(pts: PointParams, day: Optional[date], earliest: str, latest: str, step: int,
           arrive_by: Optional[str], db: sqlite3.Connection):
    a, ea, b, eb = pts.resolve(db)
    try:
        out = service.departure_window(db, a, b, day or now_wib().date(), earliest, latest, step, arrive_by)
    except service.PredictionError as e:
        raise HTTPException(e.code, str(e))
    return {"origin": ea, "destination": eb, **out}


def corridor_list(db: sqlite3.Connection):
    return [service.corridor_out(c) for c in service.load_network(db).corridors]


def corridor_factors(slug: str, day: Optional[date], db: sqlite3.Connection):
    try:
        return service.corridor_factors(service.load_network(db), slug, day or now_wib().date())
    except service.PredictionError as e:
        raise HTTPException(e.code, str(e))


@router.get("/corridors", response_model=List[CorridorOut], summary="Daftar koridor dan tabel faktor jam")
def list_corridors(db: sqlite3.Connection = Depends(get_db)):
    return corridor_list(db)


@router.get("/corridors/{slug}/factors", response_model=CorridorFactorsOut,
            summary="Faktor jam satu koridor untuk tanggal tertentu")
def get_corridor_factors(slug: str, date: Optional[date] = Query(None, description="YYYY-MM-DD, default hari ini"),
                         db: sqlite3.Connection = Depends(get_db)):
    return corridor_factors(slug, date, db)


@router.get("/predict/travel-time", response_model=TravelPrediction, summary="Prediksi waktu tempuh",
            dependencies=[Depends(get_current_user)])
def predict_travel_time(
    pts: PointParams = Depends(),
    depart_at: Optional[datetime] = Query(None, description="ISO 8601, tanpa zona = WIB. Default sekarang.",
                                          examples=["2026-11-28T10:00:00"]),
    db: sqlite3.Connection = Depends(get_db),
):
    return travel_time(pts, depart_at, db)


@router.get("/predict/departure-window", response_model=DepartureWindowOut,
            summary="Jendela berangkat terbaik dalam rentang jam", dependencies=[Depends(get_current_user)])
def departure_window(
    pts: PointParams = Depends(),
    date: Optional[date] = Query(None, description="YYYY-MM-DD, default hari ini"),
    earliest: str = Query("06:00", pattern=HHMM_PATTERN),
    latest: str = Query("12:00", pattern=HHMM_PATTERN),
    step: int = Query(15, ge=5, le=60, description="jarak antarslot, menit"),
    arrive_by: Optional[str] = Query(None, pattern=HHMM_PATTERN, description="harus tiba sebelum jam ini"),
    db: sqlite3.Connection = Depends(get_db),
):
    return window(pts, date, earliest, latest, step, arrive_by, db)
