import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import * as Api from '../services/ApiService';
import { clearToken, clearUser, loadToken, loadUser, saveToken, saveUser } from './storage';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [token, setToken] = useState(null);
  const [user, setUser] = useState(null);
  const [isLoading, setLoading] = useState(true);

  const signOut = useCallback(async () => {
    await Promise.all([clearToken(), clearUser()]);
    setToken(null);
    setUser(null);
  }, []);

  useEffect(() => {
    Api.onUnauthorized(() => signOut());
    (async () => {
      try {
        const saved = await loadToken();
        if (saved) {
          setToken(saved);
          setUser(await loadUser());
          try {
            const profile = await Api.me(saved);
            setUser(profile);
            await saveUser(profile);
          } catch (e) {
            // Hanya token yang ditolak server (401) yang membuat pengguna keluar.
            // Kalau server tidak terjangkau, tetap masuk; tiap layar menampilkan pesan error-nya sendiri.
            if (e.status === 401) await signOut();
          }
        }
      } finally {
        setLoading(false);
      }
    })();
  }, [signOut]);

  const signIn = useCallback(async (email, password) => {
    const res = await Api.login(email.trim(), password);
    await Promise.all([saveToken(res.access_token), saveUser(res.user)]);
    setToken(res.access_token);
    setUser(res.user);
  }, []);

  const signUp = useCallback(
    async (form) => {
      await Api.register(form);
      await signIn(form.email, form.password);
    },
    [signIn],
  );

  const value = useMemo(() => ({ token, user, isLoading, signIn, signUp, signOut }), [token, user, isLoading, signIn, signUp, signOut]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth harus dipakai di dalam AuthProvider');
  return ctx;
}
