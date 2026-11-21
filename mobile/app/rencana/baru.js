import { Ionicons } from '@expo/vector-icons';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import PlaceCard from '../../src/components/PlaceCard';
import { Button, Card, Chip, ErrorState, Loading, Sky, TopBar } from '../../src/components/ui';
import { useAuth } from '../../src/lib/auth';
import { nextDays } from '../../src/lib/format';
import { colors, shadow, space } from '../../src/lib/theme';
import { useAsync } from '../../src/lib/useAsync';
import { validatePlan } from '../../src/lib/validation';
import * as Api from '../../src/services/ApiService';

const ORIGINS = [
  { label: 'Braga', lat: -6.9175, lon: 107.6091 },
  { label: 'Stasiun Bandung', lat: -6.9147, lon: 107.6020 },
  { label: 'ITB Ganesha', lat: -6.8915, lon: 107.6107 },
  { label: 'Lembang', lat: -6.8117, lon: 107.6178 },
];
const TIMES = ['06:00', '07:00', '08:00', '09:00', '10:00'];
const STYLES = [
  { key: 'lunch', label: 'Makan siang', icon: 'restaurant-outline' },
  { key: 'snack', label: 'Jajan sore', icon: 'ice-cream-outline' },
  { key: 'halal', label: 'Halal saja', icon: 'checkmark-circle-outline' },
];
const FILTERS = [
  { key: null, label: 'Semua' },
  { key: 'outdoor', label: 'Alam' },
  { key: 'landmark', label: 'Landmark' },
  { key: 'indoor', label: 'Indoor' },
  { key: 'kuliner', label: 'Kuliner' },
];

export default function RencanaBaruScreen() {
  const router = useRouter();
  const { token } = useAuth();
  const { placeId } = useLocalSearchParams();
  const places = useAsync(() => Api.getPlaces(), []);
  const days = nextDays(14);
  const firstWeekend = days.find((d) => d.weekend) || days[0];

  const [form, setForm] = useState({ title: '', date: firstWeekend.iso, startTime: '08:00', origin: ORIGINS[0], lunch: true, snack: false, halal: false });
  const [selected, setSelected] = useState(placeId ? [Number(placeId)] : []);
  const [filter, setFilter] = useState(null);
  const [errors, setErrors] = useState({});
  const [serverError, setServerError] = useState(null);
  const [busy, setBusy] = useState(false);
  const set = (k) => (v) => setForm((f) => ({ ...f, [k]: v }));
  const toggle = (id) => setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));

  async function submit() {
    const e = validatePlan({ date: form.date, startTime: form.startTime, placeIds: selected });
    setErrors(e);
    setServerError(null);
    if (Object.keys(e).length) return;
    setBusy(true);
    try {
      const plan = await Api.createPlan(token, {
        title: form.title.trim() || 'Jalan-jalan di Bandung',
        date: form.date,
        start_time: form.startTime,
        origin: { lat: form.origin.lat, lon: form.origin.lon },
        items: selected.map((id) => ({ place_id: id })),
        options: { insert_lunch: form.lunch, insert_snack: form.snack, halal_only: form.halal },
        optimize: true,
      });
      router.replace(`/rencana/${plan.id}`);
    } catch (err) {
      setServerError(err.message);
    } finally {
      setBusy(false);
    }
  }

  const list = (places.data || []).filter((p) => !filter || p.category === filter);

  return (
    <Sky>
      <TopBar title="Buat Rencana" />
      <ScrollView contentContainerStyle={{ paddingHorizontal: space(5), paddingBottom: space(10) }} keyboardShouldPersistTaps="handled">
        <Card style={s.titleCard}>
          <Ionicons name="map-outline" size={20} color={colors.blue} />
          <TextInput style={s.titleInput} placeholder="Nama rencana, mis. Sabtu ke Lembang" placeholderTextColor={colors.muted} value={form.title} onChangeText={set('title')} />
        </Card>

        <Card style={{ marginTop: space(4) }}>
          <Text style={s.cardTitle}>Tanggal & jam berangkat</Text>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginTop: space(3), marginHorizontal: -space(1) }}>
            {days.map((d) => {
              const on = d.iso === form.date;
              return (
                <Pressable key={d.iso} onPress={() => set('date')(d.iso)} style={s.day}>
                  <Text style={[s.dayLetter, d.weekend && { color: colors.red }]}>{d.letter}</Text>
                  <View style={[s.dayNum, on && s.dayNumOn]}>
                    <Text style={[s.dayNumText, on && { color: '#fff' }]}>{d.day}</Text>
                  </View>
                </Pressable>
              );
            })}
          </ScrollView>
          {errors.date ? <Text style={s.error}>{errors.date}</Text> : null}
          <View style={[s.wrap, { marginTop: space(3) }]}>
            {TIMES.map((t) => <Chip key={t} label={t} active={form.startTime === t} onPress={() => set('startTime')(t)} />)}
          </View>
          {errors.startTime ? <Text style={s.error}>{errors.startTime}</Text> : null}
        </Card>

        <Card style={{ marginTop: space(4) }}>
          <Text style={s.cardTitle}>Berangkat dari</Text>
          <View style={[s.wrap, { marginTop: space(2) }]}>
            {ORIGINS.map((o) => <Chip key={o.label} label={o.label} icon="location-outline" active={form.origin.label === o.label} onPress={() => set('origin')(o)} />)}
          </View>
        </Card>

        <Card style={{ marginTop: space(4) }}>
          <Text style={s.cardTitle}>Gaya perjalanan</Text>
          <View style={s.styles}>
            {STYLES.map((st) => {
              const on = form[st.key];
              return (
                <Pressable key={st.key} onPress={() => set(st.key)(!on)} style={[s.styleTile, on && s.styleTileOn]}>
                  <View style={[s.styleIcon, on && { backgroundColor: colors.yellow }]}>
                    <Ionicons name={st.icon} size={22} color={colors.text} />
                  </View>
                  <Text style={s.styleText}>{st.label}</Text>
                </Pressable>
              );
            })}
          </View>
        </Card>

        <View style={s.pickHead}>
          <Text style={s.cardTitle}>Mau ke mana saja?</Text>
          <Text style={s.count}>{selected.length} dipilih</Text>
        </View>
        {errors.places ? <Text style={s.error}>{errors.places}</Text> : null}
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginHorizontal: -space(5), marginBottom: space(2) }} contentContainerStyle={{ paddingHorizontal: space(5) }}>
          {FILTERS.map((f) => <Chip key={f.label} label={f.label} active={filter === f.key} onPress={() => setFilter(f.key)} />)}
        </ScrollView>
        {places.loading && !places.data ? (
          <View style={{ height: 160 }}><Loading text="Memuat tempat…" /></View>
        ) : places.error && !places.data ? (
          <View style={{ height: 240 }}><ErrorState error={places.error} onRetry={places.reload} /></View>
        ) : (
          list.map((p) => <PlaceCard key={p.id} place={p} selected={selected.includes(p.id)} onPress={() => toggle(p.id)} />)
        )}

        {serverError ? <Text style={s.serverError}>{serverError}</Text> : null}
      </ScrollView>
      <View style={[s.footer, shadow]}>
        <Button title={selected.length ? `Susun jadwal (${selected.length} tempat)` : 'Susun jadwal'} icon="sparkles-outline" onPress={submit} loading={busy} />
      </View>
    </Sky>
  );
}

const s = StyleSheet.create({
  titleCard: { flexDirection: 'row', alignItems: 'center', gap: space(3), paddingVertical: space(3) },
  titleInput: { flex: 1, fontSize: 15, color: colors.text, paddingVertical: space(1) },
  cardTitle: { fontSize: 16, fontWeight: '700', color: colors.text },
  day: { alignItems: 'center', width: 44, gap: space(1.5) },
  dayLetter: { fontSize: 11, color: colors.muted, fontWeight: '600' },
  dayNum: { width: 36, height: 36, borderRadius: 18, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.bg },
  dayNumOn: { backgroundColor: colors.blue },
  dayNumText: { fontSize: 14, fontWeight: '700', color: colors.text },
  wrap: { flexDirection: 'row', flexWrap: 'wrap' },
  styles: { flexDirection: 'row', gap: space(3), marginTop: space(3) },
  styleTile: { flex: 1, alignItems: 'center', gap: space(2), padding: space(3), borderRadius: 18, borderWidth: 1.5, borderColor: colors.border },
  styleTileOn: { borderColor: colors.yellow, backgroundColor: '#FFFCF2' },
  styleIcon: { width: 46, height: 46, borderRadius: 16, backgroundColor: colors.bg, alignItems: 'center', justifyContent: 'center' },
  styleText: { fontSize: 12, fontWeight: '600', color: colors.text, textAlign: 'center' },
  pickHead: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: space(6), marginBottom: space(2) },
  count: { fontSize: 13, color: colors.blue, fontWeight: '700' },
  error: { color: colors.red, fontSize: 12, marginTop: space(2) },
  serverError: { color: colors.red, backgroundColor: colors.redSoft, padding: space(3), borderRadius: 12, marginTop: space(2) },
  footer: { padding: space(4), paddingBottom: space(6), backgroundColor: colors.card, borderTopLeftRadius: 24, borderTopRightRadius: 24 },
});
