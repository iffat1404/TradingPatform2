import React from 'react';
import './PerformanceCards.css';

/**
 * PerformanceCards - KPI banner with 5 key metrics
 *
 * Props:
 *   - result: Backtest result object
 *   - loading: Whether result is loading
 */
export function PerformanceCards({ result, loading }) {
  if (loading) {
    return <div className="performance-cards skeleton">Loading...</div>;
  }

  if (!result) {
    return (
      <div className="performance-cards empty">
        <p>Run a backtest to see performance metrics</p>
      </div>
    );
  }

  const formatCurrency = (value) => {
    return `$${Math.abs(value).toLocaleString('en-US', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })}`;
  };

  const formatPercent = (value) => {
    return `${value.toFixed(2)}%`;
  };

  const isProfit = result.return_percent >= 0;
  const winRatePercent = (result.win_rate * 100).toFixed(1);

  return (
    <div className="performance-cards">
      {/* Net Profit / Total Return */}
      <div className={`kpi-card ${isProfit ? 'positive' : 'negative'}`}>
        <div className="kpi-header">
          <span className="kpi-label">Total Return</span>
          <span className="kpi-icon">📈</span>
        </div>
        <div className="kpi-values">
          <div className="kpi-primary">{formatPercent(result.return_percent)}</div>
          <div className="kpi-secondary">{formatCurrency(result.final_value - result.initial_capital)}</div>
        </div>
      </div>

      {/* Win Rate */}
      <div className="kpi-card neutral">
        <div className="kpi-header">
          <span className="kpi-label">Win Rate</span>
          <span className="kpi-icon">🎯</span>
        </div>
        <div className="kpi-values">
          <div className="kpi-primary">{winRatePercent}%</div>
          <div className="kpi-secondary">
            {result.winning_trades} of {result.total_trades} trades
          </div>
        </div>
      </div>

      {/* Profit Factor */}
      <div className={`kpi-card ${result.profit_factor > 1 ? 'positive' : 'negative'}`}>
        <div className="kpi-header">
          <span className="kpi-label">Profit Factor</span>
          <span className="kpi-icon">💹</span>
        </div>
        <div className="kpi-values">
          <div className="kpi-primary">{result.profit_factor.toFixed(2)}</div>
          <div className="kpi-secondary">
            {result.profit_factor > 1 ? 'Profitable' : 'Loss-making'}
          </div>
        </div>
      </div>

      {/* Max Drawdown */}
      <div className="kpi-card negative">
        <div className="kpi-header">
          <span className="kpi-label">Max Drawdown</span>
          <span className="kpi-icon">📉</span>
        </div>
        <div className="kpi-values">
          <div className="kpi-primary">{formatPercent(result.max_drawdown * -100)}</div>
          <div className="kpi-secondary">Peak-to-trough decline</div>
        </div>
      </div>

      {/* Total Trades / Sharpe Ratio */}
      <div className="kpi-card dual-stat">
        <div className="dual-stat-left">
          <span className="kpi-label">Total Trades</span>
          <div className="kpi-primary">{result.total_trades}</div>
        </div>
        <div className="dual-stat-divider"></div>
        <div className="dual-stat-right">
          <span className="kpi-label">Sharpe Ratio</span>
          <div className="kpi-primary">{result.sharpe_ratio.toFixed(2)}</div>
        </div>
      </div>
    </div>
  );
}
