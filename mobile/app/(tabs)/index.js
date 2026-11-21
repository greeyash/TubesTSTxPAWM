import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useState } from 'react';
import { Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import PlaceCard, { PlaceTile } from '../../src/components/PlaceCard';
import { Chip, EmptyState, ErrorState, Loading, SearchBar, SectionHeader, Sky, TAB_BAR_SPACE } from '../../src/components/ui';
import { useAuth } from '../../src/lib/auth';
import { colors, shadow, space } from '../../src/lib/theme';
import { useAsync } from '../../src/lib/useAsync';
import * as Api from '../../src/services/ApiService';

const CATEGORIES = [
  { key: null, label: 'Semua' },
  { key: 'outdoor', label: 'Alam' },
  { key: 'kuliner', label: 'Kuliner' },
  { key: 'landmark', label: 'Landmark' },
  { key: 'indoor', label: 'Indoor' },
];
const INSIGHTS = [
  { key: 'sepi', label: 'Lagi sepi', icon: 'people', tint: colors.greenSoft, fg: colors.green },
  { key: 'hujan', label: 'Cocok saat hujan', icon: 'umbrella', tint: colors.blueSoft, fg: colors.blue },
  { key: 'malam', label: 'Buka malam', icon: 'moon', tint: colors.yellowSoft, fg: colors.amber },
];

export default function JelajahScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { user } = useAuth();
  const [category, setCategory] = useState(null);
  const [insight, setInsight] = useState(null);
  const [query, setQuery] = useState('');
  const [search, setSearch] = useState('');

  const params = {
    category,
    q: search,
    rain_friendly: insight === 'hujan' ? true : undefined,
    open_late: insight === 'malam' ? true : undefined,
  };
  const { data, loading, error, reload } = useAsync(async () => {
    const places = await Api.getPlaces(params);
    let crowd = {};
    try {
      // status keramaian semua tempat sekaligus (endpoint batch)
      if (places.length) {
        const res = await Api.getCrowdBatch(places.slice(0, 50).map((p) => p.id));
        crowd = Object.fromEntries(res.data.map((c) => [c.place_id, c]));
      }
    } catch {
      crowd = {}; // keramaian opsional: daftar tempat tetap tampil
    }
    return { places, crowd };
  }, [category, search, insight]);

  const filtered = !!(category || search || insight);
  let places = data?.places || [];
  if (insight === 'sepi') places = places.filter((p) => p.is_open_now && data.crowd[p.id]?.queue_status === 'sepi');
  const quiet = (data?.places || []).filter((p) => p.is_open_now && data?.crowd[p.id]?.queue_status === 'sepi').slice(0, 8);
  const firstName = (user?.name || '').split(' ')[0];
  const open = (p) => router.push(`/tempat/${p.id}`);

  return (
    <Sky>
      <ScrollView
        contentContainerStyle={{ paddingTop: insets.top + space(4), paddingHorizontal: space(5), paddingBottom: TAB_BAR_SPACE }}
        refreshControl={<RefreshControl refreshing={loading && !!data} onRefresh={reload} />}
        keyboardShouldPersistTaps="handled"
      >
        <View style={s.headRow}>
          <Text style={s.hello}>Halo{firstName ? `, ${firstName}` : ''} 👋</Text>
          <Pressable onPress={() => router.navigate('/profil')} style={[s.avatar, shadow]}>
            <Text style={s.avatarText}>{(firstName || '?')[0].toUpperCase()}</Text>
          </Pressable>
        </View>
        <Text style={s.title}>Siap jelajah</Text>
        <Text style={s.titleBold}>Bandung?</Text>

        <View style={{ marginTop: space(5) }}>
          <SearchBar
            value={query}
            onChangeText={setQuery}
            onSubmit={(v) => setSearch(typeof v === 'string' ? v : query.trim())}
            placeholder="Cari tempat, kuliner, kawasan…"
          />
        </View>

        <SectionHeader title="Info hari ini" />
        <View style={s.insights}>
          {INSIGHTS.map((it) => {
            const active = insight === it.key;
            return (
              <Pressable key={it.key} onPress={() => setInsight(active ? null : it.key)} style={[s.insight, shadow, active && s.insightActive]}>
                <View style={[s.insightIcon, { backgroundColor: it.tint }]}>
                  <Ionicons name={it.icon} size={20} color={it.fg} />
                </View>
                <Text style={s.insightText}>{it.label}</Text>
              </Pressable>
            );
          })}
        </View>

        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginTop: space(4), marginHorizontal: -space(5) }} contentContainerStyle={{ paddingHorizontal: space(5) }}>
          {CATEGORIES.map((c) => (
            <Chip key={c.label} label={c.label} active={category === c.key} onPress={() => setCategory(c.key)} />
          ))}
        </ScrollView>

        {loading && !data ? (
          <View style={{ height: 240 }}><Loading text="Memuat tempat…" /></View>
        ) : error && !data ? (
          <View style={{ height: 300 }}><ErrorState error={error} onRetry={reload} /></View>
        ) : (
          <>
            {!filtered && quiet.length ? (
              <>
                <SectionHeader title="Lagi sepi sekarang" subtitle="Buka dan belum ramai, berdasarkan laporan dan jam ramai" />
                <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginHorizontal: -space(5) }} contentContainerStyle={{ paddingHorizontal: space(5) }}>
                  {quiet.map((p) => <PlaceTile key={p.id} place={p} crowd={data.crowd[p.id]} onPress={() => open(p)} />)}
                </ScrollView>
              </>
            ) : null}

            <SectionHeader title={filtered ? `${places.length} tempat` : 'Semua tempat'} action={filtered ? 'Reset' : null} onAction={() => { setCategory(null); setInsight(null); setSearch(''); setQuery(''); }} />
            {places.length ? (
              places.map((p) => <PlaceCard key={p.id} place={p} onPress={() => open(p)} />)
            ) : (
              <View style={{ height: 220 }}><EmptyState title="Tidak ada tempat" text="Coba kata kunci atau filter lain." icon="search" /></View>
            )}
          </>
        )}
      </ScrollView>
    </Sky>
  );
}

const s = StyleSheet.create({
  headRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  hello: { fontSize: 15, color: colors.muted },
  avatar: { width: 42, height: 42, borderRadius: 21, backgroundColor: colors.card, alignItems: 'center', justifyContent: 'center' },
  avatarText: { fontSize: 16, fontWeight: '700', color: colors.blue },
  title: { fontSize: 30, color: colors.text, marginTop: space(3) },
  titleBold: { fontSize: 34, fontWeight: '800', color: colors.text, marginTop: -4 },
  insights: { flexDirection: 'row', gap: space(3) },
  insight: { flex: 1, backgroundColor: colors.card, borderRadius: 20, padding: space(3), alignItems: 'center', gap: space(2), borderWidth: 1.5, borderColor: 'transparent' },
  insightActive: { borderColor: colors.yellow, backgroundColor: '#FFFCF2' },
  insightIcon: { width: 44, height: 44, borderRadius: 14, alignItems: 'center', justifyContent: 'center' },
  insightText: { fontSize: 12, fontWeight: '600', color: colors.text, textAlign: 'center' },
});
