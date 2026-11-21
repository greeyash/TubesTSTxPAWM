import { Ionicons } from '@expo/vector-icons';
import { useState } from 'react';
import { KeyboardAvoidingView, Platform, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Button, Card, Chip, Field, Sky } from '../src/components/ui';
import { useAuth } from '../src/lib/auth';
import { colors, space } from '../src/lib/theme';
import { validateLogin, validateRegister } from '../src/lib/validation';

export default function LoginScreen() {
  const insets = useSafeAreaInsets();
  const { signIn, signUp } = useAuth();
  const [mode, setMode] = useState('login');
  const [form, setForm] = useState({ name: '', email: '', password: '', confirm: '', role: 'wisatawan' });
  const [errors, setErrors] = useState({});
  const [serverError, setServerError] = useState(null);
  const [busy, setBusy] = useState(false);
  const isRegister = mode === 'register';

  const set = (key) => (value) => setForm((f) => ({ ...f, [key]: value }));
  const switchMode = (m) => { setMode(m); setErrors({}); setServerError(null); };

  async function submit() {
    const e = isRegister ? validateRegister(form) : validateLogin(form);
    setErrors(e);
    setServerError(null);
    if (Object.keys(e).length) return;
    setBusy(true);
    try {
      if (isRegister) await signUp({ name: form.name.trim(), email: form.email.trim(), password: form.password, role: form.role });
      else await signIn(form.email, form.password);
    } catch (err) {
      setServerError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Sky>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView contentContainerStyle={[s.container, { paddingTop: insets.top + space(14) }]} keyboardShouldPersistTaps="handled">
          <View style={s.logo}>
            <Ionicons name="navigate" size={26} color="#fff" />
          </View>
          <Text style={s.hello}>Siap menjelajah</Text>
          <Text style={s.brand}>Xplore Bandung</Text>
          <Text style={s.tagline}>Tahu kapan berangkat, ke mana dulu, dan makan di mana tanpa terjebak macet.</Text>

          <Card style={{ padding: space(5) }}>
            <View style={s.tabs}>
              <Chip label="Masuk" active={!isRegister} onPress={() => switchMode('login')} />
              <Chip label="Daftar" active={isRegister} onPress={() => switchMode('register')} />
            </View>

            {isRegister && <Field label="Nama" value={form.name} onChangeText={set('name')} error={errors.name} placeholder="Nama lengkap" />}
            <Field
              label="Email"
              value={form.email}
              onChangeText={set('email')}
              error={errors.email}
              placeholder="nama@email.com"
              autoCapitalize="none"
              keyboardType="email-address"
              autoComplete="email"
            />
            <Field
              label="Password"
              value={form.password}
              onChangeText={set('password')}
              error={errors.password}
              placeholder={isRegister ? 'Minimal 8 karakter' : 'Password'}
              secureTextEntry
              returnKeyType={isRegister ? 'next' : 'go'}
              onSubmitEditing={isRegister ? undefined : submit}
            />
            {isRegister && (
              <>
                <Field label="Ulangi password" value={form.confirm} onChangeText={set('confirm')} error={errors.confirm} secureTextEntry returnKeyType="go" onSubmitEditing={submit} />
                <Text style={s.label}>Daftar sebagai</Text>
                <View style={[s.tabs, { marginBottom: space(1) }]}>
                  <Chip label="Wisatawan" icon="walk-outline" active={form.role === 'wisatawan'} onPress={() => set('role')('wisatawan')} />
                  <Chip label="Pengelola tempat" icon="storefront-outline" active={form.role === 'pengelola'} onPress={() => set('role')('pengelola')} />
                </View>
                {form.role === 'pengelola' && <Text style={s.hint}>Akun pengelola perlu diverifikasi admin dulu.</Text>}
              </>
            )}

            {serverError ? <Text style={s.serverError}>{serverError}</Text> : null}
            <Button title={isRegister ? 'Buat akun' : 'Masuk'} onPress={submit} loading={busy} style={{ marginTop: space(1) }} />
          </Card>
        </ScrollView>
      </KeyboardAvoidingView>
    </Sky>
  );
}

const s = StyleSheet.create({
  container: { padding: space(5), flexGrow: 1 },
  logo: { width: 52, height: 52, borderRadius: 18, backgroundColor: colors.blue, alignItems: 'center', justifyContent: 'center', marginBottom: space(5) },
  hello: { fontSize: 22, color: colors.text },
  brand: { fontSize: 34, fontWeight: '800', color: colors.text, marginTop: -2 },
  tagline: { fontSize: 15, color: colors.muted, marginTop: space(2), marginBottom: space(6), lineHeight: 21 },
  tabs: { flexDirection: 'row', marginBottom: space(4) },
  label: { fontSize: 13, fontWeight: '600', color: colors.text, marginBottom: space(1) },
  hint: { fontSize: 12, color: colors.muted, marginBottom: space(3) },
  serverError: { color: colors.red, backgroundColor: colors.redSoft, padding: space(3), borderRadius: 12, marginBottom: space(3) },
});
