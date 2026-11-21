from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

Role = Literal["wisatawan", "pengelola", "admin"]


def _email(v: str) -> str:
    v = v.strip().lower()
    local, _, domain = v.partition("@")
    if not local or "." not in domain or " " in v:
        raise ValueError("email tidak valid")
    return v


class RegisterIn(BaseModel):
    email: str = Field(examples=["budi@example.com"])
    name: str = Field(min_length=2, max_length=80)
    password: str = Field(min_length=8, max_length=128)
    role: Literal["wisatawan", "pengelola"] = "wisatawan"

    _v_email = field_validator("email")(_email)


class LoginIn(BaseModel):
    email: str
    password: str

    _v_email = field_validator("email")(_email)


class UserOut(BaseModel):
    id: int
    email: str
    name: str
    role: Role
    verified: bool = Field(description="pengelola wajib diverifikasi admin sebelum mengelola tempat")
    created_at: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut


class RoleUpdate(BaseModel):
    role: Role


class VerifyIn(BaseModel):
    verified: bool = True


class ApiKeyCreate(BaseModel):
    client_name: str = Field(min_length=2, max_length=80, examples=["K02-kelompok-lain"])


class ApiKeyOut(BaseModel):
    id: int
    client_name: str
    key_prefix: str
    created_at: str
    last_used_at: Optional[str] = None
    request_count: int
    revoked: bool


class VerifyIn(BaseModel):
    verified: bool = True


class ApiKeyCreated(ApiKeyOut):
    api_key: str = Field(description="Ditampilkan SEKALI saja. Server hanya menyimpan hash-nya.")
