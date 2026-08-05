import { Navigate, Route, Routes } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { ToastProvider } from './context/ToastContext';
import { ProtectedRoute } from './components/common/ProtectedRoute';

import { LandingPage } from './pages/landing/LandingPage';
import { LoginPage } from './pages/auth/LoginPage';
import { RegisterPage } from './pages/auth/RegisterPage';

import { TraderLayout } from './layouts/TraderLayout';
import { OverviewPage } from './pages/trader/OverviewPage';
import { TradePage } from './pages/trader/TradePage';
import { PortfolioPage } from './pages/trader/PortfolioPage';
import { OrdersPage } from './pages/trader/OrdersPage';
import { JournalPage } from './pages/trader/JournalPage';
import { AnalyticsPage } from './pages/trader/AnalyticsPage';
import { BacktestingPage } from './pages/trader/BacktestingPage';
import { AIAssistantPage } from './pages/trader/AIAssistantPage';
import { KYCPage } from './pages/trader/KYCPage';
import { SettingsPage } from './pages/trader/SettingsPage';

import { AdminLayout } from './layouts/AdminLayout';
import { AdminOverviewPage } from './pages/admin/AdminOverviewPage';
import { KycQueuePage } from './pages/admin/KycQueuePage';
import { AccountsPage } from './pages/admin/AccountsPage';
import { AuditLogsPage } from './pages/admin/AuditLogsPage';
import { TradeLogsPage } from './pages/admin/TradeLogsPage';
import { CompliancePage } from './pages/admin/CompliancePage';
import { FeedControlPage } from './pages/admin/FeedControlPage';

export default function App() {
  return (
    <AuthProvider>
      <ToastProvider>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />

          <Route element={<ProtectedRoute role="trader" />}>
            <Route path="/trader" element={<TraderLayout />}>
              <Route index element={<Navigate to="overview" replace />} />
              <Route path="overview" element={<OverviewPage />} />
              <Route path="trade" element={<TradePage />} />
              <Route path="portfolio" element={<PortfolioPage />} />
              <Route path="orders" element={<OrdersPage />} />
              <Route path="journal" element={<JournalPage />} />
              <Route path="analytics" element={<AnalyticsPage />} />
              <Route path="backtesting" element={<BacktestingPage />} />
              <Route path="ai-assistant" element={<AIAssistantPage />} />
              <Route path="kyc" element={<KYCPage />} />
              <Route path="settings" element={<SettingsPage />} />
            </Route>
          </Route>

          <Route element={<ProtectedRoute role="admin" />}>
            <Route path="/admin" element={<AdminLayout />}>
              <Route index element={<Navigate to="overview" replace />} />
              <Route path="overview" element={<AdminOverviewPage />} />
              <Route path="kyc-queue" element={<KycQueuePage />} />
              <Route path="accounts" element={<AccountsPage />} />
              <Route path="audit-logs" element={<AuditLogsPage />} />
              <Route path="trade-logs" element={<TradeLogsPage />} />
              <Route path="compliance" element={<CompliancePage />} />
              <Route path="feed-control" element={<FeedControlPage />} />
            </Route>
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </ToastProvider>
    </AuthProvider>
  );
}
