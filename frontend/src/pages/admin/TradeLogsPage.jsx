import { useEffect, useState } from 'react';
import { getTradeLogs } from '../../api/admin';
import { TICKERS } from '../../api/prices';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { formatCurrency, formatDateTime, shortId } from '../../utils/format';
import './admin-pages.css';

export function TradeLogsPage() {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({ ticker: '', account_id: '' });

  const load = () => {
    setLoading(true);
    const params = {};
    if (filters.ticker) params.ticker = filters.ticker;
    if (filters.account_id) params.account_id = filters.account_id;
    getTradeLogs(params)
      .then(setLogs)
      .catch(() => setLogs([]))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  return (
    <div className="page-section">
      <div className="page-header">
        <div>
          <h2 style={{ margin: 0 }}>Trade logs</h2>
          <p className="page-subtitle">Executed fills across every trader account.</p>
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
        <Button variant="secondary" onClick={load}>
          Apply filters
        </Button>
      </div>

      <Card>
        {loading ? (
          <div className="loading-row">Loading trade logs…</div>
        ) : logs.length ? (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Account</th>
                  <th>Ticker</th>
                  <th>Fill qty</th>
                  <th>Fill price</th>
                  <th>Notional</th>
                  <th>Fees</th>
                  <th>Order</th>
                  <th>Time</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((t) => (
                  <tr key={t.id}>
                    <td className="font-mono" title={t.account_id}>
                      {t.username || shortId(t.account_id)}
                    </td>
                    <td className="font-mono">{t.ticker}</td>
                    <td className="mono-num">{t.fill_qty ?? '—'}</td>
                    <td className="mono-num">{t.fill_price ? formatCurrency(t.fill_price) : '—'}</td>
                    <td className="mono-num">
                      {t.fill_price && t.fill_qty ? formatCurrency(t.fill_price * t.fill_qty) : '—'}
                    </td>
                    <td className="mono-num">{t.fees != null ? formatCurrency(t.fees) : '—'}</td>
                    <td className="font-mono" title={t.order_id}>
                      {shortId(t.order_id)}
                    </td>
                    <td>{formatDateTime(t.timestamp)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="empty-state">No trade fills match these filters.</div>
        )}
      </Card>
    </div>
  );
}
