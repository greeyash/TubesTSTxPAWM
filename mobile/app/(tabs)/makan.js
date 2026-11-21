import { Ionicons } from '@expo/vector-icons';
import { useState } from 'react';
import { RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Chip, EmptyState, ErrorState, Loading, PlaceArt, QueueBadge, SectionHeader, Sky, TAB_BAR_SPACE } from '../../src/components/ui';
import { useAuth } from '../../src/lib/auth';
import { PRICE } from '../../src/lib/format';
import { colors, shadow, space } from '../../src/lib/theme';
import { useAsync } from '../../src/lib/useAsync';
import * as Api from '../../src/services/ApiService';

const AREAS = [
  { label: 'Braga', lat: -6.9175, lon: 107.6091 },
  { label: 'Dago', lat: -6.8855, lon: 107.6135 },
  { label: 'Dipati Ukur', lat: -6.8920, lon: 107.6170 },
  { label: 'Cihapit', lat: -6.9055, lon: 107.6255 },
  { label: 'Lembang', lat: -6.8160, lon: 107.6175 },
];
const TRAFFIC = {
  lancar: { label: 'Jalan lancar', color: colors.green },
  padat: { label: 'Jalan padat', color: colors.amber },
  macet: { label: 'Jalan macet', color: colors.red },
};

export default function MakanScreen() {
  const insets = useSafeAreaInsets();
  const { token } = useAuth();
  const [area, setArea] = useState(AREAS[0]);
  const [halal, setHalal] = useState(false);
  const [cheap, setCheap] = useState(false);
  const [late, setLate] = useState(false);

  const { data, loading, error, reload } = useAsync(
    () => Api.eatNow(token, { lat: area.lat, lon: area.lon, radius_km: 6, halal: halal || undefined, price_max: cheap ? 2 : undefined, open_late: late || undefined }),
    [token, area, halal, cheap, late],
  );

  return (
    <Sky>
      <ScrollView
        contentContainerStyle={{ paddingTop: insets.top + space(4), paddingHorizontal: space(5), paddingBottom: TAB_BAR_SPACE }}
        refreshControl={<RefreshControl refreshing={loading && !!data} onRefresh={reload} />}
      >
        <Text style={s.title}>Mau makan</Text>
        <Text style={s.titleBold}>sekarang?</Text>
        <Text style={s.sub}>Tempat yang buka, dekat, jalannya tidak macet, dan belum antre panjang.</Text>

        <Text style={s.label}>Saya sedang di</Text>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginHorizontal: -space(5) }} contentContainerStyle={{ paddingHorizontal: space(5) }}>
          {AREAS.map((a) => <Chip key={a.label} label={a.label} icon="location-outline" active={area.label === a.label} onPress={() => setArea(a)} />)}
        </ScrollView>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginHorizontal: -space(5), marginTop: space(1) }} contentContainerStyle={{ paddingHorizontal: space(5) }}>
          <Chip label="Halal" active={halal} onPress={() => setHalal(!halal)} />
          <Chip label="Harga terjangkau" active={cheap} onPress={() => setCheap(!cheap)} />
          <Chip label="Buka malam" active={late} onPress={() => setLate(!late)} />
        </ScrollView>

        {loading && !data ? (
          <View style={{ height: 240 }}><Loading text="Mencari tempat makan…" /></View>
        ) : error && !data ? (
          <View style={{ height: 300 }}><ErrorState error={error} onRetry={reload} /></View>
        ) : (
          <>
            <SectionHeader
              title={`${data.results.length} pilihan terdekat`}
              subtitle={data.skipped_long_queue ? `${data.skipped_long_queue} tempat disembunyikan karena dilaporkan antre panjang` : null}
            />
            {data.results.length ? (
              data.results.map((r) => {
                const t = TRAFFIC[r.traffic_status];
                return (
                  <View key={r.place_id} style={[s.card, shadow]}>
                    <PlaceArt category="kuliner" height={86} style={{ width: 86 }} iconSize={30} />
                    <View style={{ flex: 1, gap: 4 }}>
                      <View style={s.rowBetween}>
                        <Text style={s.name} numberOfLines={1}>{r.name}</Text>
                        <QueueBadge status={r.queue_status} />
                      </View>
                      <Text style={s.big}>{Math.round(r.travel_minutes)} menit <Text style={s.km}>· {r.distance_km.toFixed(1)} km</Text></Text>
                      <View style={s.metaRow}>
                        <View style={[s.dot, { backgroundColor: t.color }]} />
                        <Text style={s.meta}>{t.label}</Text>
                        <Text style={s.meta}>· tutup {r.closes_at}</Text>
                        {r.price_level ? <Text style={s.meta}>· {PRICE(r.price_level)}</Text> : null}
                      </View>
                      <View style={s.metaRow}>
                        <Ionicons name={r.parking?.vehicle === 'motor' ? 'bicycle-outline' : 'car-outline'} size={13} color={colors.muted} />
                        <Text style={s.meta}>{r.parking?.vehicle === 'motor' ? 'Parkir motor saja' : 'Parkir muat mobil'}{r.halal ? ' · Halal' : ''}</Text>
                      </View>
                      {r.peak_hint ? <Text style={s.hint}>{r.peak_hint}</Text> : null}
                    </View>
                  </View>
                );
              })
            ) : (
              <View style={{ height: 220 }}><EmptyState icon="restaurant-outline" title="Tidak ada yang cocok" text="Coba area lain atau kurangi filter." /></View>
            )}
          </>
        )}
      </ScrollView>
    </Sky>
  );
}

const s = StyleSheet.create({
  title: { fontSize: 30, color: colors.text },
  titleBold: { fontSize: 34, fontWeight: '800', color: colors.text, marginTop: -4 },
  sub: { fontSize: 14, color: colors.muted, marginTop: space(2), lineHeight: 20 },
  label: { fontSize: 13, fontWeight: '600', color: colors.text, marginTop: space(5), marginBottom: space(1) },
  card: { flexDirection: 'row', gap: space(3), backgroundColor: colors.card, borderRadius: 22, padding: space(2.5), marginBottom: space(3) },
  rowBetween: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: space(2) },
  name: { fontSize: 15, fontWeight: '700', color: colors.text, flex: 1 },
  big: { fontSize: 16, fontWeight: '800', color: colors.text },
  km: { fontSize: 13, fontWeight: '500', color: colors.muted },
  metaRow: { flexDirection: 'row', alignItems: 'center', gap: 4, flexWrap: 'wrap' },
  dot: { width: 6, height: 6, borderRadius: 3 },
  meta: { fontSize: 12, color: colors.muted },
  hint: { fontSize: 12, color: colors.amber, marginTop: 2 },
});
