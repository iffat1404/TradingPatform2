import { Outlet, useLocation } from 'react-router-dom';
import { Sidebar } from '../components/common/Sidebar';
import { Topbar } from '../components/common/Topbar';
import { TickerTape } from '../components/common/TickerTape';
import { LevelAlerts } from '../components/common/LevelAlerts';
import { useAuth } from '../context/AuthContext';

const NAV_ITEMS = [
  { to: '/trader/overview', label: 'Overview', icon: 'overview' },
  { to: '/trader/trade', label: 'Trade', icon: 'trade' },
  { to: '/trader/portfolio', label: 'Portfolio', icon: 'portfolio' },
  { to: '/trader/orders', label: 'Orders', icon: 'orders' },
  { to: '/trader/journal', label: 'Journal', icon: 'journal' },
  { to: '/trader/analytics', label: 'Analytics', icon: 'analytics' },
  { to: '/trader/backtesting', label: 'Backtesting', icon: 'backtest' },
  { to: '/trader/ai-assistant', label: 'AI Assistant', icon: 'ai' },
  { to: '/trader/kyc', label: 'KYC', icon: 'kyc' },
  { to: '/trader/settings', label: 'Settings', icon: 'settings' },
];

const TITLES = {
  '/trader/overview': 'Overview',
  '/trader/trade': 'Trade',
  '/trader/portfolio': 'Portfolio',
  '/trader/orders': 'Orders',
  '/trader/journal': 'Trading Journal',
  '/trader/analytics': 'Analytics',
  '/trader/backtesting': 'Backtesting',
  '/trader/ai-assistant': 'AI Assistant',
  '/trader/kyc': 'KYC Verification',
  '/trader/settings': 'Settings',
};

export function TraderLayout() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const title = TITLES[location.pathname] || 'Nomura STP';

  return (
    <div className="theme-dark role-trader dashboard-shell">
      <Sidebar items={NAV_ITEMS} roleLabel="Trader Desk" onLogout={logout} />
      <div className="dashboard-main">
        <Topbar title={title} user={user} />
        <TickerTape />
        <LevelAlerts />
        <div className="dashboard-content">
          <Outlet />
        </div>
      </div>
    </div>
  );
}
