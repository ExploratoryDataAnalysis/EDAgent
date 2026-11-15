import React, { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { User } from '../types';
import { authService } from '../services/api';
import { setUnauthorizedHandler, tokenStore } from '../services/apiClient';

interface AuthContextType {
  user: User | null;
  initialising: boolean;
  guestNotice: string;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, fullName?: string) => Promise<void>;
  logout: () => void;
  startGuest: () => Promise<void>;
  clearGuest: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [initialising, setInitialising] = useState(() => Boolean(tokenStore.get()));
  const [guestNotice, setGuestNotice] = useState('');

  const logout = useCallback(() => {
    const storage = tokenStore.isGuest() ? sessionStorage : localStorage;
    tokenStore.clear();
    storage.removeItem('edagent_active_dataset_id');
    storage.removeItem('edagent_active_session_id');
    setUser(null);
  }, []);

  const endExpired = useCallback(() => {
    if (tokenStore.isGuest()) setGuestNotice('Your private guest session ended. Start a new session to upload again.');
    logout();
  }, [logout]);

  useEffect(() => {
    setUnauthorizedHandler(endExpired);
    return () => setUnauthorizedHandler(null);
  }, [endExpired]);

  useEffect(() => {
    const token = tokenStore.get();
    if (!token) {
      setInitialising(false);
      return;
    }
    let active = true;
    authService.me()
      .then(user => { if (active && tokenStore.get() === token) setUser(user); })
      .catch(() => { if (active && tokenStore.get() === token) endExpired(); })
      .finally(() => { if (active) setInitialising(false); });
    return () => { active = false; };
  }, [endExpired]);

  useEffect(() => {
    if (!user?.guest) return;
    const token = tokenStore.get();
    const expired = () => { if (tokenStore.get() === token) endExpired(); };
    const remaining = Math.max(0, user.guest.expires_at * 1000 - Date.now());
    const timer = window.setTimeout(expired, remaining);
    // A copied tab can retain the credential after another tab clears it.
    const check = () => { if (tokenStore.get() === token) authService.me().catch(() => {}); };
    window.addEventListener('focus', check);
    const poll = window.setInterval(check, 30_000);
    return () => {
      window.clearTimeout(timer);
      window.clearInterval(poll);
      window.removeEventListener('focus', check);
    };
  }, [user, endExpired]);

  const login = async (email: string, password: string) => {
    const res = await authService.login(email, password);
    if (tokenStore.isGuest()) logout();
    setGuestNotice('');
    tokenStore.set(res.access_token);
    setUser(res.user);
  };

  const register = async (email: string, password: string, fullName?: string) => {
    const res = await authService.register(email, password, fullName);
    if (tokenStore.isGuest()) logout();
    setGuestNotice('');
    tokenStore.set(res.access_token);
    setUser(res.user);
  };

  const startGuest = async () => {
    const res = await authService.startGuest();
    sessionStorage.removeItem('edagent_active_dataset_id');
    sessionStorage.removeItem('edagent_active_session_id');
    tokenStore.setGuest(res.access_token);
    setGuestNotice('');
    setUser(res.user);
  };

  const clearGuest = async () => {
    const token = tokenStore.get();
    await authService.clearGuest();
    if (tokenStore.get() !== token) return;
    logout();
    setGuestNotice('Private guest session cleared.');
  };

  return <AuthContext.Provider value={{ user, initialising, guestNotice, login, register, logout, startGuest, clearGuest }}>{children}</AuthContext.Provider>;
};

export const useAuth = (): AuthContextType => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider');
  return ctx;
};
