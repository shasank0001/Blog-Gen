import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '@/context/auth';

export const ProtectedRoute = () => {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) return <p role="status" className="p-8">Restoring your session…</p>;

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <Outlet />;
};
