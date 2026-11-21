import sqlite3
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..common import iso_utc, now_wib, parse_id_list, to_wib
from ..crowd.service import crowd_status
from ..db import get_db
from ..identity.deps import User, get_current_user, require_manager
from ..places.schemas import FoodType
from ..places.service import can_manage, get_place
from . import recommend, service
from .schemas import (Dashboard, EatNowOut, PlanCreate, PlanListItem, PlanOut, PlanUpdate, ReorderIn, ReorderOut,
                      VisitForecast, VisitForecastBatch)

router = APIRouter(prefix="/api", tags=["Planning"])


def _call(fn, *args):
    try:
        return fn(*args)
    except service.PlanError as e:
        raise HTTPException(e.code, str(e))


@router.post("/plans", response_model=PlanOut, status_code=status.HTTP_201_CREATED,
             summary="Buat rencana satu hari (opsional sisipkan makan siang / jajan sore)")
def create_plan(body: PlanCreate, user: User = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)):
    data = body.model_dump()
    data["options"] = {k: v for k, v in data["options"].items() if v is not None}
    plan_id = _call(service.create_plan, db, user, data)
    return service.build_plan_out(db, plan_id)


@router.get("/plans", response_model=List[PlanListItem], summary="Daftar rencana milik saya")
def list_plans(user: User = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)):
    return service.list_plans(db, user)


@router.get("/plans/{plan_id}", response_model=PlanOut,
            summary="Lihat rencana: jadwal, peringatan, jam berangkat terbaik, dan alternatif")
def get_plan(plan_id: int, user: User = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)):
    _call(service.require_access, db, plan_id, user)
    return service.build_plan_out(db, plan_id)


@router.patch("/plans/{plan_id}", response_model=PlanOut,
              summary="Ubah rencana (judul, tanggal, jam mulai, asal, daftar tempat, opsi slot makan)")
def update_plan(plan_id: int, body: PlanUpdate, user: User = Depends(get_current_user),
                db: sqlite3.Connection = Depends(get_db)):
    _call(service.require_access, db, plan_id, user)
    _call(service.update_plan, db, plan_id, body.model_dump(exclude_unset=True))
    return service.build_plan_out(db, plan_id)


@router.post("/plans/{plan_id}/reorder", response_model=ReorderOut,
             summary="Susun ulang urutan kunjungan (opsional ganti tempat yang kehujanan/antre panjang)")
def reorder(plan_id: int, body: ReorderIn, user: User = Depends(get_current_user),
            db: sqlite3.Connection = Depends(get_db)):
    _call(service.require_access, db, plan_id, user)
    return _call(service.reorder, db, plan_id, body.strategy, body.order, body.from_time, body.apply_alternatives)


@router.delete("/plans/{plan_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Hapus rencana")
def delete_plan(plan_id: int, user: User = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)):
    _call(service.require_access, db, plan_id, user)
    service.delete_plan(db, plan_id)


def eat_now_query(lat: float, lon: float, at: Optional[datetime], radius_km: float, price_max: Optional[int],
                  halal: Optional[bool], food_type: Optional[str], open_late: Optional[bool],
                  include_long_queue: bool, limit: int, db: sqlite3.Connection):
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise HTTPException(422, "koordinat tidak valid")
    return recommend.eat_now(db, (lat, lon), to_wib(at) if at else now_wib(), radius_km, price_max, halal,
                             food_type, open_late, include_long_queue, limit)


@router.get("/eat-now", response_model=EatNowOut, summary='Mode "Mau makan sekarang"')
def eat_now(
    lat: float = Query(..., examples=[-6.9175]),
    lon: float = Query(..., examples=[107.6191]),
    at: Optional[datetime] = Query(None, description="default sekarang; tanpa zona = WIB"),
    radius_km: float = Query(5.0, gt=0, le=30),
    price_max: Optional[int] = Query(None, ge=1, le=4),
    halal: Optional[bool] = None,
    food_type: Optional[FoodType] = None,
    open_late: Optional[bool] = Query(None, description="hanya yang buka malam"),
    include_long_queue: bool = Query(False, description="tampilkan juga yang antre panjang"),
    limit: int = Query(10, ge=1, le=30),
    _: User = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    return eat_now_query(lat, lon, at, radius_km, price_max, halal, food_type, open_late, include_long_queue, limit, db)


def forecast_for(place_id: int, day: Optional[date], db: sqlite3.Connection):
    p = get_place(db, place_id)
    if not p:
        raise HTTPException(404, "tempat tidak ditemukan")
    return service.visit_forecast(db, p, day or now_wib().date())


def forecast_batch(raw_ids: str, day: Optional[date], db: sqlite3.Connection):
    try:
        ids = parse_id_list(raw_ids, max_items=20)
    except ValueError as e:
        raise HTTPException(422, str(e))
    d = day or now_wib().date()
    data, missing = [], []
    for pid in ids:
        p = get_place(db, pid)
        if p:
            data.append(service.visit_forecast(db, p, d))
        else:
            missing.append(pid)
    return {"date": d.isoformat(), "data": data, "missing_ids": missing}


@router.get("/visit-forecast", response_model=VisitForecastBatch,
            summary="Prediksi kepadatan kunjungan untuk banyak tempat sekaligus")
def visit_forecast_many(place_ids: str = Query(..., description="mis. 1,2,3 (maks 20)"),
                        date: Optional[date] = Query(None), db: sqlite3.Connection = Depends(get_db)):
    return forecast_batch(place_ids, date, db)


@router.get("/places/{place_id}/visit-forecast", response_model=VisitForecast,
            summary="Prediksi kepadatan kunjungan per jam (dari itinerary tersimpan + jam ramai)")
def visit_forecast(place_id: int, date: Optional[date] = Query(None, description="YYYY-MM-DD, default hari ini"),
                   db: sqlite3.Connection = Depends(get_db)):
    return forecast_for(place_id, date, db)


@router.get("/places/{place_id}/dashboard", response_model=Dashboard,
            summary="Dashboard pengelola: perkiraan kedatangan dan ringkasan laporan hari ini")
def dashboard(place_id: int, date: Optional[date] = Query(None), user: User = Depends(require_manager),
              db: sqlite3.Connection = Depends(get_db)):
    p = get_place(db, place_id)
    if not p:
        raise HTTPException(404, "tempat tidak ditemukan")
    if not can_manage(user, p):
        raise HTTPException(403, "bukan pengelola tempat ini")
    today = now_wib().replace(hour=0, minute=0, second=0, microsecond=0)
    since = iso_utc(today.astimezone(timezone.utc))
    until = iso_utc((today + timedelta(days=1)).astimezone(timezone.utc))
    rows = db.execute("SELECT status, level FROM crowd_reports WHERE place_id = ? AND created_at >= ? AND created_at < ?",
                      (place_id, since, until)).fetchall()
    valid = [r["level"] for r in rows if r["status"] == "valid"]
    return {
        "forecast": service.visit_forecast(db, p, date or today.date()),
        "current": crowd_status(db, p),
        "reports_today": {
            "count": len(rows), "valid": len(valid),
            "flagged": sum(r["status"] == "flagged" for r in rows),
            "rejected": sum(r["status"] == "rejected" for r in rows),
            "avg_level": round(sum(valid) / len(valid), 2) if valid else None,
        },
    }
