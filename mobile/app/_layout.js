import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { Loading, Sky } from '../src/components/ui';
import { AuthProvider, useAuth } from '../src/lib/auth';

export default function RootLayout() {
  return (
    <SafeAreaProvider>
      <AuthProvider>
        <StatusBar style="dark" />
        <RootStack />
      </AuthProvider>
    </SafeAreaProvider>
  );
}

function RootStack() {
  const { token, isLoading } = useAuth();
  if (isLoading) {
    return (
      <Sky>
        <Loading text="Menyiapkan Xplore Bandung…" />
      </Sky>
    );
  }

  return (
    <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: 'transparent' } }}>
      {/* Layar yang butuh login */}
      <Stack.Protected guard={!!token}>
        <Stack.Screen name="(tabs)" />
        <Stack.Screen name="tempat/[id]" />
        <Stack.Screen name="rencana/baru" />
        <Stack.Screen name="rencana/[id]" />
      </Stack.Protected>
      {/* Layar untuk yang belum login */}
      <Stack.Protected guard={!token}>
        <Stack.Screen name="login" />
      </Stack.Protected>
    </Stack>
  );
}
