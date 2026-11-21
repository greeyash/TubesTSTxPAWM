import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { useFocusEffect, useRouter } from 'expo-router';
import { useCallback } from 'react';
import { Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { EmptyState, ErrorState, Loading, SectionHeader, Sky, TAB_BAR_SPACE } from '../../src/components/ui';
import { useAuth } from '../../src/lib/auth';
import { formatDate } from '../../src/lib/format';
import { colors, shadow, space } from '../../src/lib/theme';
import { useAsync } from '../../src/lib/useAsync';
import * as Api from '../../src/services/ApiService';

export default function RencanaScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { token } = useAuth();
  const { data, loading, error, reload } = useAsync(() => Api.getPlans(token), [token]);

  // muat ulang setiap kali tab ini dibuka lagi (mis. setelah membuat rencana)
  useFocusEffect(useCallback(() => { reload(); }, [reload]));

  return (
    <Sky>
      <ScrollView
        contentContainerStyle={{ paddingTop: insets.top + space(4), paddingHorizontal: space(5), paddingBottom: TAB_BAR_SPACE, flexGrow: 1 }}
        refreshControl={<RefreshControl refreshing={loading && !!data} onRefresh={reload} />}
      >
        <Text style={s.title}>Rencana</Text>
        <Text style={s.sub}>Susun kunjungan satu hari, Xplore Bandung yang hitung jam berangkatnya.</Text>

        <Pressable onPress={() => router.push('/rencana/baru')} style={({ pressed }) => [{ marginTop: space(5) }, pressed && { transform: [{ scale: 0.99 }] }]}>
          <LinearGradient colors={['#5B9BE0', colors.blue]} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={s.cta}>
            <View style={{ flex: 1 }}>
              <Text style={s.ctaTitle}>Buat rencana baru</Text>
              <Text style={s.ctaSub}>Pilih tempat, kami susun urutan dan slot makannya</Text>
            </View>
            <View style={s.ctaIcon}>
              <Ionicons name="add" size={26} color={colors.blue} />
            </View>
          </LinearGradient>
        </Pressable>

        <SectionHeader title="Rencana saya" />
        {loading && !data ? (
          <View style={{ height: 200 }}><Loading text="Memuat rencana…" /></View>
        ) : error && !data ? (
          <View style={{ height: 260 }}><ErrorState error={error} onRetry={reload} /></View>
        ) : data?.length ? (
          data.map((p) => (
            <Pressable key={p.id} onPress={() => router.push(`/rencana/${p.id}`)} style={({ pressed }) => [s.item, shadow, pressed && { transform: [{ scale: 0.99 }] }]}>
              <View style={s.dateBox}>
                <Text style={s.dateDay}>{Number(p.date.slice(8, 10))}</Text>
                <Text style={s.dateMon}>{formatDate(p.date).split(' ')[2]}</Text>
              </View>
              <View style={{ flex: 1, gap: 2 }}>
                <Text style={s.itemTitle} numberOfLines={1}>{p.title}</Text>
                <Text style={s.itemSub}>{formatDate(p.date).split(',')[0]} · mulai {p.start_time}</Text>
                <Text style={s.itemMeta}>{p.item_count} tempat</Text>
              </View>
              <Ionicons name="chevron-forward" size={18} color={colors.muted} />
            </Pressable>
          ))
        ) : (
          <View style={{ height: 220 }}>
            <EmptyState icon="calendar-outline" title="Belum ada rencana" text="Rencana yang kamu buat akan muncul di sini." />
          </View>
        )}
      </ScrollView>
    </Sky>
  );
}

const s = StyleSheet.create({
  title: { fontSize: 30, fontWeight: '800', color: colors.text },
  sub: { fontSize: 14, color: colors.muted, marginTop: space(1), lineHeight: 20 },
  cta: { borderRadius: 24, padding: space(5), flexDirection: 'row', alignItems: 'center', gap: space(3) },
  ctaTitle: { fontSize: 18, fontWeight: '800', color: '#fff' },
  ctaSub: { fontSize: 13, color: '#EAF3FD', marginTop: 4, lineHeight: 18 },
  ctaIcon: { width: 48, height: 48, borderRadius: 16, backgroundColor: '#fff', alignItems: 'center', justifyContent: 'center' },
  item: { flexDirection: 'row', alignItems: 'center', gap: space(3), backgroundColor: colors.card, borderRadius: 22, padding: space(3), paddingRight: space(4), marginBottom: space(3) },
  dateBox: { width: 56, height: 56, borderRadius: 16, backgroundColor: colors.blueSoft, alignItems: 'center', justifyContent: 'center' },
  dateDay: { fontSize: 20, fontWeight: '800', color: colors.blue },
  dateMon: { fontSize: 11, fontWeight: '600', color: colors.blue, marginTop: -2 },
  itemTitle: { fontSize: 15, fontWeight: '700', color: colors.text },
  itemSub: { fontSize: 12, color: colors.muted },
  itemMeta: { fontSize: 12, color: colors.blue, fontWeight: '600' },
});
