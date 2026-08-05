import { useEffect, useState } from 'react';
import { getAuditLogs } from '../../api/admin';
import { TICKERS } from '../../api/prices';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { formatDateTime, shortId } from '../../utils/format';
import './admin-pages.css';

export function AuditLogsPage() {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({ ticker: '', account_id: '', reason_code: '' });

  const load = () => {
    setLoading(true);
    const params = {};
    if (filters.ticker) params.ticker = filters.ticker;
    if (filters.account_id) params.account_id = filters.account_id;
    if (filters.reason_code) params.reason_code = filters.reason_code;
    getAuditLogs(params)
      .then(setLogs)
      .catch(() => setLogs([]))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  return (
    <div className="page-section">
      <div className="page-header">
        <div>
          <h2 style={{ margin: 0 }}>Audit logs</h2>
          <p className="page-subtitle">The full order-event audit trail, mandatory per platform principle.</p>
        </div>
      </div>

      <div className="filters-row">
        <div className="field">
          <label>Ticker</label>
          <select className="select" value={filters.ticker} onChange={(e) => setFilters((f) => ({ ...f, ticker: e.target.value }))}>
            <option value="">All</option>
            {TICKERS.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label>Account ID</label>
          <input className="input" value={filters.account_id} onChange={(e) => setFilters((f) => ({ ...f, account_id: e.target.value }))} />
        </div>
        <div className="field">
          <label>Reason code</label>
          <input className="input" value={filters.reason_code} onChange={(e) => setFilters((f) => ({ ...f, reason_code: e.target.value }))} />
        </div>
        <Button variant="secondary" onClick={load}>
          Apply filters
        </Button>
      </div>

      <Card>
        {loading ? (
          <div className="loading-row">Loading audit logs…</div>
        ) : logs.length ? (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Account</th>
                  <th>Order</th>
                  <th>Transition</th>
                  <th>Reason</th>
                  <th>Backtest</th>
                  <th>Time</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((ev) => (
                  <tr key={ev.id}>
                    <td className="font-mono" title={ev.account_id}>
                      {ev.username || shortId(ev.account_id)}
                    </td>
                    <td className="font-mono" title={ev.order_id}>
                      {shortId(ev.order_id)}
                    </td>
                    <td className="font-mono">
                      {ev.from_state ? `${ev.from_state} → ` : ''}
                      {ev.to_state}
                    </td>
                    <td>{ev.reason || '—'}</td>
                    <td>{ev.is_backtest ? 'Yes' : 'No'}</td>
                    <td>{formatDateTime(ev.timestamp)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="empty-state">No audit events match these filters.</div>
        )}
      </Card>
    </div>
  );
}
