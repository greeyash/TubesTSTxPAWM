import sqlite3
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..db import get_db
from ..identity.deps import User, require_manager
from . import service
from .schemas import Category, FoodType, PlaceCreate, PlaceOut, PlaceUpdate

router = APIRouter(prefix="/api/places", tags=["Places"])


def _raise(e: service.PlaceError):
    raise HTTPException(e.code, str(e))


@router.get("", response_model=List[PlaceOut], summary="Daftar tempat")
def list_places(
    category: Optional[Category] = None,
    rain_friendly: Optional[bool] = Query(None, description="true = cocok saat hujan"),
    halal: Optional[bool] = None,
    corridor: Optional[str] = Query(None, description="slug koridor"),
    q: Optional[str] = Query(None, max_length=60, description="cari nama/alamat"),
    food_type: Optional[FoodType] = None,
    price_max: Optional[int] = Query(None, ge=1, le=4, description="batas price_level"),
    open_late: Optional[bool] = Query(None, description="true = buka malam (>= 21.00)"),
    open_now: Optional[bool] = None,
    db: sqlite3.Connection = Depends(get_db),
):
    return service.list_places(db, category, rain_friendly, halal, q, corridor, None, food_type, price_max,
                               open_late, open_now)


@router.get("/mine", response_model=List[PlaceOut], summary="Tempat yang saya kelola")
def my_places(user: User = Depends(require_manager), db: sqlite3.Connection = Depends(get_db)):
    return service.list_places(db, manager_id=user["id"])


@router.get("/{place_id}", response_model=PlaceOut, summary="Detail tempat")
def get_place(place_id: int, db: sqlite3.Connection = Depends(get_db)):
    p = service.get_place(db, place_id)
    if not p:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "tempat tidak ditemukan")
    return p


@router.post("", response_model=PlaceOut, status_code=status.HTTP_201_CREATED, summary="Tambah tempat")
def create_place(body: PlaceCreate, user: User = Depends(require_manager),
                 db: sqlite3.Connection = Depends(get_db)):
    data = body.model_dump()
    if user["role"] != "admin":
        data.pop("manager_id", None)
    try:
        return service.create_place(db, data, user)
    except service.PlaceError as e:
        _raise(e)


@router.patch("/{place_id}", response_model=PlaceOut, summary="Ubah tempat")
def update_place(place_id: int, body: PlaceUpdate, user: User = Depends(require_manager),
                 db: sqlite3.Connection = Depends(get_db)):
    try:
        return service.update_place(db, place_id, body.model_dump(exclude_unset=True), user)
    except service.PlaceError as e:
        _raise(e)
