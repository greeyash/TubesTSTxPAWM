import { Ionicons } from '@expo/vector-icons';
import { Pressable, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { colors, shadow } from '../lib/theme';

const ICONS = { index: 'home', rencana: 'calendar', makan: 'restaurant', profil: 'person' };

// Tab bar melayang berbentuk kapsul di bawah layar
export default function FloatingTabBar({ state, descriptors, navigation }) {
  const insets = useSafeAreaInsets();
  return (
    <View pointerEvents="box-none" style={[s.wrap, { bottom: Math.max(insets.bottom, 12) + 8 }]}>
      <View style={[s.bar, shadow]}>
        {state.routes.map((route, i) => {
          const focused = state.index === i;
          const { options } = descriptors[route.key];
          const icon = ICONS[route.name] || 'ellipse';
          const onPress = () => {
            const e = navigation.emit({ type: 'tabPress', target: route.key, canPreventDefault: true });
            if (!focused && !e.defaultPrevented) navigation.navigate(route.name);
          };
          return (
            <Pressable
              key={route.key}
              accessibilityRole="tab"
              accessibilityLabel={options.title}
              accessibilityState={{ selected: focused }}
              onPress={onPress}
              style={[s.item, focused && s.itemActive]}
            >
              <Ionicons name={focused ? icon : `${icon}-outline`} size={22} color={focused ? '#fff' : colors.text} />
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
