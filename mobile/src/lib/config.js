import Constants from 'expo-constants';

// Alamat API diambil dari app.json (expo.extra.apiUrl). Untuk mencoba backend lokal,
// jalankan: EXPO_PUBLIC_API_URL=http://<ip-laptop>:8000/api npx expo start
export const API_URL =
  process.env.EXPO_PUBLIC_API_URL ||
  Constants.expoConfig?.extra?.apiUrl ||
  'https://bebas.stei.site/api';

export const REQUEST_TIMEOUT_MS = 10000;
