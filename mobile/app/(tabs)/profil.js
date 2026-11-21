import { Ionicons } from '@expo/vector-icons';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Card, Pill, SectionHeader, Sky, TAB_BAR_SPACE } from '../../src/components/ui';
import { useAuth } from '../../src/lib/auth';
import { API_URL } from '../../src/lib/config';
import { colors, shadow, space } from '../../src/lib/theme';
import { useAsync } from '../../src/lib/useAsync';
import * as Api from '../../src/services/ApiService';

const ROLE = { wisatawan: 'Wisatawan', pengelola: 'Pengelola tempat', admin: 'Admin' };

export default function ProfilScreen() {
  const insets = useSafeAreaInsets();
  const { user, token, signOut } = useAuth();
  const status = useAsync(() => Api.health(), []);
  const plans = useAsync(() => Api.getPlans(token), [token]);

  const planCount = plans.data?.length ?? '–';
  const placeCount = plans.data ? plans.data.reduce((n, p) => n + p.item_count, 0) : '–';
  const upcoming = plans.data ? plans.data.filter((p) => p.date >= new Date().toISOString().slice(0, 10)).length : '–';
  const initials = (user?.name || '?').split(' ').map((w) => w[0]).slice(0, 2).join('').toUpperCase();
  const serverState = status.loading ? ['Memeriksa…', colors.muted] : status.error ? ['Tidak terhubung', colors.red] : ['Terhubung', colors.green];

  return (
    <Sky>
      <ScrollView contentContainerStyle={{ paddingTop: insets.top + space(4), paddingHorizontal: space(5), paddingBottom: TAB_BAR_SPACE }}>
        <Text style={s.header}>Profil</Text>

        <View style={s.profile}>
          <View style={[s.avatar, shadow]}>
            <Text style={s.avatarText}>{initials}</Text>
          </View>
          <Text style={s.name}>{user?.name}</Text>
          <Text style={s.email}>{user?.email}</Text>
          <View style={s.pills}>
            <Pill label={ROLE[user?.role] || user?.role || '-'} tone="yellow" />
            {user?.role === 'pengelola' && !user?.verified ? <Pill label="Menunggu verifikasi" tone="blue" /> : <Pill label="Bandung" tone="blue" />}
          </View>
        </View>

        <View style={s.stats}>
          <Stat value={planCount} label="Rencana" />
          <Stat value={placeCount} label="Tempat" />
          <Stat value={upcoming} label="Akan datang" />
        </View>

        <SectionHeader title="Aplikasi" />
        <Card style={{ padding: 0 }}>
          <Row icon="server-outline" title="Server" subtitle={API_URL} right={<Text style={[s.state, { color: serverState[1] }]}>{serverState[0]}</Text>} onPress={status.reload} />
          <View style={s.sep} />
          <Row icon="information-circle-outline" title="Tentang" subtitle="Xplore Bandung · kelompok Bebas (K02)" />
          <View style={s.sep} />
          <Row icon="log-out-outline" title="Keluar" danger onPress={signOut} />
        </Card>
      </ScrollView>
    </Sky>
  );
}

function Stat({ value, label }) {
  return (
    <View style={s.stat}>
      <Text style={s.statValue}>{value}</Text>
      <Text style={s.statLabel}>{label}</Text>
    </View>
  );
}

function Row({ icon, title, subtitle, right, onPress, danger }) {
  return (
    <Pressable onPress={onPress} disabled={!onPress} style={({ pressed }) => [s.row, pressed && { opacity: 0.7 }]}>
      <View style={[s.rowIcon, danger && { backgroundColor: colors.redSoft }]}>
        <Ionicons name={icon} size={18} color={danger ? colors.red : colors.blue} />
      </View>
      <View style={{ flex: 1 }}>
        <Text style={[s.rowTitle, danger && { color: colors.red }]}>{title}</Text>
        {subtitle ? <Text style={s.rowSub} numberOfLines={1}>{subtitle}</Text> : null}
      </View>
      {right || (onPress ? <Ionicons name="chevron-forward" size={18} color={colors.muted} /> : null)}
    </Pressable>
  );
}

const s = StyleSheet.create({
  header: { fontSize: 18, fontWeight: '700', color: colors.text, textAlign: 'center' },
  profile: { alignItems: 'center', marginTop: space(6), gap: space(1) },
  avatar: { width: 92, height: 92, borderRadius: 32, backgroundColor: colors.card, alignItems: 'center', justifyContent: 'center', marginBottom: space(2) },
  avatarText: { fontSize: 32, fontWeight: '800', color: colors.blue },
  name: { fontSize: 22, fontWeight: '800', color: colors.text },
  email: { fontSize: 13, color: colors.muted },
  pills: { flexDirection: 'row', gap: space(2), marginTop: space(2) },
  stats: { flexDirection: 'row', justifyContent: 'space-around', marginTop: space(6) },
  stat: { alignItems: 'center' },
  statValue: { fontSize: 26, fontWeight: '800', color: colors.text },
  statLabel: { fontSize: 12, color: colors.muted },
  row: { flexDirection: 'row', alignItems: 'center', gap: space(3), padding: space(4) },
  rowIcon: { width: 38, height: 38, borderRadius: 12, backgroundColor: colors.blueSoft, alignItems: 'center', justifyContent: 'center' },
  rowTitle: { fontSize: 15, fontWeight: '600', color: colors.text },
  rowSub: { fontSize: 12, color: colors.muted, marginTop: 2 },
  state: { fontSize: 12, fontWeight: '700' },
  sep: { height: 1, backgroundColor: colors.border, marginLeft: space(16) },
});
