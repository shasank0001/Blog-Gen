import { useState, useEffect } from 'react';
import type { ReactNode } from 'react';
import { api, getMe } from '@/lib/api';
import { AuthContext } from './auth';
import type { User } from './auth';

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(() => localStorage.getItem('token'));
  const [isLoading, setIsLoading] = useState(() => !!localStorage.getItem('token'));

  useEffect(() => {
    const storedToken = localStorage.getItem('token');
    if (!storedToken) return;
    let active = true;
    getMe().then(userData => {
      if (!active) return;
      setUser(userData);
      localStorage.setItem('user', JSON.stringify(userData));
    }).catch(() => {
      if (!active) return;
      setToken(null);
      setUser(null);
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      delete api.defaults.headers.common.Authorization;
    }).finally(() => { if (active) setIsLoading(false); });
    return () => { active = false; };
  }, []);

  const login = (newToken: string, newUser: User) => {
    setToken(newToken);
    setUser(newUser);
    setIsLoading(false);
    localStorage.setItem('token', newToken);
    localStorage.setItem('user', JSON.stringify(newUser));
    api.defaults.headers.common.Authorization = `Bearer ${newToken}`;
  };
  const logout = () => {
    setToken(null);
    setUser(null);
    setIsLoading(false);
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    delete api.defaults.headers.common.Authorization;
  };
  return <AuthContext.Provider value={{ user, token, login, logout, isAuthenticated: !!token && !!user, isLoading }}>
    {children}
  </AuthContext.Provider>;
};
