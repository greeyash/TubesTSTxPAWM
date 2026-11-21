#!/bin/sh
# Cek API publik yang dipakai Bebas dari STB / laptop (hasil harus 200):  sh scripts/cek-api.sh
UA="TugasBesar-TST/1.0 (kelompok-bebas)"
cek() { printf '%-13s' "$1"; curl -gs -m 15 -A "$UA" -o /dev/null -w '%{http_code}\n' "$2"; }
cek Open-Meteo "https://api.open-meteo.com/v1/forecast?latitude=-6.89&longitude=107.61&current=temperature_2m,rain"
cek OSRM       "https://router.project-osrm.org/route/v1/driving/107.60,-6.90;107.62,-6.91?overview=false"
cek Bebas      "${BEBAS_URL:-http://localhost:8080}/api/health"
