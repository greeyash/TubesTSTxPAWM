export const CATEGORY_LABEL = { outdoor: 'Alam', indoor: 'Indoor', landmark: 'Landmark', kuliner: 'Kuliner' };
export const QUEUE_LABEL = { sepi: 'Sepi', sedang: 'Sedang', antre_panjang: 'Antre panjang' };
export const PRICE = (lvl) => (lvl ? 'Rp'.repeat(lvl) : null);

export function todayISO(offsetDays = 0) {
  const d = new Date();
  d.setDate(d.getDate() + offsetDays);
  const local = new Date(d.getTime() - d.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 10);
}

export function nextSaturdayISO() {
  const d = new Date();
  const add = (6 - d.getDay() + 7) % 7 || 7;
  return todayISO(add);
}

export function formatDate(iso) {
  const [y, m, d] = iso.split('-').map(Number);
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des'];
  const days = ['Minggu', 'Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu'];
  const dt = new Date(y, m - 1, d);
  return `${days[dt.getDay()]}, ${d} ${months[m - 1]} ${y}`;
}

// 14 hari ke depan untuk pemilih tanggal
export function nextDays(n = 14) {
  const out = [];
  const letters = ['Min', 'Sen', 'Sel', 'Rab', 'Kam', 'Jum', 'Sab'];
  for (let i = 0; i < n; i++) {
    const d = new Date();
    d.setDate(d.getDate() + i);
    out.push({ iso: todayISO(i), day: d.getDate(), letter: letters[d.getDay()], weekend: d.getDay() === 0 || d.getDay() === 6 });
  }
  return out;
}
