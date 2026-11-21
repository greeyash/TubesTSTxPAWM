import sqlite3
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..common import parse_id_list
from ..db import get_db
from ..places.service import get_place
from ..identity.deps import User, get_current_user, require_roles
from ..places.service import PlaceError, can_manage, require_place
from . import service
from .schemas import CrowdBatchOut, CrowdReportIn, CrowdReportOut, CrowdStatusOut, ModerateIn

router = APIRouter(prefix="/api", tags=["Crowd"])


def _place(db: sqlite3.Connection, place_id: int):
    try:
        return require_place(db, place_id)
    except PlaceError as e:
        raise HTTPException(e.code, str(e))


@router.post("/places/{place_id}/crowd-reports", response_model=CrowdReportOut, status_code=status.HTTP_201_CREATED,
             summary="Kirim laporan keramaian")
def report(place_id: int, body: CrowdReportIn, user: User = Depends(get_current_user),
           db: sqlite3.Connection = Depends(get_db)):
    place = _place(db, place_id)
    try:
        return service.submit_report(db, place, user, body.level, body.note, body.lat, body.lon)
    except service.CrowdError as e:
        raise HTTPException(e.code, str(e))


@router.get("/places/{place_id}/crowd", response_model=CrowdStatusOut, summary="Status keramaian saat ini")
def crowd_status(place_id: int, db: sqlite3.Connection = Depends(get_db)):
    return service.crowd_status(db, _place(db, place_id))


@router.get("/places/{place_id}/crowd-reports", response_model=List[CrowdReportOut],
            summary="Riwayat laporan keramaian")
def list_reports(place_id: int, limit: int = Query(50, ge=1, le=200),
                 user: User = Depends(require_roles("pengelola", "admin")), db: sqlite3.Connection = Depends(get_db)):
    place = _place(db, place_id)
    if not can_manage(user, place):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "bukan pengelola tempat ini")
    return service.list_reports(db, place_id, limit)


@router.patch("/crowd-reports/{report_id}", response_model=CrowdReportOut, summary="Setujui atau tolak laporan")
def moderate(report_id: int, body: ModerateIn, user: User = Depends(require_roles("pengelola", "admin")),
             db: sqlite3.Connection = Depends(get_db)):
    row = service.get_report(db, report_id)
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "laporan tidak ditemukan")
    if not can_manage(user, _place(db, row["place_id"])):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "bukan pengelola tempat ini")
    return service.moderate(db, report_id, body.status)


def crowd_batch(raw_ids: str, db: sqlite3.Connection):
    try:
        ids = parse_id_list(raw_ids)
    except ValueError as e:
        raise HTTPException(422, str(e))
    data, missing = [], []
    for pid in ids:
        p = get_place(db, pid)
        if p:
            data.append(service.crowd_status(db, p))
        else:
            missing.append(pid)
    return {"data": data, "missing_ids": missing}


@router.get("/crowd", response_model=CrowdBatchOut, summary="Status keramaian beberapa tempat")
def crowd_many(place_ids: str = Query(..., description="mis. 1,2,3 (maks 50)"), db: sqlite3.Connection = Depends(get_db)):
    return crowd_batch(place_ids, db)
