import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Button, Card, ErrorState, Loading, PlaceArt, QueueBadge, Sky, TopBar } from '../../src/components/ui';
import { useAuth } from '../../src/lib/auth';
import { confirm, notify } from '../../src/lib/confirm';
import { formatDate } from '../../src/lib/format';
import { colors, shadow, space } from '../../src/lib/theme';
import { useAsync } from '../../src/lib/useAsync';
import * as Api from '../../src/services/ApiService';

const KIND = { makan_siang: 'Makan siang', jajan_sore: 'Jajan sore' };
const REASON = { hujan: 'hujan', antre_panjang: 'antre panjang', tutup: 'tutup' };

export default function JadwalScreen() {
  const { id } = useLocalSearchParams();
  const router = useRouter();
  const { token } = useAuth();
  const { data: plan, loading, error, reload } = useAsync(() => Api.getPlan(token, id), [id, token]);
  const [busy, setBusy] = useState(null);

  async function reorder(apply) {
    setBusy(apply ? 'alt' : 'order');
    try {
      const r = await Api.reorderPlan(token, id, { strategy: 'optimize', apply_alternatives: apply });
      notify(r.changed ? 'Jadwal diperbarui' : 'Tidak ada perubahan', r.reasons.join('\n'));
      reload();
    } catch (e) {
      notify('Gagal menyusun ulang', e.message);
    } finally {
      setBusy(null);
    }
  }

  async function remove() {
    if (!(await confirm('Hapus rencana?', 'Rencana ini akan dihapus permanen.'))) return;
    try {
      await Api.deletePlan(token, id);
      router.back();
    } catch (e) {
      notify('Gagal menghapus', e.message);
    }
  }

  const trash = (
    <Pressable accessibilityLabel="Hapus rencana" onPress={remove} style={[s.roundBtn, shadow]}>
      <Ionicons name="trash-outline" size={18} color={colors.red} />
    </Pressable>
  );

  if (loading && !plan) return <Sky><TopBar title="Jadwal" /><Loading text="Menghitung jadwal…" /></Sky>;
  if (error && !plan) return <Sky><TopBar title="Jadwal" /><ErrorState error={error} onRetry={reload} /></Sky>;
  const sum = plan.summary;

  return (
    <Sky>
      <TopBar title="Jadwal" right={trash} />
      <ScrollView contentContainerStyle={{ paddingHorizontal: space(5), paddingBottom: space(10), gap: space(4) }}>
        <LinearGradient colors={['#5B9BE0', colors.blue]} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={s.hero}>
          <Text style={s.heroTitle} numberOfLines={1}>{plan.title}</Text>
          <Text style={s.heroDate}>{formatDate(plan.date)}</Text>
          <View style={s.heroRow}>
            <View>
              <Text style={s.heroLabel}>Berangkat</Text>
              <Text style={s.heroBig}>{plan.departure.recommended_start}</Text>
            </View>
            <View style={s.heroDivider} />
            <View>
              <Text style={s.heroLabel}>Selesai</Text>
              <Text style={s.heroBig}>{sum.end_at}</Text>
            </View>
            <View style={s.heroDivider} />
            <View>
              <Text style={s.heroLabel}>Di jalan</Text>
              <Text style={s.heroBig}>{Math.round(sum.total_travel_minutes)}m</Text>
            </View>
          </View>
          <Text style={s.heroNote}>{plan.departure.note}</Text>
        </LinearGradient>

        {plan.warnings.map((w) => (
          <View key={w} style={s.warn}>
            <Ionicons name="warning-outline" size={18} color={colors.amber} />
            <Text style={s.warnText}>{w}</Text>
          </View>
        ))}

        <View>
          {plan.schedule.map((st, i) => (
            <View key={st.item_id} style={s.stop}>
              <View style={s.timeCol}>
                <Text style={s.time}>{st.start_visit_at}</Text>
                <Text style={s.timeEnd}>{st.depart_at}</Text>
              </View>
              <View style={s.line}>
                <View style={[s.dot, st.kind !== 'kunjungan' && { backgroundColor: colors.yellow }]} />
                {i < plan.schedule.length - 1 ? <View style={s.bar} /> : null}
              </View>
              <View style={s.stopBody}>
                <View style={s.travel}>
                  <Ionicons name="car-outline" size={13} color={colors.muted} />
                  <Text style={s.travelText}>{Math.round(st.travel_minutes)} menit · keyakinan {st.travel_confidence}</Text>
                </View>
                <View style={[s.stopCard, shadow]}>
                  <PlaceArt category={st.category} height={56} style={{ width: 56, borderRadius: 16 }} iconSize={22} />
                  <View style={{ flex: 1, gap: 4 }}>
                    {KIND[st.kind] ? <Text style={s.kind}>{KIND[st.kind]}</Text> : null}
                    <Text style={s.name} numberOfLines={2}>{st.place_name}</Text>
                    <QueueBadge status={st.queue_status} />
                    {st.warnings.map((w) => <Text key={w} style={s.stopWarn}>• {w}</Text>)}
                  </View>
                </View>
              </View>
            </View>
          ))}
        </View>

        {plan.suggestions.length ? (
          <Card style={{ gap: space(2) }}>
            <Text style={s.section}>Saran pengganti</Text>
            {plan.suggestions.map((sg) => (
              <Text key={sg.item_id} style={s.body}>
                <Text style={{ fontWeight: '700' }}>{sg.place_name}</Text> ({REASON[sg.reason]}):{' '}
                {sg.alternatives.length ? sg.alternatives.map((a) => a.name).join(', ') : 'belum ada alternatif searah'}
              </Text>
            ))}
            <Button title="Ganti dengan alternatif" variant="ghost" icon="swap-horizontal" loading={busy === 'alt'} onPress={() => reorder(true)} />
          </Card>
        ) : null}

        <Button title="Susun ulang urutan" icon="shuffle" loading={busy === 'order'} onPress={() => reorder(false)} />
      </ScrollView>
    </Sky>
  );
}

const s = StyleSheet.create({
  roundBtn: { width: 42, height: 42, borderRadius: 21, backgroundColor: colors.card, alignItems: 'center', justifyContent: 'center' },
  hero: { borderRadius: 26, padding: space(5), gap: space(1) },
  heroTitle: { fontSize: 20, fontWeight: '800', color: '#fff' },
  heroDate: { fontSize: 13, color: '#EAF3FD' },
  heroRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: space(4), marginBottom: space(2) },
  heroLabel: { fontSize: 12, color: '#D6E7FA' },
  heroBig: { fontSize: 24, fontWeight: '800', color: '#fff' },
  heroDivider: { width: 1, height: 34, backgroundColor: 'rgba(255,255,255,0.35)' },
  heroNote: { fontSize: 12, color: '#EAF3FD', lineHeight: 17 },
  warn: { flexDirection: 'row', gap: space(2), backgroundColor: colors.amberSoft, borderRadius: 16, padding: space(3) },
  warnText: { flex: 1, color: colors.text, fontSize: 13, lineHeight: 19 },
  stop: { flexDirection: 'row' },
  timeCol: { width: 50, paddingTop: space(7) },
  time: { fontSize: 15, fontWeight: '800', color: colors.text },
  timeEnd: { fontSize: 12, color: colors.muted },
  line: { width: 18, alignItems: 'center', paddingTop: space(8) },
  dot: { width: 12, height: 12, borderRadius: 6, backgroundColor: colors.blue, borderWidth: 2, borderColor: '#fff' },
  bar: { flex: 1, width: 2, backgroundColor: colors.border, marginTop: space(1) },
  stopBody: { flex: 1, paddingBottom: space(3) },
  travel: { flexDirection: 'row', alignItems: 'center', gap: 4, marginBottom: space(1.5) },
  travelText: { fontSize: 12, color: colors.muted },
  stopCard: { flexDirection: 'row', gap: space(3), backgroundColor: colors.card, borderRadius: 20, padding: space(3) },
  kind: { fontSize: 11, fontWeight: '800', color: colors.amber, textTransform: 'uppercase', letterSpacing: 0.5 },
  name: { fontSize: 15, fontWeight: '700', color: colors.text },
  stopWarn: { fontSize: 12, color: colors.muted },
  section: { fontSize: 16, fontWeight: '700', color: colors.text },
  body: { fontSize: 14, color: colors.text, lineHeight: 20 },
});
