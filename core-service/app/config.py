"""Konfigurasi dari environment variable (.env dibaca oleh docker compose)."""
import os
from pathlib import Path

_DEFAULT_SECRET = "dev-secret-change-me"


def _flag(name: str, default: str) -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "on", "true", "yes")


class Settings:
    def __init__(self) -> None:
        self.app_env = os.getenv("APP_ENV", "development")
        self.db_path = os.getenv("DB_PATH", "data/bebas.db")
        self.seed_dir = Path(os.getenv("SEED_DIR", str(Path(__file__).resolve().parent.parent / "seed")))
        self.jwt_secret = os.getenv("JWT_SECRET", _DEFAULT_SECRET)
        self.jwt_expire_minutes = int(os.getenv("JWT_EXPIRE_MINUTES", "1440"))
        self.admin_email = os.getenv("ADMIN_EMAIL", "").strip().lower()
        self.admin_password = os.getenv("ADMIN_PASSWORD", "")
        self.external_apis = _flag("EXTERNAL_APIS", "on")
        self.osrm_url = os.getenv("OSRM_URL", "https://router.project-osrm.org").rstrip("/")
        self.open_meteo_url = os.getenv("OPEN_METEO_URL", "https://api.open-meteo.com/v1/forecast")
        self.http_timeout = float(os.getenv("HTTP_TIMEOUT", "4"))
        # API publik menolak (403) klien tanpa User-Agent yang jelas
        self.user_agent = os.getenv("USER_AGENT", "TugasBesar-TST/1.0 (kelompok-bebas)")
        self.public_base_url = os.getenv("PUBLIC_BASE_URL", "https://bebas.stei.site").rstrip("/")
        # batas pemanggilan per API key (selain rate limit per IP di Nginx)
        self.api_key_rate_per_min = int(os.getenv("API_KEY_RATE_PER_MIN", "120"))
        self.cors_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]
        # aturan validasi laporan keramaian
        self.crowd_max_distance_km = float(os.getenv("CROWD_MAX_DISTANCE_KM", "1.0"))
        self.crowd_cooldown_minutes = int(os.getenv("CROWD_COOLDOWN_MINUTES", "30"))

    def check(self) -> None:
        if self.app_env == "production" and (self.jwt_secret == _DEFAULT_SECRET or len(self.jwt_secret) < 32):
            raise RuntimeError("JWT_SECRET wajib diisi (minimal 32 karakter) saat APP_ENV=production")


settings = Settings()
VERSION = "0.1.0"
