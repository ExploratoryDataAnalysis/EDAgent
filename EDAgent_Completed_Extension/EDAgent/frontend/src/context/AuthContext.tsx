import React, { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { User } from '../types';
import { authService } from '../services/api';
import { apiClient, setUnauthorizedHandler, tokenStore } from '../services/apiClient';

export const DEFAULT_OPEN_USER: User = {
  id: 'f61c13bc-4cb0-4e0f-bab2-2bd4564ef094',
  email: 'analyst@edagent.local',
  full_name: 'Lead Analyst',
  is_active: true,
};

interface AuthContextType {
  user: User;
  initialising: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, fullName?: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User>(DEFAULT_OPEN_USER);
  const [initialising, setInitialising] = useState<boolean>(false);

  const logout = useCallback(() => {
    tokenStore.clear();
    localStorage.removeItem('edagent_active_dataset_id');
    localStorage.removeItem('edagent_active_session_id');
    setUser(DEFAULT_OPEN_USER);
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(() => setUser(DEFAULT_OPEN_USER));
    return () => setUnauthorizedHandler(null);
  }, []);

  useEffect(() => {
    const token = tokenStore.get();
    if (token) {
      authService
        .me()
        .then(setUser)
        .catch(() => {
          tokenStore.clear();
          setUser(DEFAULT_OPEN_USER);
        });
    } else {
      apiClient
        .post<{ data: { access_token: string; user: User } }>('/auth/guest')
        .then((res) => {
          if (res.data?.data?.access_token) {
            tokenStore.set(res.data.data.access_token);
            if (res.data.data.user) setUser(res.data.data.user);
          }
        })
        .catch(() => {
          // Open access without token is supported by backend
        });
    }
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
