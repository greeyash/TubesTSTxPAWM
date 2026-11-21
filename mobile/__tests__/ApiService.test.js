import * as Api from '../src/services/ApiService';
import { API_URL } from '../src/lib/config';

const json = (status, body) => ({ ok: status < 400, status, json: async () => body });

beforeEach(() => {
  global.fetch = jest.fn();
});

test('getPlaces membangun query dan melewati nilai kosong', async () => {
  fetch.mockResolvedValue(json(200, [{ id: 1 }]));
  const data = await Api.getPlaces({ category: 'kuliner', q: '', halal: true, price_max: undefined });
  expect(data).toEqual([{ id: 1 }]);
  expect(fetch.mock.calls[0][0]).toBe(`${API_URL}/places?category=kuliner&halal=true`);
});

test('login mengirim JSON POST', async () => {
  fetch.mockResolvedValue(json(200, { access_token: 't', user: { id: 1 } }));
  await Api.login('a@b.c', 'rahasia123');
  const [url, opts] = fetch.mock.calls[0];
  expect(url).toBe(`${API_URL}/auth/login`);
  expect(opts.method).toBe('POST');
  expect(JSON.parse(opts.body)).toEqual({ email: 'a@b.c', password: 'rahasia123' });
});

test('token dikirim sebagai Bearer', async () => {
  fetch.mockResolvedValue(json(200, []));
  await Api.getPlans('abc');
  expect(fetch.mock.calls[0][1].headers.Authorization).toBe('Bearer abc');
});

test('error server diubah jadi ApiError dengan pesan dari API', async () => {
  fetch.mockResolvedValue(json(404, { error: 'NOT_FOUND', message: 'tempat tidak ditemukan' }));
  await expect(Api.getPlace(999)).rejects.toMatchObject({
    name: 'ApiError',
    status: 404,
    code: 'NOT_FOUND',
    message: 'tempat tidak ditemukan',
  });
});

test('gagal jaringan menghasilkan pesan yang jelas', async () => {
  fetch.mockRejectedValue(new TypeError('Network request failed'));
  await expect(Api.health()).rejects.toMatchObject({ code: 'NETWORK_ERROR' });
});

test('timeout menghasilkan kode TIMEOUT', async () => {
  fetch.mockImplementation((_url, { signal }) => new Promise((_, reject) => {
    signal.addEventListener('abort', () => reject(Object.assign(new Error('aborted'), { name: 'AbortError' })));
  }));
  await expect(Api.request('/health', { timeout: 10 })).rejects.toMatchObject({ code: 'TIMEOUT' });
});

test('401 dengan token memanggil handler logout', async () => {
  const handler = jest.fn();
  Api.onUnauthorized(handler);
  fetch.mockResolvedValue(json(401, { error: 'UNAUTHORIZED', message: 'token tidak valid' }));
  await expect(Api.getPlans('kedaluwarsa')).rejects.toMatchObject({ status: 401 });
  expect(handler).toHaveBeenCalled();
});

test('204 mengembalikan null', async () => {
  fetch.mockResolvedValue({ ok: true, status: 204, json: async () => { throw new Error('no body'); } });
  await expect(Api.deletePlan('t', 1)).resolves.toBeNull();
});
