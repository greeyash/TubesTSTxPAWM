"""Ekspor kontrak OpenAPI ke docs/openapi.json (bisa diimpor ke Postman: Import -> File).

  cd core-service && python scripts/export_openapi.py
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("EXTERNAL_APIS", "off")

from app.config import settings  # noqa: E402
from app.main import app  # noqa: E402

spec = app.openapi()
spec["servers"] = [
    {"url": settings.public_base_url, "description": "Produksi (STB via Cloudflare Tunnel)"},
    {"url": "http://localhost:8080", "description": "Lokal lewat gateway Nginx"},
    {"url": "http://localhost:8000", "description": "Lokal uvicorn --reload"},
]
out = Path(__file__).resolve().parents[2] / "docs" / "openapi.json"
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(spec, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"ditulis: {out} ({len(spec['paths'])} path)")
