// Validasi form di sisi aplikasi. Mengembalikan objek { field: pesan }; kosong berarti valid.
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const DATE = /^\d{4}-\d{2}-\d{2}$/;
const TIME = /^([01]\d|2[0-3]):[0-5]\d$/;

export function validateLogin({ email, password }) {
  const e = {};
  if (!email?.trim()) e.email = 'Email wajib diisi';
  else if (!EMAIL.test(email.trim())) e.email = 'Format email tidak valid';
  if (!password) e.password = 'Password wajib diisi';
  return e;
}

export function validateRegister({ name, email, password, confirm }) {
  const e = validateLogin({ email, password });
  if (!name?.trim() || name.trim().length < 2) e.name = 'Nama minimal 2 karakter';
  if (password && password.length < 8) e.password = 'Password minimal 8 karakter';
  if (confirm !== password) e.confirm = 'Konfirmasi password tidak sama';
  return e;
}

// Dihitung dengan UTC supaya hasilnya sama di zona waktu mana pun (WIB = UTC+7).
export function isValidDate(s) {
  if (!DATE.test(s || '')) return false;
  const [y, m, d] = s.split('-').map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d));
  return dt.getUTCFullYear() === y && dt.getUTCMonth() === m - 1 && dt.getUTCDate() === d;
}

function localISO(date) {
  const pad = (n) => String(n).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

export function validatePlan({ date, startTime, placeIds }, today = new Date()) {
  const e = {};
  if (!isValidDate(date)) e.date = 'Tanggal harus berformat YYYY-MM-DD';
  else {
    if (date < localISO(today)) e.date = 'Tanggal tidak boleh di masa lalu';
  }
  if (!TIME.test(startTime || '')) e.startTime = 'Jam mulai harus berformat HH:MM';
  if (!placeIds?.length) e.places = 'Pilih minimal 1 tempat';
  else if (placeIds.length > 8) e.places = 'Maksimal 8 tempat dalam satu hari';
  return e;
}
