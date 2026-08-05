import { useEffect, useState } from 'react';
import { getAccounts, getKycQueue, getComplianceFlags, getAuditLogs } from '../../api/admin';
import { Card } from '../../components/common/Card';
import { StatCard } from '../../components/common/StatCard';
import { formatDateTime } from '../../utils/format';
import './admin-pages.css';

export function AdminOverviewPage() {
  const [accounts, setAccounts] = useState([]);
  const [pendingKyc, setPendingKyc] = useState([]);
  const [flags, setFlags] = useState([]);
  const [audit, setAudit] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      getAccounts().catch(() => []),
      getKycQueue('PENDING_REVIEW').catch(() => []),
      getComplianceFlags().catch(() => []),
      getAuditLogs().catch(() => []),
    ])
      .then(([acc, kyc, fl, au]) => {
        setAccounts(acc);
        setPendingKyc(kyc);
        setFlags(fl);
        setAudit(au);
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="loading-row">Loading platform overview…</div>;

  return (
    <div className="page-section">
      <div className="stat-row">
        <StatCard label="Total accounts" value={accounts.length} />
        <StatCard label="Pending KYC" value={pendingKyc.length} />
        <StatCard label="Compliance flags" value={flags.length} />
        <StatCard label="Audit events" value={audit.length} />
      </div>

      <Card title="Recent activity">
        {audit.length ? (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Account</th>
                  <th>Ticker</th>
                  <th>Action</th>
                  <th>Details</th>
                  <th>Time</th>
                </tr>
              </thead>
              <tbody>
                {audit.slice(0, 10).map((ev) => (
                  <tr key={ev.id}>
                    <td className="font-mono">{ev.username || ev.account_id}</td>
                    <td className="font-mono">{ev.ticker || '—'}</td>
                    <td>{ev.action || ev.reason_code}</td>
                    <td>{ev.details || '—'}</td>
                    <td>{formatDateTime(ev.timestamp)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="empty-state">No audit activity recorded yet.</div>
        )}
      </Card>
    </div>
  );
}
