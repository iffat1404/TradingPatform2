import { useEffect, useMemo, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { TICKERS, getDaily, getIntraday, getLatestPrice, getPlatformQuotes } from '../../api/prices';
import { createOrder, listOrders, cancelOrder } from '../../api/orders';
import { getPortfolioSummary } from '../../api/portfolio';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import { useMarketTicker } from '../../hooks/useMarketTicker';
import { useMarketClock } from '../../hooks/useMarketClock';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { Field } from '../../components/common/Field';
import { ProcessRail } from '../../components/common/ProcessRail';
import { KlineChart } from '../../components/charts/KlineChart';
import { DecisionPanel } from '../../components/common/DecisionPanel';
import { toDailyPoints, toIntradayPoints, filterToSimulatedDay } from '../../utils/chartData';
import { formatCurrency, formatDateTime, formatPercent, deltaClass, orderQty, calculateTickerChange, calculateIntradayChange } from '../../utils/format';
import { previewDecision } from '../../api/decision';
import { extractErrorMessage } from '../../api/client';
import './trader-pages.css';

const OPEN_STATUSES = new Set(['NEW', 'VALIDATED', 'ROUTED']);
const INTRADAY_INTERVALS = ['1m', '5m', '15m', '60m'];

export function TradePage() {
  const { user, refreshUser } = useAuth();
  const toast = useToast();
  const location = useLocation();
  const prefill = location.state?.prefill;
  const [ticker, setTicker] = useState(() =>
    prefill?.ticker && TICKERS.includes(prefill.ticker.toUpperCase()) ? prefill.ticker.toUpperCase() : TICKERS[0]
  );
  const [chartMode, setChartMode] = useState('historical');
  const [intradayInterval, setIntradayInterval] = useState('5m');
  const [dailyData, setDailyData] = useState([]);
  const [intradayRaw, setIntradayRaw] = useState([]);
  const [latest, setLatest] = useState(null);
  const [orders, setOrders] = useState([]);
  const [buyingPower, setBuyingPower] = useState(null);
  const [quotes, setQuotes] = useState(null);
  const [form, setForm] = useState({
    side: prefill?.side === 'sell' ? 'sell' : 'buy',
    type: prefill?.type === 'limit' ? 'limit' : 'market',
    qty: prefill?.quantity || 10,
    limitPrice: '',
    targetPrice: '',
    stopLoss: '',
    tif: 'DAY',
  });
  const [decision, setDecision] = useState(null);
  const [decisionLoading, setDecisionLoading] = useState(false);
  const [decisionError, setDecisionError] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [lastOrderSide, setLastOrderSide] = useState(null);
  const [orderSuccess, setOrderSuccess] = useState(false);
  const { tick } = useMarketTicker(ticker);
  const clock = useMarketClock();

  const kycApproved = user?.kyc_status === 'APPROVED';

  // KYC is approved by an admin out-of-band, so the cached user loaded at login goes stale
  // the moment that happens. Re-check on mount so the gate lifts without a re-login.
  useEffect(() => {
    if (user && user.kyc_status !== 'APPROVED') {
      refreshUser().catch(() => {});
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Historical daily bars — for reviewing past performance of the share.
  useEffect(() => {
    getDaily(ticker).then((rows) => setDailyData(toDailyPoints(rows))).catch(() => setDailyData([]));
    getLatestPrice(ticker).then(setLatest).catch(() => setLatest(null));
    getPlatformQuotes(ticker).then(setQuotes).catch(() => setQuotes(null));
  }, [ticker]);

  // Live minute-level bars — for the current simulated trading day only.
  useEffect(() => {
    if (chartMode !== 'intraday') return;
    getIntraday(ticker, intradayInterval)
      .then((rows) => setIntradayRaw(toIntradayPoints(rows)))
      .catch(() => setIntradayRaw([]));
  }, [ticker, intradayInterval, chartMode]);

  // The intraday dataset spans a fixed simulated window (Jul 1 - Aug 30); only bars up to
  // "now" on today's simulated date should ever be visible, never the full dataset.
  const chartPoints = useMemo(() => {
    if (chartMode === 'historical') return dailyData;
    return filterToSimulatedDay(intradayRaw, clock.simulatedTime);
  }, [chartMode, dailyData, intradayRaw, clock.simulatedTime]);

  useEffect(() => {
    if (tick?.price) setLatest((prev) => ({ ...prev, close: tick.price }));
  }, [tick]);

  const refreshOrders = () => {
    listOrders().then(setOrders).catch(() => {});
    getPortfolioSummary()
      .then((p) => setBuyingPower(p.cash_balance - (p.collateral_reserved || 0)))
      .catch(() => {});
  };

  useEffect(refreshOrders, []);

  const currentPrice = tick?.price ?? latest?.close ?? 0;
  const estimatedPrice = form.type === 'limit' && form.limitPrice ? Number(form.limitPrice) : currentPrice;

  // Use bid/ask from real-time spreads for execution
  const executionPrice = form.side === 'buy'
    ? (tick?.spread?.ask ?? estimatedPrice)
    : (tick?.spread?.bid ?? estimatedPrice);

  // Dynamic estimated cost based on side and execution price
  const estimatedCost = executionPrice * (Number(form.qty) || 0);
  const executionLabel = form.side === 'buy' ? 'Estimated Cost (BUY at ASK)' : 'Estimated Proceeds (SELL at BID)';

  const openOrders = useMemo(() => orders.filter((o) => OPEN_STATUSES.has(o.status)), [orders]);

  // Score the decision as the ticket is filled in. Debounced so typing a quantity does not
  // fire a request per keystroke, and advisory only — it never gates submission.
  useEffect(() => {
    const qty = Number(form.qty);
    if (!kycApproved || !qty || qty <= 0) {
      setDecision(null);
      return undefined;
    }

    let cancelled = false;
    setDecisionLoading(true);
    const timer = setTimeout(() => {
      previewDecision({
        ticker,
        side: form.side,
        quantity: qty,
        price: estimatedPrice || undefined,
        target_price: form.targetPrice ? Number(form.targetPrice) : undefined,
        stop_loss: form.stopLoss ? Number(form.stopLoss) : undefined,
      })
        .then((res) => {
          if (cancelled) return;
          setDecision(res);
          setDecisionError(false);
        })
        .catch(() => {
          if (!cancelled) setDecisionError(true);
        })
        .finally(() => {
          if (!cancelled) setDecisionLoading(false);
        });
    }, 400);

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [ticker, form.side, form.qty, form.targetPrice, form.stopLoss, estimatedPrice, kycApproved]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await createOrder({
        ticker,
        side: form.side,
        type: form.type,
        qty: Number(form.qty),
        limit_price: form.type === 'limit' ? Number(form.limitPrice) : executionPrice,
        target_price: form.targetPrice ? Number(form.targetPrice) : undefined,
        stop_loss: form.stopLoss ? Number(form.stopLoss) : undefined,
        time_in_force: form.tif,
      });
      setLastOrderSide(form.side);
      setOrderSuccess(true);
      toast.success(`${form.side === 'buy' ? 'Buy' : 'Sell'} order for ${ticker} submitted at ${formatCurrency(executionPrice)}.`);
      refreshOrders();
      // Clear success indicator after 3 seconds
      setTimeout(() => setOrderSuccess(false), 3000);
    } catch (err) {
      toast.error(extractErrorMessage(err, 'Order was rejected.'));
    } finally {
      setSubmitting(false);
    }
  };

  const handleCancel = async (orderId) => {
    try {
      await cancelOrder(orderId);
      toast.info('Order cancelled.');
      refreshOrders();
    } catch (err) {
      toast.error(extractErrorMessage(err, 'Could not cancel that order.'));
    }
  };

  return (
    <div className="page-section">
      <div className="trade-layout">
        <Card>
          <div className="ticker-picker">
            {TICKERS.map((t) => (
              <button key={t} className={`ticker-pill${t === ticker ? ' is-active' : ''}`} onClick={() => setTicker(t)} type="button">
                {t}
              </button>
            ))}
          </div>
          <div className="price-header">
            <span className="font-display" style={{ fontSize: 22 }}>
              {ticker}
            </span>
            <span className="price-value mono-num">{formatCurrency(currentPrice)}</span>
            {latest && (
              <div className="price-metrics">
                <span className={`mono-num ${deltaClass(calculateTickerChange(currentPrice, latest.previous_close || latest.open))}`}>
                  {calculateTickerChange(currentPrice, latest.previous_close || latest.open) >= 0 ? '▲' : '▼'} {formatPercent(calculateTickerChange(currentPrice, latest.previous_close || latest.open))}
                </span>
                <span className={`mono-num price-intraday ${deltaClass(calculateIntradayChange(currentPrice, latest.open))}`}>
                  {calculateIntradayChange(currentPrice, latest.open) >= 0 ? '+' : ''}{formatCurrency(calculateIntradayChange(currentPrice, latest.open))}
                </span>
              </div>
            )}
            {tick?.spread && (
              <div className="spread-pill">
                <span className="spread-value">
                  Spread: {formatCurrency(tick.spread.spread)} ({tick.spread.spreadPercentage.toFixed(3)}%)
                </span>
                <span className={`volatility-badge vol-${
                  tick.spread.volatilityMultiplier >= 1.5 ? 'very-high' :
                  tick.spread.volatilityMultiplier >= 1.2 ? 'high' :
                  'normal'
                }`}>
                  {tick.spread.volatilityMultiplier >= 1.5 ? 'Very High Vol' :
                   tick.spread.volatilityMultiplier >= 1.2 ? 'High Vol' :
                   'Normal Vol'}
                </span>
              </div>
            )}
          </div>

          <div className="chart-range-tabs">
            <button className={chartMode === 'historical' ? 'is-active' : ''} type="button" onClick={() => setChartMode('historical')}>
              Historical
            </button>
            <button className={chartMode === 'intraday' ? 'is-active' : ''} type="button" onClick={() => setChartMode('intraday')}>
              Intraday
            </button>
            {chartMode === 'intraday' && (
              <select
                className="select"
                style={{ height: 30, marginLeft: 8 }}
                value={intradayInterval}
                onChange={(e) => setIntradayInterval(e.target.value)}
              >
                {INTRADAY_INTERVALS.map((i) => (
                  <option key={i} value={i}>
                    {i}
                  </option>
                ))}
              </select>
            )}
          </div>

          {chartMode === 'historical' ? (
            <p className="field-hint" style={{ margin: '0 0 12px' }}>
              Past performance from the historical daily dataset.
            </p>
          ) : (
            <p className="field-hint" style={{ margin: '0 0 12px' }}>
              Live intraday bars for today's simulated session
              {clock.simulatedTime ? ` — ${formatDateTime(clock.simulatedTime)}` : ''}. Only bars up to the
              current MarketClock time are shown.
            </p>
          )}

          <KlineChart data={chartPoints} height={500} ticker={ticker} isIntraday={chartMode === 'intraday'} />

        </Card>

        <Card title="Order ticket" className="order-ticket-card">
          <form className="order-ticket" onSubmit={handleSubmit}>
            {!kycApproved && (
              <div className="kyc-gate-overlay">
                <span className="eyebrow">KYC required</span>
                <p style={{ margin: 0, fontSize: 13, color: 'var(--text-muted)' }}>
                  Your KYC status is <strong>{user?.kyc_status || 'unknown'}</strong>. Trading unlocks once an
                  admin approves your submission.
                </p>
                <Link to="/trader/kyc" className="btn btn-primary btn-sm">
                  Go to KYC
                </Link>
              </div>
            )}

            <div className="side-toggle">
              <button
                type="button"
                className={`buy${form.side === 'buy' ? ' is-active' : ''}${orderSuccess && lastOrderSide === 'buy' ? ' completed' : ''}`}
                onClick={() => setForm((f) => ({ ...f, side: 'buy' }))}
              >
                {orderSuccess && lastOrderSide === 'buy' ? '✓ Buy' : 'Buy'}
              </button>
              <button
                type="button"
                className={`sell${form.side === 'sell' ? ' is-active' : ''}${orderSuccess && lastOrderSide === 'sell' ? ' completed' : ''}`}
                onClick={() => setForm((f) => ({ ...f, side: 'sell' }))}
              >
                {orderSuccess && lastOrderSide === 'sell' ? '✓ Sell' : 'Sell'}
              </button>
            </div>

            {tick?.spread && (
              <div className="market-depth-box">
                <div className="depth-cell bid-cell">
                  <span className="depth-label">BID</span>
                  <span className="depth-value">{formatCurrency(tick.spread.bid)}</span>
                </div>
                <div className="depth-cell spread-cell">
                  <span className="depth-label">SPREAD</span>
                  <span className="depth-value">{formatCurrency(tick.spread.spread)}</span>
                </div>
                <div className="depth-cell ask-cell">
                  <span className="depth-label">ASK</span>
                  <span className="depth-value">{formatCurrency(tick.spread.ask)}</span>
                </div>
              </div>
            )}

            {/* Order Type Segmented Control */}
            <Field label="Order type">
              <div className="segmented-control">
                <button
                  type="button"
                  className={`segment-btn ${form.type === 'market' ? 'active' : ''}`}
                  onClick={() => setForm((f) => ({ ...f, type: 'market' }))}
                >
                  Market
                </button>
                <button
                  type="button"
                  className={`segment-btn ${form.type === 'limit' ? 'active' : ''}`}
                  onClick={() => setForm((f) => ({ ...f, type: 'limit' }))}
                >
                  Limit
                </button>
              </div>
            </Field>

{/* Quantity Input with Step Controls & Quick Quick-Select Pills */}
<Field label="Quantity">
  <div className="quantity-wrapper">
    <div className="quantity-input-group">
      <button
        type="button"
        className="qty-step-btn"
        onClick={() => setForm((f) => ({ ...f, qty: Math.max(1, (Number(f.qty) || 1) - 1) }))}
      >
        −
      </button>
      <input
        className="input quantity-input"
        type="number"
        min={1}
        value={form.qty}
        onChange={(e) => setForm((f) => ({ ...f, qty: e.target.value }))}
      />
      <button
        type="button"
        className="qty-step-btn"
        onClick={() => setForm((f) => ({ ...f, qty: (Number(f.qty) || 0) + 1 }))}
      >
        +
      </button>
    </div>

    {/* Quick Percent Selection (Optional based on max purchasing power) */}
    <div className="quick-qty-pills">
      {[0.25, 0.5, 0.75, 1.0].map((pct) => (
        <button
          key={pct}
          type="button"
          className="qty-pill"
          onClick={() => {
            // Calculates quantity based on max available units (e.g., maxShares = 100)
            const maxShares = 100; 
            setForm((f) => ({ ...f, qty: Math.max(1, Math.floor(maxShares * pct)) }));
          }}
        >
          {pct === 1.0 ? 'MAX' : `${pct * 100}%`}
        </button>
      ))}
    </div>
  </div>
</Field>
            {form.type === 'limit' && (
              <Field label="Limit price">
                <input
                  className="input"
                  type="number"
                  step="0.01"
                  min={0}
                  value={form.limitPrice}
                  onChange={(e) => setForm((f) => ({ ...f, limitPrice: e.target.value }))}
                />
              </Field>
            )}

            <div className="form-grid">
              <Field label="Target price" hint="Optional">
                <input
                  className="input"
                  type="number"
                  step="0.01"
                  min={0}
                  placeholder="e.g. 250"
                  value={form.targetPrice}
                  onChange={(e) => setForm((f) => ({ ...f, targetPrice: e.target.value }))}
                />
              </Field>
              <Field label="Stop loss" hint="Optional">
                <input
                  className="input"
                  type="number"
                  step="0.01"
                  min={0}
                  placeholder="e.g. 224"
                  value={form.stopLoss}
                  onChange={(e) => setForm((f) => ({ ...f, stopLoss: e.target.value }))}
                />
              </Field>
            </div>

            <div className={`order-summary-row ${form.side}`}>
              <span className="cost-label">{executionLabel}</span>
            </div>

            <div className="order-summary-row">
              <span>Estimated cost</span>
              <strong>{formatCurrency(estimatedCost)}</strong>
            </div>
            {tick?.spread && form.qty && (
              <div className="order-summary-row">
                <span>Execution spread cost</span>
                <strong className="spread-cost">{formatCurrency(tick.spread.spread * Number(form.qty))}</strong>
              </div>
            )}
            {tick?.spread && (
              <div className="order-summary-row execution-price-row">
                <span>Execution price ({form.side === 'buy' ? 'ASK' : 'BID'})</span>
                <strong className={`execution-price ${form.side}`}>
                  {formatCurrency(executionPrice)}
                </strong>
              </div>
            )}
            <div className="order-summary-row">
              <span>Buying power</span>
              <strong>{formatCurrency(buyingPower)}</strong>
            </div>

            <Button type="submit" loading={submitting} disabled={!kycApproved} style={{ width: '100%' }}>
              Place {form.side === 'buy' ? 'buy' : 'sell'} order
            </Button>
          </form>
        </Card>
      </div>

      <Card>
        <DecisionPanel decision={decision} loading={decisionLoading} error={decisionError} />
      </Card>

      <Card title="Open orders">
        {openOrders.length ? (
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
                  <th />
                </tr>
              </thead>
              <tbody>
                {openOrders.map((o) => (
                  <tr key={o.id}>
                    <td className="font-mono">{o.ticker}</td>
                    <td style={{ textTransform: 'capitalize' }}>{o.side}</td>
                    <td style={{ textTransform: 'capitalize' }}>{o.type}</td>
                    <td className="mono-num">{orderQty(o)}</td>
                    <td className="mono-num">{o.limit_price ? formatCurrency(o.limit_price) : '—'}</td>
                    <td>
                      <ProcessRail status={o.status} />
                    </td>
                    <td>
                      <button className="btn btn-danger btn-sm" type="button" onClick={() => handleCancel(o.id)}>
                        Cancel
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="empty-state">No working orders right now.</div>
        )}
      </Card>
    </div>
  );
}
