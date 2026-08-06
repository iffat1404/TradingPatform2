import React, { useState, useMemo } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import './EquityChart.css';

/**
 * EquityChart - Interactive equity curve visualization
 *
 * Props:
 *   - result: Backtest result with timestamps and equity_curve
 *   - loading: Whether result is loading
 *   - startDate: Start date string (YYYY-MM-DD) to filter data
 *   - endDate: End date string (YYYY-MM-DD) to filter data
 */
export function EquityChart({ result, loading, startDate, endDate }) {
  const [chartMode, setChartMode] = useState('equity'); // 'equity' or 'drawdown'

  // Prepare chart data with date filtering
  const chartData = useMemo(() => {
    if (!result || !result.timestamps || !result.equity_curve) return [];

    // Parse date range
    const filterStart = startDate ? new Date(startDate) : null;
    const filterEnd = endDate ? new Date(endDate) : null;

    const filtered = result.timestamps
      .map((timestamp, idx) => {
        const date = new Date(timestamp);
        return {
          timestamp,
          date,
          equityValue: result.equity_curve[idx],
          idx,
        };
      })
      .filter(item => {
        if (filterStart && item.date < filterStart) return false;
        if (filterEnd) {
          const endOfDay = new Date(filterEnd);
          endOfDay.setHours(23, 59, 59, 999);
          if (item.date > endOfDay) return false;
        }
        return true;
      });

    // Calculate max from filtered data
    const maxValue = filtered.length > 0 ? Math.max(...filtered.map(f => f.equityValue)) : 0;

    return filtered.map(item => {
      const date = new Date(item.timestamp);
      // Use UTC time to avoid timezone offset issues
      const utcMonth = date.getUTCMonth();
      const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
      const month = monthNames[utcMonth];
      const day = date.getUTCDate();
      const hours = String(date.getUTCHours()).padStart(2, '0');
      const minutes = String(date.getUTCMinutes()).padStart(2, '0');

      return {
        timestamp: `${month} ${day}, ${hours}:${minutes}`,
        equity: parseFloat(item.equityValue.toFixed(2)),
        drawdown: parseFloat(((item.equityValue - maxValue) / maxValue) * 100).toFixed(2),
      };
    });
  }, [result, startDate, endDate]);

  if (loading) {
    return (
      <div className="equity-chart-container">
        <div className="chart-header">
          <h2 className="chart-title">Portfolio Performance</h2>
        </div>
        <div className="chart-loading">Loading chart...</div>
      </div>
    );
  }

  if (!result) {
    return (
      <div className="equity-chart-container">
        <div className="chart-header">
          <h2 className="chart-title">Portfolio Performance</h2>
        </div>
        <div className="chart-empty">Run a backtest to see equity curve</div>
      </div>
    );
  }

  return (
    <div className="equity-chart-container">
      <div className="chart-header">
        <h2 className="chart-title">Portfolio Performance</h2>
        <div className="chart-controls">
          <button
            className={`mode-btn ${chartMode === 'equity' ? 'active' : ''}`}
            onClick={() => setChartMode('equity')}
          >
            Equity Curve
          </button>
          <button
            className={`mode-btn ${chartMode === 'drawdown' ? 'active' : ''}`}
            onClick={() => setChartMode('drawdown')}
          >
            Drawdown
          </button>
        </div>
      </div>

      <div className="chart-wrapper">
        {chartData.length > 0 ? (
          <ResponsiveContainer width="100%" height={400}>
            <LineChart data={chartData} margin={{ top: 5, right: 30, left: 0, bottom: 5 }}>
              <defs>
                <linearGradient id="equityGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="drawdownGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                </linearGradient>
              </defs>

              <CartesianGrid strokeDasharray="3 3" stroke="#2c2d32" />
              <XAxis
                dataKey="timestamp"
                stroke="#6b7280"
                tick={{ fontSize: 12 }}
                interval={Math.max(0, Math.floor(chartData.length / 12))}
                angle={-45}
                textAnchor="end"
                height={80}
              />
              <YAxis
                stroke="#6b7280"
                tick={{ fontSize: 12 }}
                label={{
                  value: chartMode === 'equity' ? 'Account Value ($)' : 'Drawdown (%)',
                  angle: -90,
                  position: 'insideLeft',
                }}
              />
              <Tooltip
                contentStyle={{
                  background: '#1a1b1e',
                  border: '1px solid #2c2d32',
                  borderRadius: '6px',
                  color: '#e5e7eb',
                }}
                formatter={(value) =>
                  chartMode === 'equity'
                    ? `$${value.toLocaleString('en-US', {
                        minimumFractionDigits: 2,
                        maximumFractionDigits: 2,
                      })}`
                    : `${value.toFixed(2)}%`
                }
                labelStyle={{ color: '#e5e7eb' }}
              />

              {chartMode === 'equity' ? (
                <Line
                  type="monotone"
                  dataKey="equity"
                  stroke="#10b981"
                  strokeWidth={2}
                  dot={false}
                  isAnimationActive={false}
                  fillOpacity={1}
                  fill="url(#equityGradient)"
                />
              ) : (
                <Line
                  type="monotone"
                  dataKey="drawdown"
                  stroke="#ef4444"
                  strokeWidth={2}
                  dot={false}
                  isAnimationActive={false}
                  fillOpacity={1}
                  fill="url(#drawdownGradient)"
                />
              )}
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <div className="chart-empty">No data available</div>
        )}
      </div>
    </div>
  );
}
