import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useState } from 'react';
import { Linking, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Button, Card, Chip, ErrorState, Loading, Pill, PlaceArt, QueueBadge, Sky } from '../../src/components/ui';
import { useAuth } from '../../src/lib/auth';
import { notify } from '../../src/lib/confirm';
import { CATEGORY_LABEL, PRICE } from '../../src/lib/format';
import { colors, shadow, space } from '../../src/lib/theme';
import { useAsync } from '../../src/lib/useAsync';
import * as Api from '../../src/services/ApiService';

const PARKING = { luas: 'Luas', sedang: 'Sedang', terbatas: 'Terbatas', tidak_ada: 'Tidak ada' };
const LEVELS = [
  { v: 1, label: 'Sepi', icon: 'happy-outline' },
  { v: 3, label: 'Ramai', icon: 'people-outline' },
  { v: 5, label: 'Penuh', icon: 'alert-circle-outline' },
];

export default function TempatScreen() {
  const { id } = useLocalSearchParams();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { token } = useAuth();
  const [sending, setSending] = useState(null);

  const { data, loading, error, reload } = useAsync(
    () => Promise.all([Api.getPlace(id), Api.getCrowd(id)]).then(([place, crowd]) => ({ place, crowd })),
    [id],
  );

  async function report(level) {
    setSending(level);
    try {
      const r = await Api.reportCrowd(token, id, level);
      notify('Terima kasih', r.status === 'valid' ? 'Laporanmu sudah dihitung.' : `Laporan ditandai: ${r.reason}`);
      reload();
    } catch (e) {
      notify('Laporan gagal', e.message);
    } finally {
      setSending(null);
    }
  }

  const back = (
    <Pressable accessibilityLabel="Kembali" onPress={() => router.back()} style={[s.roundBtn, shadow]}>
      <Ionicons name="chevron-back" size={20} color={colors.text} />
    </Pressable>
  );

  if (loading && !data) return <Sky><View style={{ paddingTop: insets.top + space(2), paddingLeft: space(4) }}>{back}</View><Loading /></Sky>;
  if (error && !data) return <Sky><View style={{ paddingTop: insets.top + space(2), paddingLeft: space(4) }}>{back}</View><ErrorState error={error} onRetry={reload} /></Sky>;
  const { place: p, crowd } = data;

  return (
    <Sky>
      <ScrollView contentContainerStyle={{ paddingBottom: space(10) }}>
        <PlaceArt
          category={p.category}
          photo={p.photo?.url}
          height={300 + insets.top}
          style={{ borderRadius: 0, borderBottomLeftRadius: 32, borderBottomRightRadius: 32 }}
          iconSize={96}
          iconStyle={{ top: insets.top + 56, right: space(8), bottom: undefined }}
        >
          <LinearGradient colors={['rgba(20,33,46,0.25)', 'transparent', 'rgba(20,33,46,0.6)']} locations={[0, 0.35, 1]} style={s.scrim} />
          <View style={[s.heroBar, { paddingTop: insets.top + space(2) }]}>
            {back}
            <View style={[s.roundBtn, shadow]}>
              <Ionicons name="share-social-outline" size={18} color={colors.text} />
            </View>
          </View>
          <View style={s.heroText}>
            <Pill label={CATEGORY_LABEL[p.category]} tone="yellow" />
            <Text style={s.title}>{p.name}</Text>
            {p.address ? (
              <View style={s.addrRow}>
                <Ionicons name="location-outline" size={14} color="#fff" />
                <Text style={s.addr} numberOfLines={1}>{p.address}</Text>
              </View>
            ) : null}
          </View>
        </PlaceArt>

        <View style={{ padding: space(5), gap: space(4) }}>
          <View style={s.stats}>
            <Stat icon="time-outline" label={p.is_open_now ? 'Buka' : 'Tutup'} value={`${p.open_time}–${p.close_time}`} tone={p.is_open_now ? colors.green : colors.muted} />
            <Stat icon="car-outline" label="Parkir" value={`${PARKING[p.parking?.type] || '-'}${p.parking?.vehicle === 'motor' ? ' · motor' : ''}`} />
            <Stat icon="umbrella-outline" label="Hujan" value={p.rain_friendly ? 'Aman' : 'Kurang cocok'} />
          </View>

          {p.photo ? (
            <Text style={s.credit} onPress={() => p.photo.source && Linking.openURL(p.photo.source)}>
              Foto: {p.photo.credit} · {p.photo.license} · Wikimedia Commons
            </Text>
          ) : null}

          {p.description ? <Text style={s.body}>{p.description}</Text> : null}

          <Card style={{ gap: space(2) }}>
            <View style={s.rowBetween}>
              <Text style={s.section}>Keramaian sekarang</Text>
              <QueueBadge status={crowd.queue_status} />
            </View>
            <Text style={s.muted}>
              {crowd.source === 'perkiraan' ? 'Perkiraan dari jam ramai' : `Dari ${crowd.report_count} laporan pengunjung`}
            </Text>
            {p.peak_hint ? (
              <View style={s.hint}>
                <Ionicons name="bulb-outline" size={16} color={colors.amber} />
                <Text style={s.hintText}>{p.peak_hint}</Text>
              </View>
            ) : null}
            <Text style={[s.label, { marginTop: space(2) }]}>Sedang di sini? Laporkan keramaian</Text>
            <View style={s.wrap}>
              {LEVELS.map((l) => (
                <Chip key={l.v} icon={l.icon} label={sending === l.v ? 'Mengirim…' : l.label} onPress={() => report(l.v)} />
              ))}
            </View>
          </Card>

          <Card style={{ gap: space(2.5) }}>
            <Text style={s.section}>Info lainnya</Text>
            <Info label="Halal" value={p.halal ? 'Ya' : 'Tidak semua menu'} />
            {p.ticket_price ? <Info label="Tiket masuk" value={`Rp${p.ticket_price.toLocaleString('id-ID')}`} /> : <Info label="Tiket masuk" value="Gratis" />}
            {p.price_level ? <Info label="Kisaran harga" value={PRICE(p.price_level)} /> : null}
            {p.signature_menu?.length ? <Info label="Menu andalan" value={p.signature_menu.join(', ')} /> : null}
          </Card>

          <Button title="Tambahkan ke rencana" icon="add-circle-outline" onPress={() => router.push({ pathname: '/rencana/baru', params: { placeId: p.id } })} />
        </View>
      </ScrollView>
    </Sky>
  );
}

function Stat({ icon, label, value, tone = colors.text }) {
  return (
    <View style={[s.stat, shadow]}>
      <Ionicons name={icon} size={18} color={colors.blue} />
      <Text style={[s.statLabel, { color: tone }]}>{label}</Text>
      <Text style={s.statValue} numberOfLines={1}>{value}</Text>
    </View>
  );
}

function Info({ label, value }) {
  return (
    <View style={s.rowBetween}>
      <Text style={s.muted}>{label}</Text>
      <Text style={s.infoValue}>{value}</Text>
    </View>
  );
}

const s = StyleSheet.create({
  scrim: { position: 'absolute', left: 0, right: 0, top: 0, bottom: 0 },
  heroBar: { flexDirection: 'row', justifyContent: 'space-between', paddingHorizontal: space(4) },
  roundBtn: { width: 42, height: 42, borderRadius: 21, backgroundColor: colors.card, alignItems: 'center', justifyContent: 'center' },
  heroText: { position: 'absolute', left: space(5), right: space(5), bottom: space(16), gap: space(2) },
  title: { fontSize: 28, fontWeight: '800', color: '#fff' },
  addrRow: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  addr: { color: '#fff', fontSize: 13, flex: 1 },
  stats: { flexDirection: 'row', gap: space(3), marginTop: -space(12) },
  stat: { flex: 1, backgroundColor: colors.card, borderRadius: 18, padding: space(3), gap: 2 },
  statLabel: { fontSize: 12, fontWeight: '700', marginTop: 4 },
  statValue: { fontSize: 12, color: colors.muted },
  body: { fontSize: 15, color: colors.text, lineHeight: 22 },
  credit: { fontSize: 11, color: colors.muted, marginTop: -space(2) },
  section: { fontSize: 16, fontWeight: '700', color: colors.text },
  muted: { fontSize: 13, color: colors.muted },
  label: { fontSize: 13, fontWeight: '600', color: colors.text },
  rowBetween: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: space(3) },
  wrap: { flexDirection: 'row', flexWrap: 'wrap' },
  hint: { flexDirection: 'row', gap: space(2), backgroundColor: colors.yellowSoft, borderRadius: 14, padding: space(3) },
  hintText: { flex: 1, fontSize: 13, color: colors.text, lineHeight: 19 },
  infoValue: { color: colors.text, fontSize: 14, flexShrink: 1, textAlign: 'right', fontWeight: '500' },
});
