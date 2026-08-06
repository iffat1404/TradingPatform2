import { useEffect, useState } from 'react';
import { TICKERS } from '../../api/prices';
import { getIndicators, getAlerts, getSentimentDivergence } from '../../api/analytics';
import { Card } from '../../components/common/Card';
import { StatCard } from '../../components/common/StatCard';
import { Button } from '../../components/common/Button';
import { RsiGauge, MacdPanel, BollingerPanel, PriceMaChart, BollingerBandsChart, MacdChart } from '../../components/charts/IndicatorCharts';
import { formatDateTime, formatPercent } from '../../utils/format';
import './trader-pages.css';

// The indicators endpoint returns parallel time-series arrays (one entry per date), not a
// single current snapshot — this reads the latest non-null value out of each series.
const lastValid = (arr) => {
  if (!Array.isArray(arr)) return arr ?? null;
  for (let i = arr.length - 1; i >= 0; i -= 1) {
    if (arr[i] !== null && arr[i] !== undefined) return arr[i];
  }
  return null;
};

const toSeries = (ind) => {
  if (!Array.isArray(ind?.dates)) return [];
  return ind.dates.map((date, i) => ({
    date,
    close: ind.close?.[i] ?? null,
    sma20: ind.sma_20?.[i] ?? null,
    sma50: ind.sma_50?.[i] ?? null,
    rsi: ind.rsi_14?.[i] ?? null,
    macd: ind.macd?.macd?.[i] ?? null,
    macdSignal: ind.macd?.signal?.[i] ?? null,
    macdHistogram: ind.macd?.histogram?.[i] ?? null,
    bbUpper: ind.bollinger_bands?.upper?.[i] ?? null,
    bbMiddle: ind.bollinger_bands?.middle?.[i] ?? null,
    bbLower: ind.bollinger_bands?.lower?.[i] ?? null,
  }));
};

export function AnalyticsPage() {
  const [ticker, setTicker] = useState(TICKERS[0]);
  const [indicators, setIndicators] = useState(null);
  const [series, setSeries] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [date, setDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [divergence, setDivergence] = useState(null);
  const [divLoading, setDivLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    Promise.all([getIndicators(ticker), getAlerts(ticker)])
      .then(([ind, al]) => {
        setSeries(toSeries(ind));
        setIndicators({
          sma_20: lastValid(ind?.sma_20),
          sma_50: lastValid(ind?.sma_50),
          ema_12: lastValid(ind?.ema_12),
          ema_26: lastValid(ind?.ema_26),
          rsi_14: lastValid(ind?.rsi_14),
          macd: ind?.macd
            ? { macd: lastValid(ind.macd.macd), signal: lastValid(ind.macd.signal), histogram: ind.macd.histogram }
            : null,
          bollinger_bands: ind?.bollinger_bands
            ? {
                upper: lastValid(ind.bollinger_bands.upper),
                middle: lastValid(ind.bollinger_bands.middle),
                lower: lastValid(ind.bollinger_bands.lower),
              }
            : null,
        });
        setAlerts(al?.alerts || []);
      })
      .catch(() => {
        setIndicators(null);
        setSeries([]);
        setAlerts([]);
      })
      .finally(() => setLoading(false));
    setDivergence(null);
  }, [ticker]);

  const checkDivergence = () => {
    setDivLoading(true);
    getSentimentDivergence(ticker, date)
      .then(setDivergence)
      .catch(() => setDivergence(null))
      .finally(() => setDivLoading(false));
  };

  return (
    <div className="page-section">
      <div className="page-header">
        <div>
          <h2 style={{ margin: 0 }}>Analytics</h2>
          <p className="page-subtitle">Technical indicators, alerts, and news-sentiment divergence.</p>
        </div>
      </div>

      <div className="ticker-picker">
        {TICKERS.map((t) => (
          <button key={t} className={`ticker-pill${t === ticker ? ' is-active' : ''}`} onClick={() => setTicker(t)} type="button">
            {t}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="loading-row">Loading indicators…</div>
      ) : (
        <>
          <Card title={`${ticker} — price vs. moving averages`}>
            <PriceMaChart data={series} />
          </Card>

          <div className="indicator-grid">
            <Card title="RSI">
              <RsiGauge value={indicators?.rsi_14} />
            </Card>
            <Card title="Alerts">
              {alerts.length ? (
                alerts.map((a, i) => (
                  <div className="alert-item" key={i}>
                    <span className="eyebrow">{a.type}</span>
                    <span style={{ fontSize: 13 }}>{a.message}</span>
                    <span className="field-hint">{formatDateTime(a.timestamp)}</span>
                  </div>
                ))
              ) : (
                <div className="empty-state">No active alerts for {ticker}.</div>
              )}
            </Card>
          </div>

          <Card title={`${ticker} — Bollinger Bands (20-day)`} style={{ marginTop: 16 }}>
            <BollingerBandsChart data={series} />
          </Card>

          <Card title={`${ticker} — MACD`} style={{ marginTop: 16 }}>
            <MacdChart data={series} />
          </Card>


        </>
      )}
    </div>
  );
}
