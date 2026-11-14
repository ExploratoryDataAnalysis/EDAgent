import React, { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { User } from '../types';
import { authService } from '../services/api';
import { setUnauthorizedHandler, tokenStore } from '../services/apiClient';

interface AuthContextType {
  user: User | null;
  initialising: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, fullName?: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [initialising, setInitialising] = useState(() => Boolean(tokenStore.get()));

  const logout = useCallback(() => {
    tokenStore.clear();
    localStorage.removeItem('edagent_active_dataset_id');
    localStorage.removeItem('edagent_active_session_id');
    setUser(null);
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(logout);
    return () => setUnauthorizedHandler(null);
  }, [logout]);

  useEffect(() => {
    const token = tokenStore.get();
    if (!token) {
      setInitialising(false);
      return;
    }
    let active = true;
    authService.me()
      .then(user => { if (active && tokenStore.get() === token) setUser(user); })
      .catch(() => { if (active && tokenStore.get() === token) logout(); })
      .finally(() => { if (active) setInitialising(false); });
    return () => { active = false; };
  }, [logout]);

  const login = async (email: string, password: string) => {
    const res = await authService.login(email, password);
    tokenStore.set(res.access_token);
    setUser(res.user);
  };

  const register = async (email: string, password: string, fullName?: string) => {
    const res = await authService.register(email, password, fullName);
    tokenStore.set(res.access_token);
    setUser(res.user);
  };

  return <AuthContext.Provider value={{ user, initialising, login, register, logout }}>{children}</AuthContext.Provider>;
};

export const useAuth = (): AuthContextType => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider');
  return ctx;
};
