import { Ionicons } from '@expo/vector-icons';
import { usePathname, useRouter } from 'expo-router';
import { Pressable, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { colors, shadow } from '../lib/theme';

// Daftar tab ditulis langsung (bukan dari props navigator) supaya perilakunya
// sama di iOS, Android, dan web.
const TABS = [
  { href: '/', title: 'Jelajah', icon: 'home' },
  { href: '/rencana', title: 'Rencana', icon: 'calendar' },
  { href: '/makan', title: 'Makan sekarang', icon: 'restaurant' },
  { href: '/profil', title: 'Profil', icon: 'person' },
];

function isActive(pathname, href) {
  if (href === '/') return pathname === '/' || pathname === '';
  return pathname === href || pathname.startsWith(`${href}/`);
}

// Tab bar melayang berbentuk kapsul di bawah layar
export default function FloatingTabBar() {
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const pathname = usePathname() || '/';

  return (
    <View pointerEvents="box-none" style={[s.wrap, { bottom: Math.max(insets.bottom, 12) + 8 }]}>
      <View style={[s.bar, shadow]}>
        {TABS.map((tab) => {
          const focused = isActive(pathname, tab.href);
          return (
            <Pressable
              key={tab.href}
              accessibilityRole="tab"
              accessibilityLabel={tab.title}
              accessibilityState={{ selected: focused }}
              onPress={() => {
                if (!focused) router.navigate(tab.href);
              }}
              style={[s.item, focused && s.itemActive]}
            >
              <Ionicons name={focused ? tab.icon : `${tab.icon}-outline`} size={22} color={focused ? '#fff' : colors.text} />
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

const s = StyleSheet.create({
  wrap: { position: 'absolute', left: 0, right: 0, alignItems: 'center' },
  bar: {
    flexDirection: 'row',
    gap: 6,
    padding: 6,
    borderRadius: 26,
    backgroundColor: 'rgba(255,255,255,0.94)',
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.8)',
  },
  item: { width: 52, height: 46, borderRadius: 20, alignItems: 'center', justifyContent: 'center' },
  itemActive: { backgroundColor: colors.dark },
});
