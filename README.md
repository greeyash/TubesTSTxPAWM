# Bebas: Core Service (K02, Tourism)

Core service untuk **Sistem Perencanaan Perjalanan Wisata dan Kuliner Berbasis Prediksi Kemacetan dan Cuaca di Kota Bandung**. Layanan ini menjawab tiga pertanyaan: kapan sebaiknya berangkat, ke mana lebih dulu, dan di mana makan tanpa terjebak macet atau antrean.

- Base URL: `https://bebas.stei.site/api`
- Dokumentasi interaktif: `https://bebas.stei.site/api/docs` (OpenAPI di `/api/openapi.json`, bisa diimpor ke Postman)
- Auth: `Authorization: Bearer <JWT>` untuk pengguna aplikasi, `X-API-Key: <kunci>` untuk kelompok lain (`/api/public/*`)

## Kesesuaian dengan makalah (Tugas 1)

| Bounded context di makalah | Folder | Status Tugas 2 |
|---|---|---|
| Identitas & Akses | `app/identity` | Register/login JWT, peran wisatawan/pengelola/admin, verifikasi akun pengelola/UMKM, API key |
| Katalog Tempat (Wisata & Kuliner) | `app/places` | Kategori, jam buka, jam ramai, parkir (mobil/motor), cocok-hujan, halal, jenis makanan, harga, menu andalan, filter buka malam |
| Keramaian & Antrean | `app/crowd` | Laporan pengelola & pengunjung, aturan validasi, status antrean sepi/sedang/antre panjang |
| Prediksi Kondisi Perjalanan | `app/prediction` + `app/adapters` | Ruas/koridor, faktor jam, dampak cuaca, waktu tempuh + tingkat keyakinan, jendela berangkat |
| Perencanaan Perjalanan | `app/planning` | Itinerary, slot makan searah rute, kunci jam, susun ulang, alternatif indoor saat hujan, "Mau makan sekarang", dashboard pengelola |
| Notifikasi Perjalanan | - | Dikerjakan di Tugas 3. Event pemicunya sudah diterbitkan di `/api/events` |

Domain event (Published Language) yang dicatat ke tabel `domain_events`: `TempatDiperbarui`, `StatusAntreanBerubah`, `RencanaBerubah`. Prediksi kepadatan kunjungan ditawarkan ke kelompok lain sebagai Open Host Service di `/api/public/places/{id}/visit-forecast`.

**Perbedaan dari makalah yang disengaja**

- Prakiraan cuaca memakai **Open-Meteo**, bukan BMKG. Open-Meteo memberi data per jam tanpa perlu kode wilayah adm4. Semua istilah penyedia berhenti di `adapters/weather.py`, yang menerjemahkan curah hujan menjadi kategori *dampak hujan* (`tidak_ada/ringan/sedang/lebat`). Jadi pindah ke BMKG cukup dengan mengganti file itu.
- Data lalu lintas pihak ketiga belum tersedia. Sebagai gantinya dipakai **tabel faktor jam per koridor** (`seed/corridors.json`, masih perkiraan) dan jarak/durasi dari OSRM.
- Autentikasi memakai JWT buatan sendiri yang sederhana, bukan layanan autentikasi siap pakai, supaya bisa berjalan di STB tanpa layanan luar.

## Arsitektur

```
Internet ──► Cloudflare Tunnel (cloudflared di STB)
                 │  http://localhost:8080
                 ▼
        ┌──────────────────┐      ┌────────────────────────────────┐
        │ gateway (Nginx)  │ ───► │ core-service (FastAPI)         │
        │ rate limit 60/m  │      │  identity · places · crowd     │
        │ 127.0.0.1:8080   │      │  prediction · planning         │
        └──────────────────┘      │  adapters (ACL): OSRM, cuaca   │
                                  └──────────────┬─────────────────┘
                                                 ▼
                                       SQLite (./data/bebas.db)
```

Kalau OSRM tidak bisa dihubungi, prediksi memakai jarak garis lurus × 1,3. Kalau layanan cuaca tidak bisa dihubungi, prediksi berjalan tanpa faktor cuaca dan tingkat keyakinannya turun. Setelah gagal, adapter berhenti mencoba selama 60 detik.

## Endpoint

| Metode | Path | Auth | Keterangan |
|---|---|---|---|
| GET | `/api/health` | - | Cek service |
| POST | `/api/auth/register` | - | Daftar (`wisatawan` / `pengelola`). Pengelola perlu diverifikasi |
| POST | `/api/auth/login` | - | Dapat JWT |
| GET | `/api/auth/me` | JWT | Profil |
| GET, PATCH | `/api/admin/users`, `/api/admin/users/{id}/role`, `/api/admin/users/{id}/verify` | admin | Kelola & verifikasi pengguna |
| POST, GET, DELETE | `/api/admin/api-keys` | admin | Buat / lihat / cabut API key |
| GET | `/api/events` | admin | Semua domain event |
| GET | `/api/places` | - | Filter `category`, `food_type`, `price_max`, `halal`, `open_late`, `open_now`, `rain_friendly`, `corridor`, `q` |
| GET | `/api/places/{id}` | - | Detail (termasuk `peak_hint`, `zone`, `open_late`) |
| GET | `/api/places/mine` | pengelola terverifikasi | Tempat yang saya kelola |
| POST, PATCH | `/api/places`, `/api/places/{id}` | pengelola terverifikasi/admin | Tambah / ubah tempat |
| POST | `/api/places/{id}/crowd-reports` | JWT | Laporan keramaian (divalidasi otomatis) |
| GET | `/api/places/{id}/crowd` | - | Status keramaian & antrean |
| GET | `/api/places/{id}/crowd-reports` | pengelola tempat itu/admin | Riwayat laporan |
| PATCH | `/api/crowd-reports/{id}` | pengelola tempat itu/admin | Validasi/tolak manual |
| GET | `/api/places/{id}/visit-forecast?date=` | - | Prediksi kepadatan kunjungan per jam |
| GET | `/api/crowd?place_ids=1,2,3` · `/api/visit-forecast?place_ids=&date=` | - | Versi batch (maks 50 / 20 tempat) |
| GET | `/api/feed?since=` | - | Feed event publik (format Jelajah Nusantara) |
| GET | `/api/places/{id}/dashboard?date=` | pengelola tempat itu/admin | Perkiraan kedatangan dari itinerary + ringkasan laporan |
| GET | `/api/corridors`, `/api/corridors/{slug}/factors?date=` | - | Koridor dan faktor jam |
| GET | `/api/predict/travel-time` | JWT | Waktu tempuh + tingkat keyakinan |
| GET | `/api/predict/departure-window` | JWT | Jendela berangkat terbaik |
| POST, GET | `/api/plans` | JWT | Buat / daftar itinerary |
| GET, PATCH, DELETE | `/api/plans/{id}` | pemilik/admin | Lihat (jadwal dihitung ulang), ubah, hapus |
| POST | `/api/plans/{id}/reorder` | pemilik/admin | Susun ulang (`optimize`/`manual`, `from_time`, `apply_alternatives`) |
| GET | `/api/eat-now` | JWT | Mode "Mau makan sekarang" |
| GET | `/api/public/places` (paginasi), `/places/{id}`, `/places/{id}/crowd`, `/places/{id}/visit-forecast`, `/crowd?ids=`, `/visit-forecast?ids=`, `/corridors`, `/predict/travel-time`, `/predict/departure-window`, `/eat-now`, `/feed` | X-API-Key | Untuk kelompok lain |

Semua error berbentuk `{"error": "KODE_ERROR", "message": "..."}`. Kodenya: `BAD_REQUEST`, `UNAUTHORIZED`, `FORBIDDEN`, `NOT_FOUND`, `CONFLICT`, `VALIDATION_ERROR` (ditambah `details` per field), `RATE_LIMITED`.

Titik asal/tujuan prediksi ditulis sebagai `from_place_id` / `to_place_id`, atau `from_lat`+`from_lon` / `to_lat`+`to_lon`. Waktu tanpa zona dianggap WIB.

## Aturan bisnis

**Prediksi waktu tempuh**: `menit = waktu_lancar × faktor_lalu_lintas × faktor_cuaca`

- Waktu lancar diambil dari OSRM. Cadangannya jarak garis lurus × 1,3 dibagi kecepatan dasar koridor (30 km/jam di luar koridor).
- Faktor lalu lintas adalah rata-rata berbobot faktor jam koridor yang dilewati, dengan bobot porsi perjalanan di koridor itu. Bagian di luar koridor memakai profil jalan kota. Faktor diinterpolasi antarjam dan dihitung di titik tengah perjalanan.
- Faktor cuaca berasal dari kategori dampak hujan: lebat (≥ 5 mm/jam) ×1,30, sedang (≥ 1 mm) ×1,18, ringan (≥ 0,2 mm atau peluang ≥ 80%) ×1,08.
- Tingkat keyakinan dimulai dari 0,9. Nilainya turun kalau memakai cadangan garis lurus (−0,2), tanpa prakiraan cuaca (−0,1), berangkat lebih dari 3 hari lagi (−0,1), hujan sedang/lebat (−0,1), atau rute di luar koridor (−0,05). Hasil ≥ 0,75 = tinggi, ≥ 0,55 = sedang, selebihnya rendah.

**Jendela berangkat**: slot dibuat setiap `step` menit. Rekomendasinya adalah slot berurutan yang waktunya ≤ 110% dari yang tercepat. Slot ≥ 135% masuk `avoid`. Untuk itinerary, `departure.recommended_start` mencoba jam mulai dari −60 sampai +120 menit dan memilih yang biayanya terkecil.

**Validasi laporan keramaian**

1. Satu laporan per pengguna per tempat setiap 30 menit (HTTP 429).
2. Lokasi pelapor > 1 km dari tempat → `rejected`.
3. Pengelola terverifikasi untuk tempat itu, atau admin → `valid`, bobot 2,0.
4. Wisatawan dengan lokasi dekat → bobot 1,0, tanpa lokasi → 0,6. Pelapor dengan ≥ 5 laporan valid mendapat bobot ×1,2.
5. Laporan yang dibandingkan dengan laporan lain di waktu berdekatan: kalau ada ≥ 3 laporan valid dalam 60 menit dan selisih dengan median ≥ 3 level → `flagged`, bobot 0,2.

Status dihitung dari rata-rata berbobot laporan 90 menit terakhir, dengan bobot yang meluruh seiring waktu. Kalau laporannya sedikit, hasilnya dicampur dengan perkiraan dari jam ramai. Level 1–2 = sepi, 3 = sedang, 4–5 = antre panjang. Setiap perubahan level menerbitkan `StatusAntreanBerubah`.

**Perencanaan (itinerary)**: biaya sebuah urutan = menit perjalanan + 0,5 × menit menunggu, ditambah penalti:

| Kondisi | Penalti |
|---|---|
| Tiba saat tempat tutup atau hari libur | 300 |
| Terlambat > 10 menit dari jam yang dikunci | 200 |
| Slot makan di luar jendela (siang 11.00–13.30, jajan 15.00–17.30) | 150 |
| Kunjungan melewati jam tutup | 120 |
| Tempat tidak cocok hujan saat hujan ≥ 1 mm | 45 |
| Dilaporkan antre panjang | 40 |
| Tiba di jam ramai | 20 |

- Urutan: rencana ≤ 7 tempat dicoba semua permutasinya. Lebih dari itu, dipakai greedy + 2-opt.
- Slot makan ("sisipkan makan siang/jajan sore"): tempat kuliner dan posisinya dipilih yang menambah biaya paling kecil, sehingga yang terpilih adalah yang searah rute. Contohnya, setelah Farmhouse sistem memilih makan di Lembang/Setiabudi. Ada opsi `halal_only` dan `price_max`.
- Kunci jam (`locked_time`): kunjungan dimulai tepat pada jam tersebut, dan optimasi menghormatinya.
- Peringatan rencana: kombinasi kawasan utara (Lembang/Dago Pakar) dan selatan (Ciwidey) dianggap tidak realistis untuk satu hari. Rencana yang selesai lewat 22.00 juga diberi peringatan.
- `suggestions`: alternatif yang searah (memutar ≤ 10 km) untuk tempat yang kehujanan (diganti tempat indoor/landmark yang cocok hujan), tutup, atau dilaporkan antre panjang. `reorder` dengan `apply_alternatives: true` langsung menerapkan alternatif teratas.

**Mau makan sekarang**: menampilkan tempat kuliner dalam radius tertentu yang masih buka minimal 30 menit lagi. Skornya = menit perjalanan + penalti antrean (sedang 10, antre panjang 30) + 10 kalau jalan padat. Tempat yang *dilaporkan* antre panjang disembunyikan. Filternya: harga, halal, jenis makanan, buka malam.

**Dashboard pengelola dan prediksi kepadatan**: kedatangan per jam dihitung dari itinerary yang disimpan pengguna untuk tanggal itu, lalu digabung dengan jam ramai. Tingkat keramaian naik 1 kalau ada ≥ 3 kedatangan per jam, dan naik 2 kalau ≥ 8.

## Menjalankan

### Laptop (tanpa Docker)
```bash
cd core-service
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
ADMIN_EMAIL=admin@local.test ADMIN_PASSWORD=admin12345 uvicorn app.main:app --reload
# buka http://localhost:8000/api/docs
pytest -q          # tes otomatis (tanpa jaringan)
```

### Docker / STB
```bash
cp .env.example .env      # isi JWT_SECRET dan ADMIN_PASSWORD
docker compose up -d --build
curl http://localhost:8080/api/health
```
Database tersimpan di `./data/bebas.db` (volume). Seed koridor dan tempat dimuat otomatis saat tabel masih kosong. Kalau skema berubah sebelum ada data penting, cukup hapus `./data/bebas.db` lalu jalankan ulang.

Setiap kontainer punya `mem_limit`, `cpus`, `restart: unless-stopped`, dan rotasi log. Gateway hanya membuka `127.0.0.1:8080`, jadi satu-satunya jalan masuk dari internet adalah lewat tunnel.

### Cloudflare Tunnel (pilih salah satu)

| | Opsi A: cloudflared service sistem | Opsi B: cloudflared kontainer (format dokumen tugas) |
|---|---|---|
| Kapan dipakai | `sudo systemctl status cloudflared` sudah *active (running)* | cloudflared belum terpasang di STB |
| `.env` | tidak perlu apa-apa | `COMPOSE_PROFILES=tunnel` dan `TUNNEL_TOKEN=...` |
| Public Hostname (tunnel `k02-bebas`) | `bebas` · `stei.site` · Path kosong · HTTP · **`127.0.0.1:8080`** | `bebas` · `stei.site` · HTTP · **`gateway:80`** |
| Cek | `curl https://bebas.stei.site/api/health` | `docker compose logs tunnel \| tail -3`, lalu curl yang sama |

Jangan memakai keduanya sekaligus. Token tunnel hanya disimpan di `.env` STB, tidak pernah di-commit.

Pakai `127.0.0.1`, bukan `localhost`. cloudflared bisa mencoba `localhost` lewat IPv6 (`::1`), padahal gateway hanya mendengarkan di IPv4, sehingga hasilnya 502.

Kalau Public Hostname terlanjur dibuat dengan Path `api` yang mengarah ke `localhost:80`, service tetap bisa jalan tanpa mengubah dashboard. Buat file `docker-compose.override.yml` di STB (jangan di-commit) dengan isi berikut, lalu jalankan `docker compose up -d`:

```yaml
services:
  gateway:
    ports: ["127.0.0.1:80:80", "[::1]:80:80"]
```

Seluruh API dan dokumentasi (`/api/docs`) ada di bawah `/api`, jadi tetap terjangkau lewat aturan itu.

### Operasional STB
- Backup: `sh scripts/backup.sh` menyalin database ke `data/backups/` tanpa mematikan service, dan menyimpan 14 backup terakhir. Contoh jadwal cron ada di dalam skrip.
- Cek API publik dan service: `sh scripts/cek-api.sh` (semua hasil harus 200).
- Pantau beban: `docker stats` dan `free -h`.
- Kontrak OpenAPI terbaru: `cd core-service && python scripts/export_openapi.py` menghasilkan `docs/openapi.json` (Postman: Import → File).

## Akun uji dan API key

Akun admin dibuat otomatis dari `ADMIN_EMAIL`/`ADMIN_PASSWORD` di `.env`. Akun yang dibuat lewat CLI langsung terverifikasi.

```bash
docker compose exec core-service python -m app.cli create-user --email wisatawan@bebas.test --name "Uji Wisatawan" --role wisatawan
docker compose exec core-service python -m app.cli create-user --email pengelola@bebas.test --name "Uji Pengelola" --role pengelola
docker compose exec core-service python -m app.cli assign-manager --place-id 1 --user-id 3
docker compose exec core-service python -m app.cli create-api-key --client "K02-nama-kelompok"
docker compose exec core-service python -m app.cli list-api-keys
```
API key hanya tampil sekali saat dibuat. Server hanya menyimpan hash SHA-256-nya. Pengelola yang mendaftar lewat aplikasi harus diverifikasi admin (`PATCH /api/admin/users/{id}/verify`) sebelum bisa mengelola tempat.

## Untuk kelompok lain (kesepakatan integrasi)

| Hal | Ketentuan |
|---|---|
| Base URL | `https://bebas.stei.site/api` |
| Dokumentasi | Swagger `https://bebas.stei.site/api/docs`, kontrak `docs/openapi.json` di repo |
| Auth | Header `X-API-Key` untuk semua `/api/public/*`. Satu kunci per kelompok, bisa dicabut kalau disalahgunakan |
| Cara minta akses | Hubungi admin Bebas (kontak di entri API Registry), sebutkan nama kelompok. Kalian akan menerima API key dan satu akun uji wisatawan |
| Endpoint yang ditawarkan | `places` (paginasi `?page&limit` → `{"data","page","limit","total"}`), `places/{id}`, `places/{id}/crowd`, `places/{id}/visit-forecast`, batch `crowd?ids=` dan `visit-forecast?ids=`, `corridors`, `predict/travel-time`, `predict/departure-window`, `eat-now`, `feed?since=` |
| Tanpa API key | Data non-pribadi juga terbuka tanpa kunci (dibatasi 60/menit per IP): `/api/places`, `/api/places/{id}/crowd`, `/api/crowd?place_ids=`, `/api/visit-forecast?place_ids=`, `/api/corridors`, `/api/feed`. Aplikasi mobile bisa memanggilnya langsung tanpa menyimpan API key di APK |
| Format | JSON, waktu ISO 8601 WIB (`+07:00`), koordinat desimal WGS84, jarak dalam km, durasi dalam menit |
| Batas pemanggilan | 120 panggilan/menit per API key dan 60/menit per IP (burst 20) di gateway. Kalau terlampaui → HTTP 429 dengan header `Retry-After` |
| Kode error | `{"error": "KODE", "message": "..."}`: 401 `UNAUTHORIZED`, 404 `NOT_FOUND`, 422 `VALIDATION_ERROR`, 429 `RATE_LIMITED` |
| Saran untuk pemakai | Pasang timeout ±5 detik dan cache hasil ±5 menit. Data tempat dan koridor jarang berubah |
| Laporan bug | GitHub Issue di repo ini |

Daftar kelompok yang memakai API Bebas, dan API kelompok lain yang dipakai Bebas, akan dicatat di sini saat Tugas 3.

## Integrasi dengan Jelajah Nusantara

Jelajah Nusantara (JN) adalah ekosistem 4 kelompok bertema Tourism: K1 Destination (`jn-destinasi`), K2 Culture & Story (`jn-budaya`), K3 Itinerary & Route (`jn-rute`), dan K4 Ulasan & Reputasi (`jn-ulasan`). Core Bebas tidak memanggil API mereka. Pemanggilan dilakukan di layanan integrasi (Tugas 3) atau di aplikasi, sesuai aturan tugas dan aturan JN.

**Yang disiapkan di core Bebas**

Destinasi K1 bisa masuk itinerary Bebas. Item rencana menerima `external`, yaitu snapshot destinasi milik kelompok lain, sebagai pengganti `place_id`:

```json
{"external": {"destination_id": "dst_12", "name": "Curug Citambur", "lat": -7.2241, "lon": 107.3047,
              "opening_hours": "07:00-16:00", "category": "curug", "captured_at": "2026-11-20T08:00:00Z"}}
```

- `app/planning/external.py` adalah anti-corruption layer-nya. Modul ini menerjemahkan kategori K1 ke kategori Bebas (curug → outdoor, situs sejarah/desa adat → landmark, museum → indoor, kuliner lokal → kuliner), mem-parse jam buka, dan memakai durasi default per kategori. Hasilnya, destinasi K1 dijadwalkan dengan prediksi macet, cuaca, dan jam buka yang sama seperti tempat Bebas.
- Bebas hanya menyimpan ID berprefiks (`dst_`) dan snapshot. Snapshot yang berumur lebih dari 7 hari diberi peringatan "perlu disegarkan".
- Konvensi kontrak JN: endpoint batch (`?ids=`), paginasi `{"data","page","total"}`, error `{"error","message"}`, feed `{"events":[{"seq","type","occurred_at","data"}],"next_since"}`, dan data non-pribadi yang terbuka tanpa API key.
- Perbedaan yang disengaja: waktu ditulis dalam ISO 8601 dengan zona WIB (`+07:00`), bukan UTC. Batas per API key 120/menit (JN memakai 60).

**Rencana pemakaian di Tugas 3 (layanan integrasi Bebas, di luar STB)**

| Penyedia | Endpoint | Dipakai untuk |
|---|---|---|
| K1 Destination | `GET /destinations/nearby`, `/batch`, `/{id}` | Memilih destinasi tersembunyi di sekitar Bandung, membuat snapshot, lalu dijadwalkan oleh core Bebas |
| K4 Ulasan & Reputasi | `GET /ratings/summary?target_type=destination&ids=` | Mengurutkan destinasi dan alternatif berdasarkan rating terverifikasi |
| K2 Culture & Story (opsional) | `GET /stories/summaries?destination_ids=`, `GET /events?from&to` | Cuplikan kisah per stop, peringatan acara budaya di tanggal perjalanan |

Ketahanan: timeout 5 detik, retry 1×, katalog K1 di-cache utuh, dan rating di-cache 5 menit. Kalau API mereka mati, itinerary tetap dibuat dari katalog Bebas dengan pesan "layanan X sedang tidak tersedia".

**Yang ditawarkan Bebas ke JN**: prediksi waktu tempuh per jam dan jendela berangkat untuk koridor Bandung (cocok untuk K3), serta status keramaian dan prediksi kepadatan per tempat (cocok untuk detail destinasi K1).

## Checklist Tugas 2

- [x] Microservice FastAPI + SQLite, Docker dengan `mem_limit` dan `cpus` di setiap kontainer
- [x] Gateway Nginx dengan rate limit, auth JWT + API key (bonus auth & authorization)
- [x] `/api/health`, Swagger `/api/docs`, kontrak `docs/openapi.json`
- [x] Seed 6 koridor dan 33 tempat, tes otomatis (`pytest -q`)
- [ ] Deploy ke STB dan tunnel `https://bebas.stei.site/api/health` menjawab 200
- [ ] Akun admin, akun uji wisatawan dan pengelola, API key per kelompok pemakai
- [ ] Entri API Registry: base URL, link `/docs`, auth `Bearer JWT + X-API-Key`, status Online (batas akhir Minggu 14)
- [ ] README.pdf di repo (`docs/README.pdf`)

## Contoh

```bash
# rencana Sabtu: Farmhouse, Floating Market, Tebing Keraton + makan siang otomatis
curl -X POST https://bebas.stei.site/api/plans -H "Authorization: Bearer $TOKEN" -H 'content-type: application/json' -d '{
  "date": "2026-11-28", "start_time": "08:00", "origin": {"lat": -6.9175, "lon": 107.6191},
  "items": [{"place_id": 1}, {"place_id": 2}, {"place_id": 4}],
  "options": {"insert_lunch": true, "halal_only": true}, "optimize": true}'

# untuk kelompok lain
curl "https://bebas.stei.site/api/public/eat-now?lat=-6.9050&lon=107.6250&halal=true" -H "X-API-Key: bbs_..."
```
Contoh potongan jadwal:
```json
{"position": 3, "kind": "makan_siang", "place_name": "Sentra Kuliner Jalan Raya Lembang", "zone": "utara",
 "arrive_at": "12:39", "start_visit_at": "12:39", "depart_at": "13:39", "travel_confidence": "sedang",
 "queue_status": "antre_panjang", "warnings": ["tiba di jam ramai"]}
```

## Data seed
- `seed/corridors.json`: 6 koridor (Setiabudi-Lembang, Dago-Dago Pakar, Soreang-Ciwidey, Asia Afrika-Braga, Burangrang-Cihapit, Dipati Ukur) dan profil jalan kota. Faktor jam masih perkiraan.
- `seed/places.json`: 33 tempat, terdiri dari 9 outdoor, 6 indoor, 5 landmark, dan 13 kuliner (makanan berat, jajanan, kafe, oleh-oleh, sentra kuliner) di koridor Lembang, Dago Pakar, Ciwidey, dan pusat kota. Semua nilai masih perkiraan dan perlu diverifikasi.
