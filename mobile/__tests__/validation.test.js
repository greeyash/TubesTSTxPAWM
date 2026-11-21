import { isValidDate, validateLogin, validatePlan, validateRegister } from '../src/lib/validation';

test('login: email dan password wajib', () => {
  expect(validateLogin({ email: '', password: '' })).toEqual({ email: 'Email wajib diisi', password: 'Password wajib diisi' });
  expect(validateLogin({ email: 'bukan-email', password: 'x' }).email).toBe('Format email tidak valid');
  expect(validateLogin({ email: 'a@b.co', password: 'x' })).toEqual({});
});

test('daftar: nama, panjang password, konfirmasi', () => {
  const e = validateRegister({ name: 'A', email: 'a@b.co', password: 'pendek', confirm: 'lain' });
  expect(e.name).toBeDefined();
  expect(e.password).toBe('Password minimal 8 karakter');
  expect(e.confirm).toBe('Konfirmasi password tidak sama');
  expect(validateRegister({ name: 'Ani', email: 'a@b.co', password: 'panjang123', confirm: 'panjang123' })).toEqual({});
});

test('tanggal valid', () => {
  expect(isValidDate('2026-11-28')).toBe(true);
  expect(isValidDate('2026-02-30')).toBe(false);
  expect(isValidDate('28-11-2026')).toBe(false);
});

test('rencana: tanggal, jam, jumlah tempat', () => {
  const today = new Date(2026, 10, 21, 9, 0); // 21 Nov 2026 pukul 09.00 waktu lokal
  expect(validatePlan({ date: '2026-11-20', startTime: '08:00', placeIds: [1] }, today).date).toBe('Tanggal tidak boleh di masa lalu');
  expect(validatePlan({ date: '2026-11-28', startTime: '8 pagi', placeIds: [1] }, today).startTime).toBeDefined();
  expect(validatePlan({ date: '2026-11-28', startTime: '08:00', placeIds: [] }, today).places).toBe('Pilih minimal 1 tempat');
  expect(validatePlan({ date: '2026-11-28', startTime: '08:00', placeIds: [1, 2] }, today)).toEqual({});
});
