# Xplore Bandung

Aplikasi React Native (Expo SDK 58) dari kelompok Bebas: perencana wisata dan kuliner di Bandung yang memperhitungkan prediksi macet dan cuaca. Aplikasi ini memakai microservice Bebas di `https://bebas.stei.site/api`.

## Menjalankan dengan Expo Go

1. Pasang **Expo Go** di HP (Play Store / App Store).
2. Di laptop (perlu Node.js 20+):
   ```bash
   cd mobile
   npm install
   npx expo start
   ```
3. Scan QR code yang muncul di terminal dengan Expo Go (Android) atau kamera (iPhone). HP dan laptop harus di jaringan Wi-Fi yang sama. Kalau tidak bisa, jalankan `npx expo start --tunnel`.

Versi web untuk dicoba di browser: `npx expo start --web`.

Untuk memakai backend lokal, ganti alamat API saat menjalankan:

```bash
EXPO_PUBLIC_API_URL=http://<ip-laptop>:8000/api npx expo start
```

## Akun demo

Daftar langsung dari layar **Daftar** di aplikasi, atau pakai akun uji wisatawan dari README microservice.

## Struktur

```
mobile/
├── app/                      # layar (Expo Router: setiap file = satu rute)
│   ├── _layout.js            # Stack utama + penjaga login
│   ├── login.js              # Masuk / Daftar
│   ├── (tabs)/               # navigasi tab bawah
│   │   ├── _layout.js
│   │   ├── index.js          # Jelajah
│   │   ├── rencana.js        # Daftar rencana
│   │   ├── makan.js          # Mau makan sekarang
│   │   └── profil.js         # Profil
│   ├── tempat/[id].js        # Detail tempat (stack)
│   └── rencana/
│       ├── baru.js           # Form rencana baru (stack)
│       └── [id].js           # Jadwal (stack)
├── src/
│   ├── services/ApiService.js  # semua pemanggilan API
│   ├── lib/                  # auth (Context), storage token, validasi, format, tema
│   └── components/           # komponen UI, kartu tempat, tab bar melayang
├── docs/screens/             # screenshot tiap layar
└── __tests__/                # unit test Jest
```

## Tes

```bash
npm test
```
