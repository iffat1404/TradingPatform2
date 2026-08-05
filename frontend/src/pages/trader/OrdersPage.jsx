import { useEffect, useState } from 'react';
import { listOrders, cancelOrder, getOrderEvents } from '../../api/orders';
import { explainRejection } from '../../api/genai';
import { TICKERS } from '../../api/prices';
import { Card } from '../../components/common/Card';
import { Modal } from '../../components/common/Modal';
import { ProcessRail, ORDER_STAGES } from '../../components/common/ProcessRail';
import { useToast } from '../../context/ToastContext';
import { formatCurrency, formatDateTime, orderQty } from '../../utils/format';
import { extractErrorMessage } from '../../api/client';
import './trader-pages.css';

const STATUS_OPTIONS = ['NEW', 'VALIDATED', 'ROUTED', 'FILLED', 'REJECTED', 'CANCELLED'];
const OPEN_STATUSES = new Set(['NEW', 'VALIDATED', 'ROUTED']);

export function OrdersPage() {
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('');
  const [tickerFilter, setTickerFilter] = useState('');
  const [activeOrder, setActiveOrder] = useState(null);
  const [events, setEvents] = useState([]);
  const [rejectionNote, setRejectionNote] = useState('');
  const toast = useToast();

  const load = () => {
    setLoading(true);
    const params = {};
    if (statusFilter) params.status = statusFilter;
    if (tickerFilter) params.ticker = tickerFilter;
    listOrders(params)
      .then(setOrders)
      .catch(() => toast.error('Could not load order history.'))
      .finally(() => setLoading(false));
  };

  useEffect(load, [statusFilter, tickerFilter]);

  const openEvents = (order) => {
    setActiveOrder(order);
    setRejectionNote('');
    getOrderEvents(order.id)
      .then(setEvents)
      .catch(() => setEvents([]));
    if (order.status === 'REJECTED') {
      explainRejection(order.id, 'validation_failed')
        .then((res) => setRejectionNote(res.explanation))
        .catch(() => setRejectionNote(''));
    }
  };

  const handleCancel = async (orderId) => {
    try {
      await cancelOrder(orderId);
      toast.info('Order cancelled.');
      load();
    } catch (err) {
      toast.error(extractErrorMessage(err, 'Could not cancel that order.'));
    }
  };

  return (
    <div className="page-section">
      <div className="page-header">
        <div>
          <h2 style={{ margin: 0 }}>Orders</h2>
          <p className="page-subtitle">Every order this account has ever placed, with its full lifecycle.</p>
        </div>
      </div>

      <div className="filters-row">
        <div className="field">
          <label>Status</label>
          <select className="select" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
            <option value="">All statuses</option>
            {STATUS_OPTIONS.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label>Ticker</label>
          <select className="select" value={tickerFilter} onChange={(e) => setTickerFilter(e.target.value)}>
            <option value="">All tickers</option>
            {TICKERS.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </div>
      </div>

      <Card>
        {loading ? (
          <div className="loading-row">Loading orders…</div>
        ) : orders.length ? (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Ticker</th>
                  <th>Side</th>
                  <th>Type</th>
                  <th>Qty</th>
                  <th>Limit</th>
                  <th>Status</th>
                  <th>Created</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {orders.map((o) => (
                  <tr key={o.id} onClick={() => openEvents(o)} style={{ cursor: 'pointer' }}>
                    <td className="font-mono">{o.ticker}</td>
                    <td style={{ textTransform: 'capitalize' }}>{o.side}</td>
                    <td style={{ textTransform: 'capitalize' }}>{o.type}</td>
                    <td className="mono-num">{orderQty(o)}</td>
                    <td className="mono-num">{o.limit_price ? formatCurrency(o.limit_price) : '—'}</td>
                    <td>
                      <ProcessRail status={o.status} />
                    </td>
                    <td>{formatDateTime(o.created_at)}</td>
                    <td onClick={(e) => e.stopPropagation()}>
                      {OPEN_STATUSES.has(o.status) && (
                        <button className="btn btn-danger btn-sm" type="button" onClick={() => handleCancel(o.id)}>
                          Cancel
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="empty-state">No orders match these filters.</div>
        )}
      </Card>

      <Modal open={Boolean(activeOrder)} onClose={() => setActiveOrder(null)} title={`${activeOrder?.ticker} — order trail`}>
        <div style={{ marginBottom: 16 }}>
          <ProcessRail status={activeOrder?.status} />
        </div>
        {events.length ? (
          <ul className="stack" style={{ gap: 10 }}>
            {events.map((ev, i) => {
              // The events endpoint emits from_status/to_status/event_type/notes; other
              // order-event payloads use from_state/to_state/reason. Accept both.
              const from = ev.from_status ?? ev.from_state;
              const to = ev.to_status ?? ev.to_state;
              const detail = ev.event_type ?? ev.reason;
              return (
                <li key={ev.id || i} style={{ fontSize: 13 }}>
                  <span className="font-mono" style={{ color: 'var(--text-muted)' }}>
                    {formatDateTime(ev.timestamp)}
                  </span>{' '}
                  — {from ? `${from} → ` : ''}
                  <strong>{to}</strong>
                  {detail ? <span style={{ color: 'var(--text-muted)' }}> ({detail})</span> : null}
                  {ev.notes ? <span style={{ color: 'var(--text-muted)' }}> {ev.notes}</span> : null}
                </li>
              );
            })}
          </ul>
        ) : (
          <div className="empty-state">No event trail recorded yet.</div>
        )}
        {rejectionNote ? (
          <div className="ai-output" style={{ marginTop: 12 }}>
            <span className="eyebrow">AI explanation</span>
            <p style={{ margin: '6px 0 0' }}>{rejectionNote}</p>
          </div>
        ) : null}
      </Modal>
    </div>
  );
}
