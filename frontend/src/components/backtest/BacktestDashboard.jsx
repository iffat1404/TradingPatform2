import React, { useState } from 'react';
import { useBacktest } from '../../hooks/useBacktest';
import { PerformanceCards } from './PerformanceCards';
import { EquityChart } from './EquityChart';
import { TradeLogTable } from './TradeLogTable';
import { Card } from '../common/Card';
import './BacktestDashboard.css';

/**
 * BacktestDashboard - Main backtesting interface
 *
 * Layout: Two-column
 * - Left: Strategy control panel (scrollable)
 * - Right: Results area (scrollable)
 */
export function BacktestDashboard() {
  const {
    strategies,
    strategiesLoading,
    selectedStrategy,
    selectStrategy,
    formState,
    updateFormField,
    updateParameter,
    backtest,
    backtestLoading,
    backtestError,
    runBacktest,
  } = useBacktest();

  const [expandedStrategy, setExpandedStrategy] = useState(null);

  const handleStrategySelect = (strategyId) => {
    selectStrategy(strategyId);
    setExpandedStrategy(strategyId);
  };

  return (
    <div className="backtest-dashboard">
      {/* Left Panel: Strategy Controls */}
      <div className="backtest-controls">
        <Card className="controls-card">
          <div className="panel-header">
            <h2>Strategy</h2>
            <p className="panel-hint">Select and configure a strategy</p>
          </div>

          {/* Strategy Selector */}
          <div className="strategy-list">
            {strategiesLoading ? (
              <div className="loading-placeholder">Loading strategies...</div>
            ) : strategies.length === 0 ? (
              <div className="empty-placeholder">No strategies available</div>
            ) : (
              strategies.map(strategy => (
                <button
                  key={strategy.id}
                  className={`strategy-item ${selectedStrategy?.id === strategy.id ? 'active' : ''}`}
                  onClick={() => handleStrategySelect(strategy.id)}
                >
                  <div className="strategy-name">{strategy.name}</div>
                  <div className="strategy-desc">{strategy.description}</div>
                </button>
              ))
            )}
          </div>

          {/* Backtest Configuration */}
          {selectedStrategy && (
            <div className="config-section">
              <h3 className="section-title">Configuration</h3>

              <div className="form-group">
                <label>Symbol</label>
                <input
                  type="text"
                  className="form-input"
                  value={formState.symbol}
                  onChange={(e) => updateFormField('symbol', e.target.value)}
                  placeholder="e.g., BTC-USD"
                />
              </div>

              <div className="form-group">
                <label>Timeframe</label>
                <select
                  className="form-input"
                  value={formState.timeframe}
                  onChange={(e) => updateFormField('timeframe', e.target.value)}
                >
                  <option value="1h">1 Hour</option>
                  <option value="1d">1 Day</option>
                  <option value="1w">1 Week</option>
                </select>
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label>Start Date</label>
                  <input
                    type="date"
                    className="form-input"
                    value={formState.start_date}
                    onChange={(e) => updateFormField('start_date', e.target.value)}
                  />
                </div>
                <div className="form-group">
                  <label>End Date</label>
                  <input
                    type="date"
                    className="form-input"
                    value={formState.end_date}
                    onChange={(e) => updateFormField('end_date', e.target.value)}
                  />
                </div>
              </div>

              <div className="form-group">
                <label>Initial Capital</label>
                <input
                  type="number"
                  className="form-input"
                  value={formState.initial_capital}
                  onChange={(e) => updateFormField('initial_capital', e.target.value)}
                  min="100"
                />
              </div>

              {/* Strategy Parameters */}
              <div className="params-section">
                <h4 className="params-title">Strategy Parameters</h4>
                {selectedStrategy.parameters?.map(param => (
                  <div key={param.name} className="form-group">
                    <label>{param.name}</label>
                    <input
                      type={param.type === 'int' ? 'number' : 'text'}
                      className="form-input"
                      value={formState.parameters?.[param.name] || param.default || ''}
                      onChange={(e) => updateParameter(param.name, e.target.value)}
                      placeholder={`Default: ${param.default}`}
                    />
                  </div>
                ))}
              </div>

              {/* Run Backtest Button */}
              <button
                className="btn btn-primary btn-block"
                onClick={runBacktest}
                disabled={backtestLoading}
              >
                {backtestLoading ? 'Running...' : 'Run Backtest'}
              </button>
            </div>
          )}
        </Card>
      </div>

      {/* Right Panel: Results Area */}
      <div className="backtest-results">
        {/* Error Alert */}
        {backtestError && (
          <div className="error-alert">
            <span className="error-icon">⚠️</span>
            <span className="error-message">{backtestError}</span>
          </div>
        )}

        {/* Performance Cards */}
        {backtest && (
          <>
            <PerformanceCards
              result={backtest}
              loading={backtestLoading}
            />

            {/* Equity Chart with date filtering */}
            <EquityChart
              result={backtest}
              loading={backtestLoading}
              startDate={new Date(formState.startDate).toISOString().split('T')[0]}
              endDate={new Date(formState.endDate).toISOString().split('T')[0]}
            />

            {/* Trade Log - Always Visible */}
            <Card className="trades-card">
              <TradeLogTable
                result={backtest}
                loading={backtestLoading}
              />
            </Card>
          </>
        )}

        {!backtest && !backtestError && (
          <Card className="empty-state">
            <p>Run a backtest to see results</p>
          </Card>
        )}
      </div>
    </div>
  );
}
