import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';

export function ProtectedRoute({ role }) {
  const { isAuthenticated, role: userRole, initializing } = useAuth();

  if (initializing) {
    return <div className="loading-row">Loading session…</div>;
  }
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  if (role && userRole !== role) {
    return <Navigate to={userRole === 'admin' ? '/admin/overview' : '/trader/overview'} replace />;
  }
  return <Outlet />;
}
