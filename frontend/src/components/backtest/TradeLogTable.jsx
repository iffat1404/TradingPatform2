import React, { useState, useMemo } from 'react';
import './TradeLogTable.css';

const TRADES_PER_PAGE = 10;

/**
 * TradeLogTable - Paginated trade execution history
 *
 * Props:
 *   - result: Backtest result with trades array
 *   - loading: Whether result is loading
 */
export function TradeLogTable({ result, loading }) {
  const [currentPage, setCurrentPage] = useState(1);
  const [filterType, setFilterType] = useState('all'); // 'all', 'winning', 'losing'

  // Filter trades
  const filteredTrades = useMemo(() => {
    if (!result || !result.trades) return [];

    return result.trades.filter(trade => {
      if (filterType === 'winning') return trade.pnl > 0;
      if (filterType === 'losing') return trade.pnl < 0;
      return true;
    });
  }, [result, filterType]);

  // Paginate trades
  const paginatedTrades = useMemo(() => {
    const start = (currentPage - 1) * TRADES_PER_PAGE;
    return filteredTrades.slice(start, start + TRADES_PER_PAGE);
  }, [filteredTrades, currentPage]);

  const totalPages = Math.ceil(filteredTrades.length / TRADES_PER_PAGE);

  // Reset to page 1 when filter changes
  React.useEffect(() => {
    setCurrentPage(1);
  }, [filterType]);

  if (loading) {
    return (
      <div className="trade-log-table-container">
        <div className="table-header">
          <h2 className="table-title">Trade Execution History</h2>
        </div>
        <div className="table-loading">Loading trades...</div>
      </div>
    );
  }

  if (!result || !result.trades || result.trades.length === 0) {
    return (
      <div className="trade-log-table-container">
        <div className="table-header">
          <h2 className="table-title">Trade Execution History</h2>
        </div>
        <div className="table-empty">No trades executed</div>
      </div>
    );
  }

  const formatCurrency = (value) => {
    return `$${Math.abs(value).toLocaleString('en-US', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })}`;
  };

  const formatDate = (dateString) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <div className="trade-log-table-container">
      <div className="table-header">
        <h2 className="table-title">Trade Execution History</h2>

        <div className="table-controls">
          <select
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
            className="filter-select"
          >
            <option value="all">All Trades ({filteredTrades.length})</option>
            <option value="winning">Winning ({result.winning_trades})</option>
            <option value="losing">Losing ({result.losing_trades})</option>
          </select>
        </div>
      </div>

      <div className="table-wrapper">
        <table className="trade-table">
          <thead>
            <tr>
              <th className="col-trade-num">#</th>
              <th className="col-signal">Signal</th>
              <th className="col-entry-time">Entry Time</th>
              <th className="col-entry-price">Entry Price</th>
              <th className="col-exit-time">Exit Time</th>
              <th className="col-exit-price">Exit Price</th>
              <th className="col-size">Size</th>
              <th className="col-pnl">P&L ($)</th>
              <th className="col-pnl-pct">P&L (%)</th>
            </tr>
          </thead>
          <tbody>
            {paginatedTrades.map((trade, idx) => {
              const tradeNumber = (currentPage - 1) * TRADES_PER_PAGE + idx + 1;
              const isProfitable = trade.pnl > 0;

              return (
                <tr key={`${trade.entry_time}-${tradeNumber}`} className={`trade-row ${isProfitable ? 'profitable' : 'loss'}`}>
                  <td className="col-trade-num">
                    <span className="trade-num">{tradeNumber}</span>
                  </td>
                  <td className="col-signal">
                    <span className={`signal-badge ${trade.entry_time ? 'buy' : 'sell'}`}>
                      {trade.entry_time ? 'BUY' : 'SELL'}
                    </span>
                  </td>
                  <td className="col-entry-time">
                    <span className="timestamp">{formatDate(trade.entry_time)}</span>
                  </td>
                  <td className="col-entry-price">
                    <span className="price">{formatCurrency(trade.entry_price)}</span>
                  </td>
                  <td className="col-exit-time">
                    <span className="timestamp">{formatDate(trade.exit_time)}</span>
                  </td>
                  <td className="col-exit-price">
                    <span className="price">{formatCurrency(trade.exit_price)}</span>
                  </td>
                  <td className="col-size">
                    <span className="size">{trade.size.toFixed(4)}</span>
                  </td>
                  <td className="col-pnl">
                    <span className={`pnl ${isProfitable ? 'profit' : 'loss'}`}>
                      {isProfitable ? '+' : ''}{formatCurrency(trade.pnl)}
                    </span>
                  </td>
                  <td className="col-pnl-pct">
                    <span className={`pnl-pct ${isProfitable ? 'profit' : 'loss'}`}>
                      {isProfitable ? '+' : ''}{trade.pnl_percent.toFixed(2)}%
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="table-pagination">
          <button
            className="pagination-btn"
            onClick={() => setCurrentPage(Math.max(1, currentPage - 1))}
            disabled={currentPage === 1}
          >
            ← Previous
          </button>

          <div className="pagination-info">
            Page {currentPage} of {totalPages}
          </div>

          <button
            className="pagination-btn"
            onClick={() => setCurrentPage(Math.min(totalPages, currentPage + 1))}
            disabled={currentPage === totalPages}
          >
            Next →
          </button>
        </div>
      )}
    </div>
  );
}
