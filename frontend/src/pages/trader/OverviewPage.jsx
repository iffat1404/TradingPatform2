import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { getPortfolioSummary, getPortfolioPnl } from '../../api/portfolio';
import { listOrders } from '../../api/orders';
import { getMarketCurrent, TICKERS } from '../../api/prices';
import { getPortfolioReport } from '../../api/reports';
import { useAuth } from '../../context/AuthContext';
import { Card } from '../../components/common/Card';
import { StatCard } from '../../components/common/StatCard';
import { ProcessRail } from '../../components/common/ProcessRail';
import { NewsFeed } from '../../components/common/NewsFeed';
import { PerformanceAreaChart } from '../../components/charts/PerformanceAreaChart';
import { AllocationDonut, ALLOCATION_COLORS } from '../../components/charts/AllocationDonut';
import { formatCurrency, formatPercent, formatDateTime, deltaClass, orderQty } from '../../utils/format';
import './trader-pages.css';

const extractPerformanceSeries = (report, start, current) => {
  const candidates = [report?.performance?.history, report?.performance?.series].filter(Array.isArray);
  if (candidates.length && candidates[0].length) {
    return candidates[0].map((pt, i) => ({
      label: pt.date || pt.timestamp || `#${i + 1}`,
      value: pt.value ?? pt.net_worth ?? pt.close ?? 0,
    }));
  }
  return [
    { label: 'Starting capital', value: start ?? 0 },
    { label: 'Now', value: current ?? 0 },
  ];
};

export function OverviewPage() {
  const { user } = useAuth();
  const [portfolio, setPortfolio] = useState(null);
  const [pnl, setPnl] = useState(null);
  const [orders, setOrders] = useState([]);
  const [market, setMarket] = useState(null);
  const [perfSeries, setPerfSeries] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    Promise.all([getPortfolioSummary(), getPortfolioPnl(), listOrders(), getMarketCurrent()])
      .then(([p, pl, o, m]) => {
        if (!active) return;
        setPortfolio(p);
        setPnl(pl);
        setOrders(o);
        setMarket(m);
        getPortfolioReport()
          .then((report) => active && setPerfSeries(extractPerformanceSeries(report, user?.starting_capital, p.net_worth)))
          .catch(() => active && setPerfSeries(extractPerformanceSeries(null, user?.starting_capital, p.net_worth)));
      })
      .catch(() => active && setError('Could not load your dashboard. Try refreshing.'))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (loading) return <div className="loading-row">Loading your desk…</div>;
  if (error) return <div className="error-banner">{error}</div>;

  const buyingPower = portfolio ? portfolio.cash_balance - (portfolio.collateral_reserved || 0) : 0;
  const openPositions = portfolio?.positions?.length ?? 0;

  const allocationData = (portfolio?.positions || [])
    .filter((p) => p.market_value)
    .map((p) => ({ name: p.ticker, value: Math.abs(p.market_value) }));

  const recentOrders = orders.slice(0, 6);

  const topMovers = TICKERS.map((ticker) => {
    const row = market?.[ticker];
    if (!row) return null;
    const changePct = row.open ? ((row.close - row.open) / row.open) * 100 : 0;
    return { ticker, changePct, price: row.close };
  })
    .filter(Boolean)
    .sort((a, b) => Math.abs(b.changePct) - Math.abs(a.changePct))
    .slice(0, 5);

  return (
    <div className="page-section">
      <div className="stat-row">
        <StatCard label="Net worth" value={formatCurrency(portfolio?.net_worth)} />
        <StatCard label="Total P&L" value={formatCurrency(pnl?.total_pnl)} deltaTone={deltaClass(pnl?.total_pnl)} />
        <StatCard label="Cash balance" value={formatCurrency(portfolio?.cash_balance)} />
        <StatCard label="Buying power" value={formatCurrency(buyingPower)} />
        <StatCard label="Open positions" value={openPositions} />
      </div>

      <div className="overview-row-1">
        <Card title="Portfolio performance">
          <PerformanceAreaChart data={perfSeries} />
        </Card>
        <Card title="Asset allocation">
          <AllocationDonut data={allocationData} />
          <div className="allocation-legend">
            {allocationData.map((d, i) => (
              <span key={d.name} className="allocation-legend-item">
                <span className="legend-dot" style={{ background: ALLOCATION_COLORS[i % ALLOCATION_COLORS.length] }} />
                {d.name}
              </span>
            ))}
          </div>
        </Card>
        <Card title="Market overview">
          <ul className="market-mini-list">
            {TICKERS.map((ticker) => {
              const row = market?.[ticker];
              if (!row) return null;
              const changePct = row.open ? ((row.close - row.open) / row.open) * 100 : 0;
              return (
                <li key={ticker}>
                  <span className="font-mono">{ticker}</span>
                  <span className="mono-num">{formatCurrency(row.close)}</span>
                  <span className={`mono-num ${deltaClass(changePct)}`}>{formatPercent(changePct)}</span>
                </li>
              );
            })}
          </ul>
          <Link to="/trader/trade" className="btn btn-ghost btn-sm" style={{ marginTop: 8 }}>
            View all markets →
          </Link>
        </Card>
      </div>

      <div className="overview-row-2">
        <Card
          title="Recent orders"
          action={
            <Link to="/trader/orders" className="btn btn-ghost btn-sm">
              View all
            </Link>
          }
        >
          {recentOrders.length ? (
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Ticker</th>
                    <th>Side</th>
                    <th>Qty</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {recentOrders.map((o) => (
                    <tr key={o.id}>
                      <td className="font-mono">{o.ticker}</td>
                      <td style={{ textTransform: 'capitalize' }}>{o.side}</td>
                      <td className="mono-num">{orderQty(o)}</td>
                      <td>
                        <ProcessRail status={o.status} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="empty-state">No orders yet — head to Trade to place your first one.</div>
          )}
        </Card>

        <Card title="Top movers">
          <ul className="mover-list">
            {topMovers.map((m) => (
              <li key={m.ticker}>
                <span className="font-mono">{m.ticker}</span>
                <span className={`mono-num ${deltaClass(m.changePct)}`}>{formatPercent(m.changePct)}</span>
              </li>
            ))}
          </ul>
        </Card>

        <Card
          title="Market news"
          action={
            <Link to="/trader/journal" className="btn btn-ghost btn-sm">
              Journal
            </Link>
          }
        >
          <NewsFeed days={1} limit={12} minRelevance={0.1} />
        </Card>
      </div>
    </div>
  );
}
