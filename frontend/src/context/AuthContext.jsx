import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { getMe, login as loginApi, register as registerApi } from '../api/auth';
import { getToken, setToken, setUnauthorizedHandler } from '../api/client';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [initializing, setInitializing] = useState(true);
  const navigate = useNavigate();

  const clearSession = useCallback(() => {
    setToken(null);
    setUser(null);
  }, []);

  const logout = useCallback(() => {
    clearSession();
    navigate('/login');
  }, [clearSession, navigate]);

  useEffect(() => {
    setUnauthorizedHandler(() => {
      clearSession();
      navigate('/login');
    });
  }, [clearSession, navigate]);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      setInitializing(false);
      return;
    }
    getMe()
      .then(setUser)
      .catch(() => setToken(null))
      .finally(() => setInitializing(false));
  }, []);

  const refreshUser = useCallback(async () => {
    const me = await getMe();
    setUser(me);
    return me;
  }, []);

  const login = useCallback(async (username, password) => {
    const res = await loginApi({ username, password });
    setToken(res.access_token);
    const me = await getMe();
    setUser(me);
    return me;
  }, []);

  const register = useCallback(
    async (payload) => {
      await registerApi(payload);
      return login(payload.username, payload.password);
    },
    [login]
  );

  const value = {
    user,
    role: user?.role ?? null,
    isAuthenticated: Boolean(user),
    initializing,
    login,
    register,
    logout,
    refreshUser,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
