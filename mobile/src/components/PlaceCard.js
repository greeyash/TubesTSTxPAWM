import { Ionicons } from '@expo/vector-icons';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { CATEGORY_LABEL, PRICE } from '../lib/format';
import { colors, shadow, space } from '../lib/theme';
import { PlaceArt, QueueBadge } from './ui';

// Baris tempat: ilustrasi kecil di kiri, info di kanan
export default function PlaceCard({ place, onPress, selected }) {
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [s.row, shadow, selected && s.selected, pressed && { transform: [{ scale: 0.99 }] }]}
    >
      <PlaceArt category={place.category} height={76} style={{ width: 76 }} iconSize={28} />
      <View style={s.body}>
        <Text style={s.name} numberOfLines={1}>{place.name}</Text>
        <Text style={s.sub} numberOfLines={1}>{CATEGORY_LABEL[place.category]} · {place.address || place.description}</Text>
        <View style={s.meta}>
          <View style={[s.dot, { backgroundColor: place.is_open_now ? colors.green : colors.muted }]} />
          <Text style={s.metaText}>{place.is_open_now ? 'Buka' : 'Tutup'} · {place.open_time}–{place.close_time}</Text>
          {place.price_level ? <Text style={s.metaText}>· {PRICE(place.price_level)}</Text> : null}
        </View>
      </View>
      {selected !== undefined ? (
        <View style={[s.check, selected && s.checkOn]}>
          {selected ? <Ionicons name="checkmark" size={16} color="#fff" /> : null}
        </View>
      ) : (
        <Ionicons name="chevron-forward" size={18} color={colors.muted} />
      )}
    </Pressable>
  );
}

// Kartu tinggi untuk carousel horizontal
export function PlaceTile({ place, crowd, onPress }) {
  return (
    <Pressable onPress={onPress} style={({ pressed }) => [s.tile, pressed && { transform: [{ scale: 0.98 }] }]}>
      <PlaceArt category={place.category} height={200} style={{ width: 160 }} iconSize={58} iconStyle={{ right: undefined, bottom: undefined, top: 62, left: 51 }}>
        <View style={s.tileTop}>{crowd ? <QueueBadge status={crowd.queue_status} solid /> : null}</View>
        <View style={s.tileBottom}>
          <Text style={s.tileSub} numberOfLines={1}>{CATEGORY_LABEL[place.category]}</Text>
          <Text style={s.tileName} numberOfLines={2}>{place.name}</Text>
        </View>
      </PlaceArt>
    </Pressable>
  );
}

const s = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space(3),
    backgroundColor: colors.card,
    borderRadius: 22,
    padding: space(2.5),
    paddingRight: space(4),
    marginBottom: space(3),
    borderWidth: 1.5,
    borderColor: 'transparent',
  },
  selected: { borderColor: colors.blue, backgroundColor: '#F7FAFE' },
  body: { flex: 1, gap: 3 },
  name: { fontSize: 15, fontWeight: '700', color: colors.text },
  sub: { fontSize: 12, color: colors.muted },
  meta: { flexDirection: 'row', alignItems: 'center', gap: 5, marginTop: 2 },
  dot: { width: 6, height: 6, borderRadius: 3 },
  metaText: { fontSize: 12, color: colors.muted },
  check: { width: 24, height: 24, borderRadius: 12, borderWidth: 1.5, borderColor: colors.border, alignItems: 'center', justifyContent: 'center' },
  checkOn: { backgroundColor: colors.blue, borderColor: colors.blue },
  tile: { marginRight: space(3) },
  tileTop: { padding: space(2.5) },
  tileBottom: { position: 'absolute', left: 0, right: 0, bottom: 0, padding: space(3), backgroundColor: 'rgba(20,33,46,0.22)' },
  tileSub: { fontSize: 11, color: '#fff', opacity: 0.9 },
  tileName: { fontSize: 15, fontWeight: '700', color: '#fff' },
});
