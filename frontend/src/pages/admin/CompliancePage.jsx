import { useEffect, useState } from 'react';
import { getComplianceFlags } from '../../api/admin';
import { Card } from '../../components/common/Card';
import { formatDateTime } from '../../utils/format';
import './admin-pages.css';

export function CompliancePage() {
  const [flags, setFlags] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getComplianceFlags()
      .then(setFlags)
      .catch(() => setFlags([]))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="page-section">
      <div className="page-header">
        <div>
          <h2 style={{ margin: 0 }}>Compliance flags</h2>
          <p className="page-subtitle">Wash-trade patterns and other automated compliance detections.</p>
        </div>
      </div>

      <Card>
        {loading ? (
          <div className="loading-row">Loading compliance flags…</div>
        ) : flags.length ? (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Account</th>
                  <th>Flag type</th>
                  <th>Description</th>
                  <th>Order</th>
                  <th>Time</th>
                </tr>
              </thead>
              <tbody>
                {flags.map((f) => (
                  <tr key={f.id}>
                    <td>{f.username || f.account_id}</td>
                    <td className="badge badge-negative" style={{ display: 'inline-flex' }}>
                      {f.flag_type}
                    </td>
                    <td>{f.description}</td>
                    <td className="font-mono">{f.order_id || '—'}</td>
                    <td>{formatDateTime(f.timestamp)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="empty-state">No compliance flags raised — the book is clean.</div>
        )}
      </Card>
    </div>
  );
}
