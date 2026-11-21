import { Tabs } from 'expo-router';
import FloatingTabBar from '../../src/components/FloatingTabBar';

export default function TabLayout() {
  return (
    <Tabs tabBar={() => <FloatingTabBar />} screenOptions={{ headerShown: false }}>
      <Tabs.Screen name="index" options={{ title: 'Jelajah' }} />
      <Tabs.Screen name="rencana" options={{ title: 'Rencana' }} />
      <Tabs.Screen name="makan" options={{ title: 'Makan sekarang' }} />
      <Tabs.Screen name="profil" options={{ title: 'Profil' }} />
    </Tabs>
  );
}
