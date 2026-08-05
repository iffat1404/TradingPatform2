import { Outlet, useLocation } from 'react-router-dom';
import { Sidebar } from '../components/common/Sidebar';
import { Topbar } from '../components/common/Topbar';
import { useAuth } from '../context/AuthContext';

const NAV_ITEMS = [
  { to: '/admin/overview', label: 'Overview', icon: 'overview' },
  { to: '/admin/kyc-queue', label: 'KYC Queue', icon: 'kyc-queue' },
  { to: '/admin/accounts', label: 'Accounts', icon: 'accounts' },
  { to: '/admin/audit-logs', label: 'Audit Logs', icon: 'audit' },
  { to: '/admin/trade-logs', label: 'Trade Logs', icon: 'orders' },
  { to: '/admin/compliance', label: 'Compliance', icon: 'compliance' },
  { to: '/admin/feed-control', label: 'Feed & Session', icon: 'feed' },
];

const TITLES = {
  '/admin/overview': 'Admin Overview',
  '/admin/kyc-queue': 'KYC Queue',
  '/admin/accounts': 'Accounts',
  '/admin/audit-logs': 'Audit Logs',
  '/admin/trade-logs': 'Trade Logs',
  '/admin/compliance': 'Compliance Flags',
  '/admin/feed-control': 'Feed & Session Control',
};

export function AdminLayout() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const title = TITLES[location.pathname] || 'Admin Console';

  return (
    <div className="theme-dark role-admin dashboard-shell">
      <Sidebar items={NAV_ITEMS} roleLabel="Admin Console" onLogout={logout} />
      <div className="dashboard-main">
        <Topbar title={title} user={user} />
        <div className="dashboard-content">
          <Outlet />
        </div>
      </div>
    </div>
  );
}
