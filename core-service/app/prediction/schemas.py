from typing import Dict, List, Literal, Optional

from pydantic import BaseModel


class LatLonOut(BaseModel):
    lat: float
    lon: float


class CorridorOut(BaseModel):
    id: int
    slug: str
    name: str
    start: LatLonOut
    end: LatLonOut
    length_km: float
    base_speed_kmh: float
    factors: Dict[str, List[float]]
    notes: Optional[str] = None


class HourFactor(BaseModel):
    hour: str
    factor: float
    minutes: float


class CorridorFactorsOut(BaseModel):
    slug: str
    name: str
    date: str
    day_type: str
    hours: List[HourFactor]


class CorridorShare(BaseModel):
    slug: str
    name: str
    share: float
    factor: float


class WeatherInfo(BaseModel):
    precipitation_mm: Optional[float] = None
    precipitation_probability: Optional[int] = None
    rain_impact: Optional[Literal["tidak_ada", "ringan", "sedang", "lebat"]] = None


class Confidence(BaseModel):
    score: float
    level: Literal["rendah", "sedang", "tinggi"]
    reasons: List[str]


class Sources(BaseModel):
    routing: str
    weather: str


class Endpoint(BaseModel):
    lat: float
    lon: float
    name: Optional[str] = None


class TravelPrediction(BaseModel):
    origin: Endpoint
    destination: Endpoint
    distance_km: float
    free_flow_minutes: float
    traffic_factor: float
    weather_factor: float
    predicted_minutes: float
    depart_at: str
    arrive_at: str
    corridors: List[CorridorShare]
    weather: WeatherInfo
    confidence: Confidence
    sources: Sources


class Slot(BaseModel):
    depart_at: str
    arrive_at: str
    minutes: float
    traffic_factor: float
    weather_factor: float
    confidence: Literal["rendah", "sedang", "tinggi"]
    on_time: Optional[bool] = None


class Window(BaseModel):
    start: str
    end: str
    max_minutes: float


class TimeRange(BaseModel):
    start: str
    end: str


class DepartureWindowOut(BaseModel):
    origin: Endpoint
    destination: Endpoint
    date: str
    distance_km: float
    corridors: List[CorridorShare]
    sources: Sources
    best: Slot
    recommended_window: Window
    avoid: List[TimeRange]
    slots: List[Slot]
    notes: List[str]
