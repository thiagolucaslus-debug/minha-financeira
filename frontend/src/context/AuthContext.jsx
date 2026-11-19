import React, { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { api, getStoredToken, setStoredToken } from '../api/client';
import { useTheme } from './ThemeContext';

const AuthContext = createContext({
  user: null,
  loading: true,
  login: async () => {},
  register: async () => {},
  logout: () => {},
  refreshUser: async () => {},
  setUser: () => {},
});

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const { setTheme } = useTheme();

  const refreshUser = useCallback(async () => {
    const tok = getStoredToken();
    if (!tok) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      const me = await api.me();
      setUser(me);
      if (me?.tema_preferido) {
        setTheme(me.tema_preferido);
      }
    } catch {
      setStoredToken('');
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, [setTheme]);

  useEffect(() => {
    refreshUser();
  }, [refreshUser]);

  useEffect(() => {
    const onUnauth = () => setUser(null);
    window.addEventListener('mf:unauthorized', onUnauth);
    return () => window.removeEventListener('mf:unauthorized', onUnauth);
  }, []);

  const login = async (username, senha) => {
    const res = await api.login({ username, senha });
    setStoredToken(res.access_token);
    setUser(res.usuario);
    if (res.usuario?.tema_preferido) {
      setTheme(res.usuario.tema_preferido);
    }
    return res.usuario;
  };

  const register = async (nome, username, senha) => {
    const res = await api.register({ nome, username, senha });
    setStoredToken(res.access_token);
    setUser(res.usuario);
    return res.usuario;
  };

  const logout = () => {
    setStoredToken('');
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout, refreshUser, setUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
