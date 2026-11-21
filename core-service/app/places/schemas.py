from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from ..common import HHMM_PATTERN, hhmm_to_min

Category = Literal["outdoor", "indoor", "landmark", "kuliner"]
FoodType = Literal["makanan_berat", "jajanan", "kafe", "oleh_oleh", "sentra_kuliner"]
QueueStatus = Literal["sepi", "sedang", "antre_panjang"]
HHMM = Field(pattern=HHMM_PATTERN, examples=["08:00"])


def _check_ranges(v: List[List[str]]) -> List[List[str]]:
    for r in v:
        if len(r) != 2:
            raise ValueError("setiap rentang jam ramai berbentuk [\"HH:MM\", \"HH:MM\"]")
        a, b = hhmm_to_min(r[0]), hhmm_to_min(r[1])
        if b <= a:
            raise ValueError("jam akhir harus setelah jam mulai")
    return v


class PeakHours(BaseModel):
    weekday: List[List[str]] = Field(default_factory=list, examples=[[["11:00", "13:00"]]])
    weekend: List[List[str]] = Field(default_factory=list, examples=[[["09:00", "12:00"], ["15:00", "17:00"]]])

    _v_wd = field_validator("weekday")(_check_ranges)
    _v_we = field_validator("weekend")(_check_ranges)


class Parking(BaseModel):
    type: Literal["luas", "sedang", "terbatas", "tidak_ada"] = "sedang"
    capacity: Optional[int] = Field(default=None, ge=0)
    vehicle: Literal["mobil", "motor"] = Field(default="mobil", description="mobil = muat mobil dan motor; motor = hanya motor")


class Photo(BaseModel):
    url: str = Field(description="gambar (lebar ~900 px) dari Wikimedia Commons")
    credit: str = Field(description="nama fotografer, wajib ditampilkan")
    license: str = Field(examples=["CC BY-SA 4.0"])
    source: Optional[str] = Field(default=None, description="halaman file di Wikimedia Commons")
    wiki: Optional[str] = None


class PlaceFields(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    category: Category
    description: Optional[str] = Field(default=None, max_length=1000)
    address: Optional[str] = Field(default=None, max_length=300)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    open_time: str = HHMM
    close_time: str = Field(pattern=HHMM_PATTERN, examples=["17:00"])
    closed_days: List[int] = Field(default_factory=list, description="0=Senin .. 6=Minggu")
    peak_hours: PeakHours = Field(default_factory=PeakHours)
    parking: Parking = Field(default_factory=Parking)
    rain_friendly: bool = False
    halal: bool = True
    avg_visit_minutes: int = Field(default=60, ge=10, le=720)
    ticket_price: int = Field(default=0, ge=0)
    food_type: Optional[FoodType] = Field(default=None, description="hanya untuk kategori kuliner")
    price_level: Optional[int] = Field(default=None, ge=1, le=4,
                                       description="perkiraan per orang: 1 <25rb, 2 25-50rb, 3 50-100rb, 4 >100rb")
    signature_menu: List[str] = Field(default_factory=list, max_length=10, description="menu andalan")
    corridor_slug: Optional[str] = None

    @field_validator("closed_days")
    @classmethod
    def _days(cls, v: List[int]) -> List[int]:
        if any(d < 0 or d > 6 for d in v):
            raise ValueError("closed_days berisi 0..6")
        return sorted(set(v))


class PlaceCreate(PlaceFields):
    slug: Optional[str] = Field(default=None, pattern=r"^[a-z0-9-]+$")
    manager_id: Optional[int] = Field(default=None, description="Hanya admin yang boleh mengisi")


class PlaceUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=120)
    category: Optional[Category] = None
    description: Optional[str] = None
    address: Optional[str] = None
    lat: Optional[float] = Field(default=None, ge=-90, le=90)
    lon: Optional[float] = Field(default=None, ge=-180, le=180)
    open_time: Optional[str] = Field(default=None, pattern=HHMM_PATTERN)
    close_time: Optional[str] = Field(default=None, pattern=HHMM_PATTERN)
    closed_days: Optional[List[int]] = None
    peak_hours: Optional[PeakHours] = None
    parking: Optional[Parking] = None
    rain_friendly: Optional[bool] = None
    halal: Optional[bool] = None
    avg_visit_minutes: Optional[int] = Field(default=None, ge=10, le=720)
    ticket_price: Optional[int] = Field(default=None, ge=0)
    food_type: Optional[FoodType] = None
    price_level: Optional[int] = Field(default=None, ge=1, le=4)
    signature_menu: Optional[List[str]] = Field(default=None, max_length=10)
    corridor_slug: Optional[str] = None
    manager_id: Optional[int] = Field(default=None, description="Hanya admin")


class PlaceOut(PlaceFields):
    id: int
    slug: str
    manager_id: Optional[int] = None
    is_open_now: bool
    is_peak_now: bool
    open_late: bool = Field(description="buka sampai >= 21.00")
    photo: Optional[Photo] = Field(default=None, description="foto tempat (bisa kosong)")
    zone: Literal["utara", "kota", "selatan"]
    peak_hint: Optional[str] = Field(default=None, examples=["ramai pukul 12.00-13.00, disarankan datang 11.00"])
    created_at: str
    updated_at: str
