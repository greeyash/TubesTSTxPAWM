from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, model_validator

from ..common import HHMM_PATTERN

Kind = Literal["kunjungan", "makan_siang", "jajan_sore"]
Level = Literal["rendah", "sedang", "tinggi"]
Queue = Literal["sepi", "sedang", "antre_panjang"]


class Origin(BaseModel):
    lat: float = Field(ge=-90, le=90, examples=[-6.9175])
    lon: float = Field(ge=-180, le=180, examples=[107.6191])


class ExternalPlace(BaseModel):
    """Snapshot destinasi kelompok lain (mis. Jelajah Nusantara K1). Disimpan apa adanya + waktu pengambilan."""
    destination_id: str = Field(pattern=r"^[a-z]{2,6}_[A-Za-z0-9_-]{1,40}$", examples=["dst_12"])
    name: str = Field(min_length=1, max_length=120, examples=["Curug Citambur"])
    lat: float = Field(ge=-11.5, le=6.5, description="dalam wilayah Indonesia")
    lon: float = Field(ge=94.5, le=141.5)
    opening_hours: Optional[str] = Field(default=None, examples=["07:00-16:00"])
    category: Optional[str] = Field(default=None, examples=["curug"],
                                    description="kategori versi sumber; diterjemahkan ke outdoor/indoor/landmark/kuliner")
    rain_friendly: Optional[bool] = None
    captured_at: Optional[str] = Field(default=None, examples=["2026-11-20T08:00:00Z"])


class PlanItemIn(BaseModel):
    place_id: Optional[int] = Field(default=None, description="tempat dari katalog Bebas")
    external: Optional[ExternalPlace] = Field(default=None, description="atau destinasi kelompok lain (snapshot)")
    duration_minutes: Optional[int] = Field(default=None, ge=10, le=720,
                                            description="default = rata-rata lama kunjungan tempat")
    locked_time: Optional[str] = Field(default=None, pattern=HHMM_PATTERN,
                                       description="kunci tempat ini pada jam tertentu (mulai kunjungan)")

    @model_validator(mode="after")
    def _one_source(self) -> "PlanItemIn":
        if (self.place_id is None) == (self.external is None):
            raise ValueError("isi salah satu: place_id (katalog Bebas) atau external (snapshot destinasi lain)")
        return self


class PlanOptions(BaseModel):
    insert_lunch: Optional[bool] = Field(default=None, description="sisipkan makan siang (11.00-13.30)")
    insert_snack: Optional[bool] = Field(default=None, description="sisipkan jajan sore (15.00-17.30)")
    halal_only: Optional[bool] = Field(default=None, description="slot makan hanya dari tempat halal")
    price_max: Optional[int] = Field(default=None, ge=1, le=4, description="batas price_level slot makan")


class PlanCreate(BaseModel):
    title: str = Field(default="Rencana satu hari", max_length=100)
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$", examples=["2026-11-28"])
    start_time: str = Field(default="08:00", pattern=HHMM_PATTERN)
    origin: Origin
    items: List[PlanItemIn] = Field(min_length=1, max_length=10)
    options: PlanOptions = Field(default_factory=PlanOptions)
    optimize: bool = Field(default=False, description="true = langsung susun urutan terbaik")


class PlanUpdate(BaseModel):
    title: Optional[str] = Field(default=None, max_length=100)
    date: Optional[str] = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    start_time: Optional[str] = Field(default=None, pattern=HHMM_PATTERN)
    origin: Optional[Origin] = None
    items: Optional[List[PlanItemIn]] = Field(default=None, min_length=1, max_length=10,
                                              description="mengganti seluruh daftar kunjungan, urutan sesuai array")
    options: Optional[PlanOptions] = None


class ReorderIn(BaseModel):
    strategy: Literal["optimize", "manual"] = "optimize"
    order: Optional[List[int]] = Field(default=None, description="untuk manual: daftar item_id sesuai urutan baru")
    from_time: Optional[str] = Field(default=None, pattern=HHMM_PATTERN,
                                     description="susun ulang sisa hari mulai jam ini (item yang sudah lewat dikunci)")
    apply_alternatives: bool = Field(default=False,
                                     description="ganti tempat yang kehujanan/antre panjang dengan alternatif teratas")


class ScheduleItem(BaseModel):
    item_id: int
    position: int
    kind: Kind
    locked_time: Optional[str] = None
    place_id: Optional[int] = None
    external_ref: Optional[str] = Field(default=None, description="ID destinasi kelompok lain, mis. dst_12")
    place_name: str
    category: str
    zone: Literal["utara", "kota", "selatan"]
    travel_minutes: float
    travel_confidence: Level
    arrive_at: str
    start_visit_at: str
    depart_at: str
    duration_minutes: int
    wait_minutes: float
    crowd_estimate: int
    crowd_label: str
    queue_status: Queue
    rain_mm: Optional[float] = None
    warnings: List[str]


class Summary(BaseModel):
    end_at: str
    total_travel_minutes: float
    total_wait_minutes: float
    warning_count: int
    score: float = Field(description="biaya total, makin kecil makin baik")


class Departure(BaseModel):
    planned_start: str
    recommended_start: str
    cost_saving: float
    note: str


class Alternative(BaseModel):
    place_id: int
    name: str
    category: str
    detour_km: float


class Suggestion(BaseModel):
    item_id: int
    place_id: Optional[int] = None
    external_ref: Optional[str] = None
    place_name: str
    reason: Literal["hujan", "antre_panjang", "tutup"]
    alternatives: List[Alternative]


class PlanOut(BaseModel):
    id: int
    user_id: int
    title: str
    date: str
    start_time: str
    origin: Origin
    options: Dict[str, Any]
    created_at: str
    updated_at: str
    schedule: List[ScheduleItem]
    summary: Summary
    warnings: List[str] = Field(description="peringatan tingkat rencana, mis. kombinasi utara-selatan")
    departure: Departure
    suggestions: List[Suggestion]
    sources: Dict[str, str]


class ReorderOut(PlanOut):
    before: Summary
    changed: bool
    reasons: List[str]


class PlanListItem(BaseModel):
    id: int
    title: str
    date: str
    start_time: str
    item_count: int
    updated_at: str


class EatNowItem(BaseModel):
    place_id: int
    name: str
    food_type: Optional[str] = None
    price_level: Optional[int] = None
    halal: bool
    signature_menu: List[str]
    distance_km: float
    travel_minutes: float
    traffic_status: Literal["lancar", "padat", "macet"]
    queue_status: Queue
    crowd_label: str
    crowd_source: str
    parking: Dict[str, Any]
    peak_hint: Optional[str] = None
    closes_at: str
    open_late: bool
    confidence: Level
    routing: str
    score: float


class EatNowOut(BaseModel):
    at: str
    origin: Origin
    radius_km: float
    skipped_long_queue: int
    results: List[EatNowItem]


class ForecastHour(BaseModel):
    hour: str
    planned_arrivals: int
    level: int
    label: str
    queue_status: Queue


class VisitForecast(BaseModel):
    place_id: int
    place_name: str
    date: str
    total_planned_arrivals: int
    busiest_hour: Optional[str] = None
    hours: List[ForecastHour]


class VisitForecastBatch(BaseModel):
    date: str
    data: List[VisitForecast]
    missing_ids: List[int] = []


class ReportSummary(BaseModel):
    count: int
    valid: int
    flagged: int
    rejected: int
    avg_level: Optional[float] = None


class Dashboard(BaseModel):
    forecast: VisitForecast
    current: Dict[str, Any]
    reports_today: ReportSummary
