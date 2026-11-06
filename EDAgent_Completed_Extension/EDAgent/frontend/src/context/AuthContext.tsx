import React, { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { User } from '../types';
import { authService } from '../services/api';
import { setUnauthorizedHandler, tokenStore } from '../services/apiClient';

interface AuthContextType {
  user: User | null;
  /** True while the stored token is being validated at start-up. */
  initialising: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, fullName?: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [initialising, setInitialising] = useState<boolean>(!!tokenStore.get());

  const logout = useCallback(() => {
    tokenStore.clear();
    // Per-user UI state must not leak to the next person who signs in on this browser.
    localStorage.removeItem('edagent_active_dataset_id');
    localStorage.removeItem('edagent_active_session_id');
    setUser(null);
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(() => setUser(null));
    return () => setUnauthorizedHandler(null);
  }, []);

  useEffect(() => {
    if (!tokenStore.get()) return;
    authService
      .me()
      .then(setUser)
      .catch(() => tokenStore.clear())
      .finally(() => setInitialising(false));
  }, []);

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
