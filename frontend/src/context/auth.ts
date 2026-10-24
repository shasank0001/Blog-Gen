import { createContext, useContext } from 'react';

export interface User { id: string; email: string; is_active: boolean }
export interface AuthContextType {
  user: User | null;
  token: string | null;
  login: (token: string, user: User) => void;
  logout: () => void;
  isAuthenticated: boolean;
  isLoading: boolean;
}
export const AuthContext = createContext<AuthContextType | undefined>(undefined);
export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within an AuthProvider');
  return context;
}
