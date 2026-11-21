"""SQLite: koneksi, skema, dan pemuatan data seed."""
import json
import logging
import sqlite3
from pathlib import Path
from typing import Iterator

from .common import iso_utc, utcnow
from .config import settings

log = logging.getLogger("bebas.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('wisatawan','pengelola','admin')),
  verified INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS api_keys (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  client_name TEXT NOT NULL,
  key_prefix TEXT NOT NULL,
  key_hash TEXT UNIQUE NOT NULL,
  created_by INTEGER REFERENCES users(id),
  created_at TEXT NOT NULL,
  last_used_at TEXT,
  request_count INTEGER NOT NULL DEFAULT 0,
  revoked INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS corridors (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  slug TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL,
  start_lat REAL NOT NULL, start_lon REAL NOT NULL,
  end_lat REAL NOT NULL, end_lon REAL NOT NULL,
  length_km REAL NOT NULL,
  base_speed_kmh REAL NOT NULL,
  factors TEXT NOT NULL,
  notes TEXT
);
CREATE TABLE IF NOT EXISTS places (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  slug TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL,
  category TEXT NOT NULL CHECK (category IN ('outdoor','indoor','landmark','kuliner')),
  description TEXT,
  address TEXT,
  lat REAL NOT NULL,
  lon REAL NOT NULL,
  open_time TEXT NOT NULL,
  close_time TEXT NOT NULL,
  closed_days TEXT NOT NULL DEFAULT '[]',
  peak_hours TEXT NOT NULL DEFAULT '{}',
  parking TEXT NOT NULL DEFAULT '{}',
  rain_friendly INTEGER NOT NULL DEFAULT 0,
  halal INTEGER NOT NULL DEFAULT 0,
  avg_visit_minutes INTEGER NOT NULL DEFAULT 60,
  ticket_price INTEGER NOT NULL DEFAULT 0,
  food_type TEXT,
  price_level INTEGER,
  signature_menu TEXT NOT NULL DEFAULT '[]',
  corridor_slug TEXT,
  manager_id INTEGER REFERENCES users(id),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS crowd_reports (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  place_id INTEGER NOT NULL REFERENCES places(id) ON DELETE CASCADE,
  user_id INTEGER NOT NULL REFERENCES users(id),
  level INTEGER NOT NULL CHECK (level BETWEEN 1 AND 5),
  note TEXT,
  reporter_lat REAL,
  reporter_lon REAL,
  status TEXT NOT NULL CHECK (status IN ('valid','flagged','rejected')),
  weight REAL NOT NULL,
  reason TEXT,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_crowd_place_time ON crowd_reports(place_id, created_at);
CREATE TABLE IF NOT EXISTS plans (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id),
  title TEXT NOT NULL,
  date TEXT NOT NULL,
  start_time TEXT NOT NULL,
  origin_lat REAL NOT NULL,
  origin_lon REAL NOT NULL,
  options TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS plan_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  plan_id INTEGER NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
  place_id INTEGER REFERENCES places(id),
  ext_ref TEXT,
  ext_snapshot TEXT,
  position INTEGER NOT NULL,
  duration_minutes INTEGER NOT NULL,
  kind TEXT NOT NULL DEFAULT 'kunjungan' CHECK (kind IN ('kunjungan','makan_siang','jajan_sore')),
  locked_time TEXT,
  CHECK (place_id IS NOT NULL OR ext_ref IS NOT NULL)
);
CREATE TABLE IF NOT EXISTS domain_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  type TEXT NOT NULL,
  aggregate TEXT NOT NULL,
  aggregate_id INTEGER NOT NULL,
  payload TEXT NOT NULL,
  occurred_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_type ON domain_events(type, id);
"""


def connect() -> sqlite3.Connection:
    Path(settings.db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.db_path, check_same_thread=False, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def get_db() -> Iterator[sqlite3.Connection]:
    """Dependency FastAPI: satu koneksi per request. Service melakukan commit sendiri."""
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    conn = connect()
    try:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.executescript(SCHEMA)
        _seed(conn)
        conn.commit()
    finally:
        conn.close()


def _seed(conn: sqlite3.Connection) -> None:
    now = iso_utc(utcnow())
    if conn.execute("SELECT COUNT(*) FROM corridors").fetchone()[0] == 0:
        data = json.loads((settings.seed_dir / "corridors.json").read_text(encoding="utf-8"))
        conn.execute(
            "INSERT OR REPLACE INTO meta(key, value) VALUES ('default_profile', ?)",
            (json.dumps(data["default_profile"]),),
        )
        for c in data["corridors"]:
            for day in ("weekday", "weekend"):
                if len(c["factors"][day]) != 24:
                    raise ValueError(f"koridor {c['slug']}: faktor {day} harus 24 nilai")
            conn.execute(
                "INSERT INTO corridors(slug,name,start_lat,start_lon,end_lat,end_lon,length_km,base_speed_kmh,factors,notes)"
                " VALUES (?,?,?,?,?,?,?,?,?,?)",
                (c["slug"], c["name"], c["start"]["lat"], c["start"]["lon"], c["end"]["lat"], c["end"]["lon"],
                 c["length_km"], c["base_speed_kmh"], json.dumps(c["factors"]), c.get("notes")),
            )
        log.info("seed: %d koridor dimuat", len(data["corridors"]))
    if conn.execute("SELECT COUNT(*) FROM places").fetchone()[0] == 0:
        data = json.loads((settings.seed_dir / "places.json").read_text(encoding="utf-8"))
        for p in data["places"]:
            conn.execute(
                "INSERT INTO places(slug,name,category,description,address,lat,lon,open_time,close_time,closed_days,"
                "peak_hours,parking,rain_friendly,halal,avg_visit_minutes,ticket_price,food_type,price_level,"
                "signature_menu,corridor_slug,created_at,updated_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (p["slug"], p["name"], p["category"], p.get("description"), p.get("address"), p["lat"], p["lon"],
                 p["open_time"], p["close_time"], json.dumps(p.get("closed_days", [])),
                 json.dumps(p.get("peak_hours", {})), json.dumps(p.get("parking", {})),
                 int(p.get("rain_friendly", False)), int(p.get("halal", False)), p.get("avg_visit_minutes", 60),
                 p.get("ticket_price", 0), p.get("food_type"), p.get("price_level"),
                 json.dumps(p.get("signature_menu", []), ensure_ascii=False), p.get("corridor_slug"), now, now),
            )
        log.info("seed: %d tempat dimuat", len(data["places"]))
