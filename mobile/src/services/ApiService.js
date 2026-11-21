// Semua pemanggilan ke microservice Bebas lewat satu pintu.
// Error selalu dilempar sebagai ApiError dengan pesan yang bisa ditampilkan ke pengguna.
import { API_URL, REQUEST_TIMEOUT_MS } from '../lib/config';

export class ApiError extends Error {
  constructor(message, { status = 0, code = 'NETWORK_ERROR', details } = {}) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

function buildUrl(path, query) {
  const url = `${API_URL}${path}`;
  if (!query) return url;
  const parts = Object.entries(query)
    .filter(([, v]) => v !== undefined && v !== null && v !== '')
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`);
  return parts.length ? `${url}?${parts.join('&')}` : url;
}

let unauthorizedHandler = null;
export function onUnauthorized(fn) {
  unauthorizedHandler = fn;
}

export async function request(path, { method = 'GET', query, body, token, timeout = REQUEST_TIMEOUT_MS } = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  const headers = { Accept: 'application/json' };
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  if (token) headers.Authorization = `Bearer ${token}`;

  let res;
  try {
    res = await fetch(buildUrl(path, query), {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });
  } catch (e) {
    const aborted = e?.name === 'AbortError';
    throw new ApiError(
      aborted ? 'Server terlalu lama merespons. Coba lagi.' : 'Tidak bisa terhubung ke server. Periksa koneksi internet.',
      { code: aborted ? 'TIMEOUT' : 'NETWORK_ERROR' },
    );
  } finally {
    clearTimeout(timer);
  }

  if (res.status === 204) return null;
  let data = null;
  try {
    data = await res.json();
  } catch {
    data = null;
  }
  if (!res.ok) {
    if (res.status === 401 && token && unauthorizedHandler) unauthorizedHandler();
    const message = data?.message || data?.detail || `Terjadi kesalahan (${res.status}).`;
    throw new ApiError(message, { status: res.status, code: data?.error || `HTTP_${res.status}`, details: data?.details });
  }
  return data;
}

// ---- endpoint ----
export const health = () => request('/health', { timeout: 5000 });

export const login = (email, password) => request('/auth/login', { method: 'POST', body: { email, password } });
export const register = ({ name, email, password, role = 'wisatawan' }) =>
  request('/auth/register', { method: 'POST', body: { name, email, password, role } });
export const me = (token) => request('/auth/me', { token });

export const getPlaces = (filters = {}) => request('/places', { query: filters });
export const getPlace = (id) => request(`/places/${id}`);
export const getCrowd = (id) => request(`/places/${id}/crowd`);
export const getCrowdBatch = (ids) => request('/crowd', { query: { place_ids: ids.join(',') } });
export const reportCrowd = (token, id, level) =>
  request(`/places/${id}/crowd-reports`, { method: 'POST', token, body: { level } });

export const getPlans = (token) => request('/plans', { token });
export const getPlan = (token, id) => request(`/plans/${id}`, { token });
export const createPlan = (token, plan) => request('/plans', { method: 'POST', token, body: plan });
export const deletePlan = (token, id) => request(`/plans/${id}`, { method: 'DELETE', token });
export const reorderPlan = (token, id, options = { strategy: 'optimize' }) =>
  request(`/plans/${id}/reorder`, { method: 'POST', token, body: options });

export const eatNow = (token, { lat, lon, ...filters }) => request('/eat-now', { token, query: { lat, lon, ...filters } });
