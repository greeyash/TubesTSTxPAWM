#!/bin/sh
# Backup database SQLite tanpa mematikan service. Jalankan di STB dari folder repo:
#   sh scripts/backup.sh
# Jadwalkan harian (crontab -e):
#   0 3 * * * cd /home/<user>/bebas && sh scripts/backup.sh >> data/backups/backup.log 2>&1
set -e
STAMP=$(date +%Y%m%d-%H%M)
mkdir -p data/backups
docker compose exec -T core-service python -c "
import os, sqlite3
src = sqlite3.connect(os.environ.get('DB_PATH', '/app/data/bebas.db'))
dst = sqlite3.connect('/app/data/backups/bebas-$STAMP.db')
src.backup(dst)
dst.close(); src.close()
"
# simpan 14 backup terakhir
ls -1t data/backups/bebas-*.db 2>/dev/null | tail -n +15 | xargs -r rm --
echo "backup selesai: data/backups/bebas-$STAMP.db"
