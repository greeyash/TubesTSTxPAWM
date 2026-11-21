from typing import List, Literal, Optional

from pydantic import BaseModel, Field

ReportStatus = Literal["valid", "flagged", "rejected"]


class CrowdReportIn(BaseModel):
    level: int = Field(ge=1, le=5, description="1=sepi, 2=sedang, 3=ramai, 4=sangat ramai, 5=penuh sesak")
    note: Optional[str] = Field(default=None, max_length=280)
    lat: Optional[float] = Field(default=None, ge=-90, le=90, description="lokasi pelapor (opsional, menaikkan bobot)")
    lon: Optional[float] = Field(default=None, ge=-180, le=180)


class CrowdReportOut(BaseModel):
    id: int
    place_id: int
    user_id: int
    level: int
    note: Optional[str] = None
    status: ReportStatus
    weight: float
    reason: Optional[str] = None
    distance_km: Optional[float] = None
    created_at: str


class ModerateIn(BaseModel):
    status: Literal["valid", "rejected"]


class CrowdStatusOut(BaseModel):
    place_id: int
    place_name: str
    level: int = Field(description="1..5")
    label: str
    queue_status: Literal["sepi", "sedang", "antre_panjang"]
    score: float = Field(description="skor kontinu 1.0..5.0")
    source: Literal["laporan", "campuran", "perkiraan"]
    confidence: float
    report_count: int
    window_minutes: int
    is_open: bool
    is_peak: bool
    at: str
    notes: List[str] = []


class CrowdBatchOut(BaseModel):
    data: List[CrowdStatusOut]
    missing_ids: List[int] = []
