"""Cari foto tempat dari Wikipedia bahasa Indonesia / Wikimedia Commons, lalu simpan ke seed/places.json.

Hanya foto berlisensi bebas (CC / domain publik) yang dipakai. Setiap foto menyimpan nama
fotografer, lisensi, dan tautan sumber untuk atribusi di aplikasi.

  python scripts/fetch_photos.py            # lihat hasil pencarian saja
  python scripts/fetch_photos.py --write    # simpan ke seed/places.json
  python scripts/fetch_photos.py --write --only=gedung-sate,jalan-braga   # sebagian tempat saja
"""
import html
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

SEED = Path(__file__).resolve().parent.parent / "seed" / "places.json"
UA = "TugasBesar-TST/1.0 (kelompok-bebas)"
WIKI = "https://id.wikipedia.org/w/api.php"
COMMONS = "https://commons.wikimedia.org/w/api.php"
FREE = re.compile(r"(CC[ -]?BY|CC0|public domain|^PD|GFDL|copyrighted free use)", re.I)

# Judul artikel yang pasti (kalau pencarian otomatis kurang tepat). None = sengaja tanpa foto.
TITLES = {
    "farmhouse-susu-lembang": "Farm House Lembang",
    "tahura-djuanda": "Taman Hutan Raya Ir. H. Djuanda",
    "babakan-siliwangi": "Babakan Siliwangi",
    "kawah-putih": "Kawah Putih",
    "museum-geologi": "Museum Geologi Bandung",
    "museum-kaa": "Museum Konferensi Asia Afrika",
    "trans-studio-bandung": "Trans Studio Bandung",
    "museum-sri-baduga": "Museum Sri Baduga",
    "saung-angklung-udjo": "Saung Angklung Udjo",
    "museum-pos-indonesia": "Museum Pos Indonesia",
    "gedung-sate": "Gedung Sate",
    "jalan-braga": "Jalan Braga",
    "observatorium-bosscha": "Observatorium Bosscha",
    "lapangan-gasibu": "Lapangan Gasibu",
    "tebing-keraton": "Tebing Keraton",
    "orchid-forest-cikole": "Orchid Forest Cikole",
    "kebun-teh-rancabali": "Rancabali, Bandung",
}

# File Commons yang dipilih manual (sudah dicek gambarnya)
FILES = {
    "floating-market-lembang": "Floating Market Lembang (27031698372).jpg",
    "situ-patenggang": "Danau Situ Patenggang, Ciwidey, Jawa Barat.jpg",
    "alun-alun-bandung": "Masjid Raya Bandung dan Alun-alun Bandung (potrait).jpg",
    "trans-studio-bandung": "Transtudio bandung - panoramio.jpg",
    "tebing-keraton": "Tebing Keraton 07.jpg",
    "kebun-teh-rancabali": "Kebun teh rancabali.jpg",
}

# Tidak ada foto bebas yang benar-benar menunjukkan tempat ini -> pakai ilustrasi
SKIP = {"farmhouse-susu-lembang", "kuliner-ciwidey", "oleh-oleh-lembang", "lapangan-gasibu"}

# Kata kunci pencarian langsung di Wikimedia Commons (dipakai kalau artikel tidak punya foto yang cocok)
COMMONS_QUERY = {
    "pasar-cihapit": "Cihapit market Bandung",
    "paskal-food-market": "Paskal Hyper Square",
    "braga-culinary-night": "Braga Bandung night",
    "kampung-daun": "Kampung Daun Bandung",
    "oleh-oleh-ciwidey": "Ciwidey strawberry",
}


def get(url, params, tries=5):
    """GET ke API MediaWiki, menunggu kalau kena batas pemanggilan (429)."""
    q = urllib.parse.urlencode({**params, "format": "json", "formatversion": 2, "maxlag": 5})
    req = urllib.request.Request(f"{url}?{q}", headers={"User-Agent": UA})
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                time.sleep(1.0)  # jaga kecepatan: maks ~1 permintaan/detik
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code != 429 or attempt == tries - 1:
                raise
            wait = int(e.headers.get("Retry-After") or 10 * (attempt + 1))
            print(f"  (kena batas, tunggu {wait} dtk)")
            time.sleep(wait)


def page_images(titles):
    """Ambil gambar utama banyak artikel sekaligus. Hasil: {judul_diminta: (judul_asli, nama_file)}."""
    out = {}
    if not titles:
        return out
    data = get(WIKI, {"action": "query", "titles": "|".join(titles), "prop": "pageimages", "piprop": "name", "redirects": 1})
    q = data.get("query", {})
    alias = {}
    for n in q.get("normalized", []) + q.get("redirects", []):
        alias[n["to"]] = alias.get(n["from"], n["from"])
    for pg in q.get("pages", []):
        if pg.get("missing") or not pg.get("pageimage"):
            continue
        asked = alias.get(pg["title"], pg["title"])
        asked = alias.get(asked, asked)
        out[asked] = (pg["title"], pg["pageimage"])
        out[pg["title"]] = (pg["title"], pg["pageimage"])
    return out


def commons_search(name):
    data = get(COMMONS, {"action": "query", "list": "search", "srnamespace": 6,
                         "srsearch": f"{name} filetype:bitmap", "srlimit": 1})
    hits = data.get("query", {}).get("search", [])
    return hits[0]["title"].removeprefix("File:") if hits else None


def page_image(title):
    data = get(WIKI, {"action": "query", "titles": title, "prop": "pageimages", "piprop": "name", "redirects": 1})
    pages = data.get("query", {}).get("pages", [])
    if not pages or pages[0].get("missing"):
        return None, None
    return pages[0]["title"], pages[0].get("pageimage")


def search(name):
    data = get(WIKI, {"action": "query", "list": "search", "srsearch": f"{name} Bandung", "srlimit": 3})
    return [h["title"] for h in data.get("query", {}).get("search", [])]


def file_info(filename):
    for api in (COMMONS, WIKI):
        data = get(api, {"action": "query", "titles": f"File:{filename}", "prop": "imageinfo",
                         "iiprop": "url|extmetadata", "iiurlwidth": 900})
        pages = data.get("query", {}).get("pages", [])
        if pages and pages[0].get("imageinfo"):
            ii = pages[0]["imageinfo"][0]
            meta = ii.get("extmetadata", {})
            artist = re.sub(r"<[^>]+>", "", html.unescape(meta.get("Artist", {}).get("value", ""))).strip()
            return {
                "url": ii.get("thumburl") or ii["url"],
                "credit": re.sub(r"\s+", " ", artist)[:80] or "Wikimedia Commons",
                "license": meta.get("LicenseShortName", {}).get("value", ""),
                "source": ii.get("descriptionurl"),
            }
    return None


def main(write, only=None):
    data = json.loads(SEED.read_text(encoding="utf-8"))
    found = 0
    imgs = page_images([t for s_, t in TITLES.items() if t and (not only or s_ in only)])
    for p in data["places"]:
        slug = p["slug"]
        if only and slug not in only:
            continue
        title = TITLES.get(slug)
        candidates = []  # (sumber, nama_file)
        if slug in SKIP:
            print(f"{slug:28} - (dilewati)", flush=True)
            continue
        if slug in FILES:
            candidates.append((f"Commons: {FILES[slug]}", FILES[slug]))
        elif title and title in imgs:
            candidates.append((imgs[title][0], imgs[title][1]))
        if not candidates and not title and p["category"] != "kuliner":
            for t in search(p["name"])[:1]:
                _, img = page_image(t)
                if img:
                    candidates.append((t, img))
        if not candidates and (slug in COMMONS_QUERY or p["category"] != "kuliner"):
            f = commons_search(COMMONS_QUERY.get(slug) or f"{p['name']} Bandung")
            if f:
                candidates.append((f"Commons: {f}", f))
        photo = None
        for src, img in candidates:
            info = file_info(img)
            if info and FREE.search(info["license"]):
                photo = {**info, "wiki": src}
                break
        status = f"{photo['wiki'][:60]} | {photo['license']} | {photo['url']}" if photo else "-"
        print(f"{slug:28} {status}", flush=True)
        if photo:
            found += 1
            if write:
                p["photo"] = photo
    print(f"\n{found}/{len(data['places'])} tempat punya foto")
    if write:
        SEED.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        print("disimpan ke", SEED)


if __name__ == "__main__":
    only = None
    for a in sys.argv[1:]:
        if a.startswith("--only="):
            only = set(a.split("=", 1)[1].split(","))
    main("--write" in sys.argv, only)
