import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';

// Token disimpan di SecureStore (Android/iOS). Web tidak didukung SecureStore, jadi memakai localStorage.
const KEY = 'bebas.token';
const USER_KEY = 'bebas.user';

export async function saveToken(token) {
  if (Platform.OS === 'web') return globalThis.localStorage?.setItem(KEY, token);
  return SecureStore.setItemAsync(KEY, token);
}

export async function loadToken() {
  if (Platform.OS === 'web') return globalThis.localStorage?.getItem(KEY) ?? null;
  return SecureStore.getItemAsync(KEY);
}

export async function clearToken() {
  if (Platform.OS === 'web') return globalThis.localStorage?.removeItem(KEY);
  return SecureStore.deleteItemAsync(KEY);
}

// Profil disimpan juga supaya nama tetap tampil saat server tidak terjangkau.
export async function saveUser(user) {
  const raw = JSON.stringify(user);
  if (Platform.OS === 'web') return globalThis.localStorage?.setItem(USER_KEY, raw);
  return SecureStore.setItemAsync(USER_KEY, raw);
}

export async function loadUser() {
  const raw = Platform.OS === 'web' ? globalThis.localStorage?.getItem(USER_KEY) : await SecureStore.getItemAsync(USER_KEY);
  try {
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export async function clearUser() {
  if (Platform.OS === 'web') return globalThis.localStorage?.removeItem(USER_KEY);
  return SecureStore.deleteItemAsync(USER_KEY);
}
