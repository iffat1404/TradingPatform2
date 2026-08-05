import { useAuth } from '../../context/AuthContext';
import { Card } from '../../components/common/Card';
import { Badge, kycTone } from '../../components/common/Badge';
import { formatCurrency, formatDateTime } from '../../utils/format';
import './trader-pages.css';

export function SettingsPage() {
  const { user, logout } = useAuth();

  return (
    <div className="page-section">
      <div className="page-header">
        <div>
          <h2 style={{ margin: 0 }}>Settings</h2>
          <p className="page-subtitle">Your account, at a glance.</p>
        </div>
      </div>

      <Card title="Account">
        <div className="stack" style={{ gap: 14 }}>
          <Row label="Username" value={user?.username} />
          <Row label="Role" value={<span style={{ textTransform: 'capitalize' }}>{user?.role}</span>} />
          <Row label="KYC status" value={<Badge tone={kycTone(user?.kyc_status)}>{user?.kyc_status}</Badge>} />
          <Row label="Starting capital" value={formatCurrency(user?.starting_capital)} />
          <Row label="Cash balance" value={formatCurrency(user?.cash_balance)} />
          <Row label="Member since" value={formatDateTime(user?.created_at)} />
        </div>
      </Card>

      <Card title="Session">
        <p className="page-subtitle" style={{ marginBottom: 12 }}>
          Signing out clears your session on this device immediately.
        </p>
        <button className="btn btn-danger" type="button" onClick={logout}>
          Log out
        </button>
      </Card>
    </div>
  );
}

function Row({ label, value }) {
  return (
    <div className="row" style={{ justifyContent: 'space-between', borderBottom: '1px solid var(--border)', paddingBottom: 10 }}>
      <span className="eyebrow">{label}</span>
      <span>{value ?? '—'}</span>
    </div>
  );
}
