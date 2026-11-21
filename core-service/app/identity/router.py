import sqlite3
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from ..db import get_db
from . import service
from .deps import User, get_current_user, require_roles
from .schemas import ApiKeyCreate, ApiKeyCreated, ApiKeyOut, LoginIn, RegisterIn, RoleUpdate, TokenOut, UserOut, VerifyIn
from .security import create_token

router = APIRouter(prefix="/api", tags=["Identity"])
admin_only = require_roles("admin")


@router.post("/auth/register", response_model=UserOut, status_code=status.HTTP_201_CREATED,
             summary="Daftar akun wisatawan atau pengelola")
def register(body: RegisterIn, db: sqlite3.Connection = Depends(get_db)):
    try:
        return service.create_user(db, body.email, body.name, body.password, body.role)
    except service.IdentityError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e))


@router.post("/auth/login", response_model=TokenOut, summary="Login, dapat JWT")
def login(body: LoginIn, db: sqlite3.Connection = Depends(get_db)):
    user = service.authenticate(db, body.email, body.password)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "email atau password salah")
    token, expires = create_token(user["id"], user["role"])
    return {"access_token": token, "token_type": "bearer", "expires_in": expires, "user": user}


@router.get("/auth/me", response_model=UserOut, summary="Profil pengguna yang sedang login")
def me(user: User = Depends(get_current_user)):
    return user


@router.get("/admin/users", response_model=List[UserOut], tags=["Admin"])
def list_users(_: User = Depends(admin_only), db: sqlite3.Connection = Depends(get_db)):
    return service.list_users(db)


@router.patch("/admin/users/{user_id}/role", response_model=UserOut, tags=["Admin"])
def set_role(user_id: int, body: RoleUpdate, _: User = Depends(admin_only), db: sqlite3.Connection = Depends(get_db)):
    user = service.set_role(db, user_id, body.role)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "pengguna tidak ditemukan")
    return user


@router.patch("/admin/users/{user_id}/verify", response_model=UserOut, tags=["Admin"],
              summary="Verifikasi akun pengelola / UMKM")
def verify_user(user_id: int, body: VerifyIn, _: User = Depends(admin_only), db: sqlite3.Connection = Depends(get_db)):
    user = service.set_verified(db, user_id, body.verified)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "pengguna tidak ditemukan")
    return user


@router.post("/admin/api-keys", response_model=ApiKeyCreated, status_code=status.HTTP_201_CREATED, tags=["Admin"],
             summary="Buat API key untuk kelompok lain (kunci hanya tampil sekali)")
def create_key(body: ApiKeyCreate, admin: User = Depends(admin_only), db: sqlite3.Connection = Depends(get_db)):
    return service.create_api_key(db, body.client_name, admin["id"])


@router.get("/admin/api-keys", response_model=List[ApiKeyOut], tags=["Admin"])
def list_keys(_: User = Depends(admin_only), db: sqlite3.Connection = Depends(get_db)):
    return service.list_api_keys(db)


@router.delete("/admin/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Admin"],
               summary="Cabut API key")
def revoke_key(key_id: int, _: User = Depends(admin_only), db: sqlite3.Connection = Depends(get_db)):
    if not service.revoke_api_key(db, key_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "API key tidak ditemukan")
