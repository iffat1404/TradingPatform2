import { useEffect, useMemo, useState } from 'react';
import { getAccounts } from '../../api/admin';
import { Card } from '../../components/common/Card';
import { Badge, kycTone } from '../../components/common/Badge';
import { formatCurrency, formatDateTime } from '../../utils/format';
import './admin-pages.css';

export function AccountsPage() {
  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');

  useEffect(() => {
    getAccounts()
      .then(setAccounts)
      .finally(() => setLoading(false));
  }, []);

  const filtered = useMemo(
    () => accounts.filter((a) => a.username.toLowerCase().includes(search.toLowerCase())),
    [accounts, search]
  );

  return (
    <div className="page-section">
      <div className="page-header">
        <div>
          <h2 style={{ margin: 0 }}>Accounts</h2>
          <p className="page-subtitle">Every trader and admin account on the platform.</p>
        </div>
        <input
          className="input"
          style={{ maxWidth: 240 }}
          placeholder="Search username…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      <Card>
        {loading ? (
          <div className="loading-row">Loading accounts…</div>
        ) : filtered.length ? (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Username</th>
                  <th>Role</th>
                  <th>KYC status</th>
                  <th>Cash balance</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((a) => (
                  <tr key={a.id}>
                    <td>{a.username}</td>
                    <td style={{ textTransform: 'capitalize' }}>{a.role}</td>
                    <td>
                      <Badge tone={kycTone(a.kyc_status)}>{a.kyc_status}</Badge>
                    </td>
                    <td className="mono-num">{formatCurrency(a.cash_balance)}</td>
                    <td>{formatDateTime(a.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="empty-state">No accounts match "{search}".</div>
        )}
      </Card>
    </div>
  );
}
