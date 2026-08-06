import { useEffect, useState } from 'react';
import { getPortfolioSummary, getPortfolioPnl, getPortfolioExposure, getTickerLots } from '../../api/portfolio';
import { exportPortfolioCsv, getPortfolioReport } from '../../api/reports';
import { getMarketCurrent } from '../../api/prices';
import { Card } from '../../components/common/Card';
import { StatCard } from '../../components/common/StatCard';
import { Modal } from '../../components/common/Modal';
import { useToast } from '../../context/ToastContext';
import { formatCurrency, formatPercent, formatDateTime, deltaClass, calculateTickerChange, calculateIntradayChange } from '../../utils/format';
import { extractErrorMessage } from '../../api/client';
import './trader-pages.css';

export function PortfolioPage() {
  const [portfolio, setPortfolio] = useState(null);
  const [pnl, setPnl] = useState(null);
  const [exposure, setExposure] = useState(null);
  const [marketData, setMarketData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [lotsTicker, setLotsTicker] = useState(null);
  const [lots, setLots] = useState([]);
  const [exporting, setExporting] = useState(false);
  const toast = useToast();

  const [report, setReport] = useState(null);

  useEffect(() => {
    let active = true;
    Promise.all([getPortfolioSummary(), getPortfolioPnl(), getPortfolioExposure(), getPortfolioReport().catch(() => null), getMarketCurrent().catch(() => null)])
      .then(([p, pl, ex, rep, market]) => {
        if (!active) return;
        setPortfolio(p);
        setPnl(pl);
        setExposure(ex);
        setReport(rep);
        setMarketData(market);
      })
      .catch(() => active && setError('Could not load your portfolio.'))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, []);

  const openLots = (ticker) => {
    setLotsTicker(ticker);
    getTickerLots(ticker)
      .then(setLots)
      .catch(() => setLots([]));
  };

  const handleExport = async () => {
    setExporting(true);
    try {
      const blob = await exportPortfolioCsv();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'shunryu-stp-portfolio.csv';
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      toast.error(extractErrorMessage(err, 'Could not export your portfolio.'));
    } finally {
      setExporting(false);
    }
  };

  if (loading) return <div className="loading-row">Loading your portfolio…</div>;
  if (error) return <div className="error-banner">{error}</div>;

  const positions = portfolio?.positions || [];

  // The /portfolio/exposure endpoint returns an array of ticker objects with sector info
  // Aggregate sector data from that array
  const byTicker = Array.isArray(exposure)
    ? exposure.map(item => ({
        ticker: item.ticker,
        percentage: item.exposure_pct,
        pct: item.exposure_pct
      }))
    : [];

  const bySector = Array.isArray(exposure)
    ? Object.entries(
        exposure.reduce((acc, item) => {
          const sector = item.sector || 'Other';
          if (!acc[sector]) acc[sector] = { name: sector, exposure_pct: 0 };
          acc[sector].exposure_pct += item.exposure_pct || 0;
          return acc;
        }, {})
      ).map(([name, data]) => ({ name, percentage: data.exposure_pct, pct: data.exposure_pct }))
    : [];

  return (
    <div className="page-section">
      <div className="page-header">
        <div>
          <h2 style={{ margin: 0 }}>Portfolio</h2>
          <p className="page-subtitle">Positions, exposure, and realized / unrealized performance.</p>
        </div>
        <button className="btn btn-secondary btn-sm" onClick={handleExport} disabled={exporting} type="button">
          {exporting ? 'Exporting…' : 'Export CSV'}
        </button>
      </div>

      <div className="stat-row">
        <StatCard label="Net worth" value={formatCurrency(portfolio?.net_worth)} />
        <StatCard label="Cash balance" value={formatCurrency(portfolio?.cash_balance)} />
        <StatCard label="Total P&L" value={formatCurrency(pnl?.total_pnl)} deltaTone={deltaClass(pnl?.total_pnl)} />
        <StatCard label="Realized P&L" value={formatCurrency(pnl?.realized_pnl)} deltaTone={deltaClass(pnl?.realized_pnl)} />
        <StatCard label="Unrealized P&L" value={formatCurrency(pnl?.unrealized_pnl)} deltaTone={deltaClass(pnl?.unrealized_pnl)} />
      </div>

      <Card title="Open positions">
        {positions.length ? (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Ticker</th>
                  <th>Qty</th>
                  <th>Avg cost</th>
                  <th>Market value</th>
                  <th>Day change %</th>
                  <th>Intraday</th>
                  <th>Unrealized P&L</th>
                  <th>Realized P&L</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {positions.map((p) => {
                  const tickerData = marketData?.[p.ticker];
                  const currentPrice = tickerData?.close || p.market_value / Math.abs(p.signed_qty);
                  const dayChangePct = calculateTickerChange(currentPrice, tickerData?.previous_close || tickerData?.open);
                  const intradayChange = calculateIntradayChange(currentPrice, tickerData?.open);
                  
                  return (
                    <tr key={p.ticker}>
                      <td className="font-mono">{p.ticker}</td>
                      <td className="mono-num">{p.signed_qty}</td>
                      <td className="mono-num">{formatCurrency(p.avg_cost)}</td>
                      <td className="mono-num">{p.market_value !== undefined ? formatCurrency(p.market_value) : '—'}</td>
                      <td className={`mono-num ${deltaClass(dayChangePct)}`}>
                        {dayChangePct >= 0 ? '▲' : '▼'} {formatPercent(dayChangePct)}
                      </td>
                      <td className={`mono-num price-intraday ${deltaClass(intradayChange)}`}>
                        {intradayChange >= 0 ? '+' : ''}{formatCurrency(intradayChange)}
                      </td>
                      <td className={`mono-num ${deltaClass(p.unrealized_pnl)}`}>
                        {p.unrealized_pnl !== undefined ? formatCurrency(p.unrealized_pnl) : '—'}
                      </td>
                      <td className={`mono-num ${deltaClass(p.realized_pnl)}`}>{formatCurrency(p.realized_pnl)}</td>
                      <td>
                        <button className="btn btn-ghost btn-sm" type="button" onClick={() => openLots(p.ticker)}>
                          View lots
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="empty-state">No open positions yet — place your first order from Trade.</div>
        )}
      </Card>

      <div className="two-col">
        <Card title="Exposure by ticker">
          {byTicker.length ? (
            byTicker.map((row, i) => {
              const pct = row.percentage ?? row.pct ?? 0;
              return (
                <div className="exposure-bar-row" key={row.ticker || i}>
                  <div className="exposure-bar-label">
                    <span className="font-mono">{row.ticker}</span>
                    <span className="mono-num">{formatPercent(pct)}</span>
                  </div>
                  <div className="exposure-bar-track">
                    <div className="exposure-bar-fill" style={{ width: `${Math.min(100, pct || 0)}%` }} />
                  </div>
                </div>
              );
            })
          ) : (
            <div className="empty-state">No exposure data yet.</div>
          )}
        </Card>

        <Card title="Exposure by sector">
          {bySector.length ? (
            bySector.map((row) => {
              const pct = row.percentage ?? row.pct ?? 0;
              return (
                <div className="exposure-bar-row" key={row.name}>
                  <div className="exposure-bar-label">
                    <span>{row.name}</span>
                    <span className="mono-num">{formatPercent(pct)}</span>
                  </div>
                  <div className="exposure-bar-track">
                    <div className="exposure-bar-fill" style={{ width: `${Math.min(100, pct || 0)}%` }} />
                  </div>
                </div>
              );
            })
          ) : (
            <div className="empty-state">No sector data yet.</div>
          )}
        </Card>
      </div>

      <Modal open={Boolean(lotsTicker)} onClose={() => setLotsTicker(null)} title={`${lotsTicker} — FIFO lots`}>
        {lots.length ? (
          <table className="data-table">
            <thead>
              <tr>
                <th>Qty</th>
                <th>Cost</th>
                <th>Entry time</th>
              </tr>
            </thead>
            <tbody>
              {lots.map((lot) => (
                <tr key={lot.id}>
                  <td className="mono-num">{lot.qty}</td>
                  <td className="mono-num">{formatCurrency(lot.cost)}</td>
                  <td>{formatDateTime(lot.entry_time)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="empty-state">No lots recorded for this ticker.</div>
        )}
      </Modal>
    </div>
  );
}
