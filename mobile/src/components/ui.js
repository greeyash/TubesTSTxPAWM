import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { useRouter } from 'expo-router';
import { useState } from 'react';
import { ActivityIndicator, Image, Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { CATEGORY_ART, colors, radius, shadow, space } from '../lib/theme';

// Latar langit lembut di belakang setiap layar
export function Sky({ children, style }) {
  return (
    <LinearGradient colors={[colors.skyTop, colors.skyMid, colors.bg]} locations={[0, 0.35, 0.7]} style={[{ flex: 1 }, style]}>
      {children}
    </LinearGradient>
  );
}

// Baris atas untuk layar stack: tombol kembali bulat + judul di tengah
export function TopBar({ title, right }) {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  return (
    <View style={[styles.topBar, { paddingTop: insets.top + space(2) }]}>
      <Pressable accessibilityLabel="Kembali" onPress={() => router.back()} style={[styles.roundBtn, shadow]}>
        <Ionicons name="chevron-back" size={20} color={colors.text} />
      </Pressable>
      <Text style={styles.topTitle} numberOfLines={1}>{title}</Text>
      <View style={styles.roundSlot}>{right}</View>
    </View>
  );
}

export function Button({ title, onPress, variant = 'primary', loading = false, disabled = false, icon, style }) {
  const primary = variant === 'primary';
  return (
    <Pressable
      accessibilityRole="button"
      onPress={onPress}
      disabled={disabled || loading}
      style={({ pressed }) => [
        styles.btn,
        primary ? styles.btnPrimary : styles.btnGhost,
        (disabled || loading) && { opacity: 0.5 },
        pressed && { transform: [{ scale: 0.98 }] },
        style,
      ]}
    >
      {loading ? (
        <ActivityIndicator color={primary ? '#fff' : colors.blue} />
      ) : (
        <View style={styles.btnRow}>
          {icon ? <Ionicons name={icon} size={18} color={primary ? '#fff' : colors.blue} /> : null}
          <Text style={[styles.btnText, !primary && { color: colors.blue }]}>{title}</Text>
        </View>
      )}
    </Pressable>
  );
}

export function Field({ label, error, ...props }) {
  return (
    <View style={{ marginBottom: space(4) }}>
      {label ? <Text style={styles.label}>{label}</Text> : null}
      <TextInput placeholderTextColor={colors.muted} style={[styles.input, error && { borderColor: colors.red }]} {...props} />
      {error ? <Text style={styles.error}>{error}</Text> : null}
    </View>
  );
}

export function SearchBar({ value, onChangeText, onSubmit, placeholder }) {
  return (
    <View style={[styles.search, shadow]}>
      <Ionicons name="search" size={18} color={colors.muted} />
      <TextInput
        style={styles.searchInput}
        value={value}
        onChangeText={onChangeText}
        onSubmitEditing={onSubmit}
        placeholder={placeholder}
        placeholderTextColor={colors.muted}
        returnKeyType="search"
      />
      {value ? (
        <Pressable accessibilityLabel="Hapus pencarian" onPress={() => { onChangeText(''); onSubmit?.(''); }}>
          <Ionicons name="close-circle" size={18} color={colors.muted} />
        </Pressable>
      ) : null}
    </View>
  );
}

export function Chip({ label, active, onPress, icon }) {
  return (
    <Pressable onPress={onPress} style={[styles.chip, active ? styles.chipActive : shadow]}>
      {icon ? <Ionicons name={icon} size={14} color={colors.text} style={{ marginRight: 4 }} /> : null}
      <Text style={[styles.chipText, active && { fontWeight: '700' }]}>{label}</Text>
    </Pressable>
  );
}

export function Card({ children, style }) {
  return <View style={[styles.card, shadow, style]}>{children}</View>;
}

export function SectionHeader({ title, subtitle, action, onAction }) {
  return (
    <View style={styles.section}>
      <View style={{ flex: 1 }}>
        <Text style={styles.sectionTitle}>{title}</Text>
        {subtitle ? <Text style={styles.sectionSub}>{subtitle}</Text> : null}
      </View>
      {action ? <Text style={styles.sectionAction} onPress={onAction}>{action}</Text> : null}
    </View>
  );
}

// Foto tempat (Wikimedia Commons). Kalau tidak ada / gagal dimuat, tampil ilustrasi gradasi + ikon kategori.
export function PlaceArt({ category, height = 120, style, children, iconSize, iconStyle, photo }) {
  const [failed, setFailed] = useState(false);
  const art = CATEGORY_ART[category] || CATEGORY_ART.outdoor;
  const showPhoto = !!photo && !failed;
  return (
    <LinearGradient colors={art.colors} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={[{ height, borderRadius: radius, overflow: 'hidden' }, style]}>
      {showPhoto ? (
        <Image source={{ uri: photo }} style={StyleSheet.absoluteFill} resizeMode="cover" onError={() => setFailed(true)} />
      ) : (
        <>
          <View style={[styles.artBlob, { top: -height * 0.3, right: -height * 0.2, width: height, height }]} />
          <View style={[styles.artBlob, { bottom: -height * 0.45, left: -height * 0.25, width: height * 1.1, height: height * 1.1 }]} />
          <Ionicons name={art.icon} size={iconSize || Math.round(height * 0.38)} color="rgba(255,255,255,0.9)" style={[styles.artIcon, iconStyle]} />
        </>
      )}
      {children}
    </LinearGradient>
  );
}

const QUEUE = {
  sepi: { label: 'Sepi', fg: colors.green, bg: colors.greenSoft },
  sedang: { label: 'Sedang', fg: colors.amber, bg: colors.amberSoft },
  antre_panjang: { label: 'Antre panjang', fg: colors.red, bg: colors.redSoft },
};

export function QueueBadge({ status, solid }) {
  const q = QUEUE[status];
  if (!q) return null;
  return (
    <View style={[styles.badge, { backgroundColor: solid ? '#FFFFFFE6' : q.bg }]}>
      <View style={[styles.badgeDot, { backgroundColor: q.fg }]} />
      <Text style={[styles.badgeText, { color: q.fg }]}>{q.label}</Text>
    </View>
  );
}

export function Pill({ label, tone = 'blue' }) {
  const t = { blue: [colors.blueSoft, colors.blue], yellow: [colors.yellowSoft, colors.amber], green: [colors.greenSoft, colors.green] }[tone];
  return (
    <View style={[styles.badge, { backgroundColor: t[0] }]}>
      <Text style={[styles.badgeText, { color: t[1] }]}>{label}</Text>
    </View>
  );
}

export function Loading({ text = 'Memuat…' }) {
  return (
    <View style={styles.center}>
      <ActivityIndicator color={colors.blue} />
      <Text style={styles.muted}>{text}</Text>
    </View>
  );
}

export function ErrorState({ error, onRetry }) {
  return (
    <View style={styles.center}>
      <View style={[styles.stateIcon, { backgroundColor: colors.redSoft }]}>
        <Ionicons name="cloud-offline-outline" size={26} color={colors.red} />
      </View>
      <Text style={styles.stateTitle}>Gagal memuat data</Text>
      <Text style={[styles.muted, { textAlign: 'center' }]}>{error?.message || 'Terjadi kesalahan.'}</Text>
      {onRetry ? <Button title="Coba lagi" variant="ghost" icon="refresh" onPress={onRetry} style={{ marginTop: space(3) }} /> : null}
    </View>
  );
}

export function EmptyState({ title, text, action, icon = 'compass-outline' }) {
  return (
    <View style={styles.center}>
      <View style={[styles.stateIcon, { backgroundColor: colors.blueSoft }]}>
        <Ionicons name={icon} size={26} color={colors.blue} />
      </View>
      <Text style={styles.stateTitle}>{title}</Text>
      {text ? <Text style={[styles.muted, { textAlign: 'center' }]}>{text}</Text> : null}
      {action}
    </View>
  );
}

export const TAB_BAR_SPACE = 110; // ruang di bawah konten agar tidak tertutup tab bar melayang

export const styles = StyleSheet.create({
  topBar: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: space(4), paddingBottom: space(3) },
  roundBtn: { width: 42, height: 42, borderRadius: 21, backgroundColor: colors.card, alignItems: 'center', justifyContent: 'center' },
  roundSlot: { width: 42, height: 42, alignItems: 'center', justifyContent: 'center' },
  topTitle: { flex: 1, textAlign: 'center', fontSize: 18, fontWeight: '700', color: colors.text },
  btn: { borderRadius: 18, paddingVertical: space(4), paddingHorizontal: space(5), alignItems: 'center' },
  btnRow: { flexDirection: 'row', alignItems: 'center', gap: space(2) },
  btnPrimary: { backgroundColor: colors.blue },
  btnGhost: { backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border },
  btnText: { color: '#fff', fontWeight: '700', fontSize: 15 },
  label: { fontSize: 13, fontWeight: '600', color: colors.text, marginBottom: space(2) },
  input: {
    backgroundColor: colors.card,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 16,
    paddingHorizontal: space(4),
    paddingVertical: space(3.5),
    fontSize: 15,
    color: colors.text,
  },
  error: { color: colors.red, fontSize: 12, marginTop: space(1) },
  search: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space(2),
    backgroundColor: colors.card,
    borderRadius: 999,
    paddingHorizontal: space(4),
    paddingVertical: space(3),
  },
  searchInput: { flex: 1, fontSize: 15, color: colors.text, padding: 0 },
  chip: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: space(4),
    paddingVertical: space(2),
    borderRadius: 999,
    backgroundColor: colors.card,
    marginRight: space(2),
    marginVertical: space(1),
  },
  chipActive: { backgroundColor: colors.yellow },
  chipText: { fontSize: 13, color: colors.text, fontWeight: '500' },
  card: { backgroundColor: colors.card, borderRadius: radius, padding: space(4) },
  section: { flexDirection: 'row', alignItems: 'flex-end', marginTop: space(6), marginBottom: space(3) },
  sectionTitle: { fontSize: 18, fontWeight: '700', color: colors.text },
  sectionSub: { fontSize: 12, color: colors.muted, marginTop: 2 },
  sectionAction: { fontSize: 13, color: colors.blue, fontWeight: '600' },
  artBlob: { position: 'absolute', borderRadius: 999, backgroundColor: 'rgba(255,255,255,0.18)' },
  artIcon: { position: 'absolute', right: '12%', bottom: '14%' },
  badge: { flexDirection: 'row', alignItems: 'center', gap: 5, paddingHorizontal: space(2.5), paddingVertical: space(1), borderRadius: 999, alignSelf: 'flex-start' },
  badgeDot: { width: 6, height: 6, borderRadius: 3 },
  badgeText: { fontSize: 12, fontWeight: '600' },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: space(8), gap: space(2) },
  stateIcon: { width: 56, height: 56, borderRadius: 28, alignItems: 'center', justifyContent: 'center', marginBottom: space(1) },
  muted: { color: colors.muted, fontSize: 14 },
  stateTitle: { fontSize: 16, fontWeight: '700', color: colors.text },
});
