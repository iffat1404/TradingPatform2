import { useEffect, useState } from 'react';
import { listOrders, cancelOrder, getOrderEvents } from '../../api/orders';
import { explainRejection } from '../../api/genai';
import { updateOrderLevels } from '../../api/decision';
import { TICKERS } from '../../api/prices';
import { Card } from '../../components/common/Card';
import { Modal } from '../../components/common/Modal';
import { Field } from '../../components/common/Field';
import { Button } from '../../components/common/Button';
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
  const [planOrder, setPlanOrder] = useState(null);
  const [planForm, setPlanForm] = useState({ target: '', stop: '' });
  const [savingPlan, setSavingPlan] = useState(false);
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
      explainRejection(order.id)
        .then((res) => setRejectionNote(res.explanation))
        .catch(() => setRejectionNote(''));
    }
  };

  const openPlan = (order) => {
    setPlanOrder(order);
    setPlanForm({
      target: order.target_price ?? '',
      stop: order.stop_loss ?? '',
    });
  };

  const handleSavePlan = async () => {
    const target = planForm.target === '' ? null : Number(planForm.target);
    const stop = planForm.stop === '' ? null : Number(planForm.stop);
    if (target === null && stop === null) {
      toast.error('Set a target or a stop to save.');
      return;
    }
    setSavingPlan(true);
    try {
      const res = await updateOrderLevels(planOrder.id, {
        ...(target !== null ? { target_price: target } : {}),
        ...(stop !== null ? { stop_loss: stop } : {}),
      });
      // The backend only records an event when a value actually changes, so say which it was.
      if (res.changed) {
        toast.success(`Plan updated: ${res.changes.join('; ')}`);
      } else {
        toast.info('No change — those are already the current levels.');
      }
      setPlanOrder(null);
      load();
    } catch (err) {
      toast.error(extractErrorMessage(err, 'Could not update the plan.'));
    } finally {
      setSavingPlan(false);
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
                  <th>Plan (target / stop)</th>
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
                    <td className="mono-num">
                      {o.target_price || o.stop_loss
                        ? `${o.target_price ? formatCurrency(o.target_price) : '—'} / ${
                            o.stop_loss ? formatCurrency(o.stop_loss) : '—'
                          }`
                        : 'no plan'}
                    </td>
                    <td>
                      <ProcessRail status={o.status} />
                    </td>
                    <td>{formatDateTime(o.created_at)}</td>
                    <td onClick={(e) => e.stopPropagation()}>
                      <div className="row" style={{ gap: 6 }}>
                        <button className="btn btn-ghost btn-sm" type="button" onClick={() => openPlan(o)}>
                          Adjust plan
                        </button>
                        {OPEN_STATUSES.has(o.status) && (
                          <button className="btn btn-danger btn-sm" type="button" onClick={() => handleCancel(o.id)}>
                            Cancel
                          </button>
                        )}
                      </div>
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

      <Modal
        open={Boolean(planOrder)}
        onClose={() => setPlanOrder(null)}
        title={`${planOrder?.ticker} — adjust trade plan`}
      >
        <div className="stack" style={{ gap: 16 }}>
          <p className="field-hint" style={{ margin: 0 }}>
            These levels are a record of your intent — nothing auto-exits on them. Every change
            is written to this order's audit trail, which is how the journal spots a plan being
            moved repeatedly.
          </p>

          <div className="form-grid">
            <Field label="Target price" hint="Where you plan to take profit">
              <input
                className="input"
                type="number"
                step="0.01"
                min={0}
                value={planForm.target}
                onChange={(e) => setPlanForm((f) => ({ ...f, target: e.target.value }))}
              />
            </Field>
            <Field label="Stop loss" hint="Where you plan to cut the loss">
              <input
                className="input"
                type="number"
                step="0.01"
                min={0}
                value={planForm.stop}
                onChange={(e) => setPlanForm((f) => ({ ...f, stop: e.target.value }))}
              />
            </Field>
          </div>

          <Button onClick={handleSavePlan} loading={savingPlan}>
            Save plan
          </Button>
        </div>
      </Modal>
    </div>
  );
}
