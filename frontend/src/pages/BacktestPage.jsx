import React, { useState, useEffect } from 'react';
import { useToast } from '../../context/ToastContext';
import { StrategySelector } from '../../components/backtest/StrategySelector';
import { StrategyParamForm } from '../../components/backtest/StrategyParamForm';
import { Card } from '../../components/common/Card';
import './BacktestPage.css';

const API_BASE = 'http://127.0.0.1:8000/api/v1/backtest';

/**
 * BacktestPage - Main backtesting interface
 *
 * Allows users to:
 * 1. Select a preset strategy
 * 2. Configure strategy parameters
 * 3. Set backtest parameters (symbol, dates, capital)
 * 4. Run backtest and view results
 */
export function BacktestPage() {
  const toast = useToast();

  // State
  const [strategies, setStrategies] = useState([]);
  const [selectedStrategy, setSelectedStrategy] = useState(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);

  // Form state
  const [formData, setFormData] = useState({
    symbol: 'BTC-USD',
    timeframe: '1d',
    start_date: '2023-01-01',
    end_date: '2024-01-01',
    initial_capital: 10000,
  });

  const [parameters, setParameters] = useState({});

  // Fetch available strategies
  useEffect(() => {
    const fetchStrategies = async () => {
      try {
        const res = await fetch(`${API_BASE}/strategies`);
        if (!res.ok) throw new Error('Failed to fetch strategies');
        const data = await res.json();
        setStrategies(data);
      } catch (err) {
        toast.error('Failed to load strategies');
        console.error(err);
      }
    };

    fetchStrategies();
  }, [toast]);

  // Handle strategy selection
  const handleStrategySelect = (strategy) => {
    setSelectedStrategy(strategy);
    // Initialize parameters with defaults
    const defaults = {};
    strategy.parameters.forEach(param => {
      defaults[param.name] = param.default;
    });
    setParameters(defaults);
    setResult(null);  // Clear previous results
  };

  // Handle parameter change
  const handleParameterChange = (paramName, value) => {
    setParameters(prev => ({
      ...prev,
      [paramName]: value,
    }));
  };

  // Handle form field change
  const handleFormChange = (field, value) => {
    setFormData(prev => ({
      ...prev,
      [field]: value,
    }));
  };

  // Execute backtest
  const handleExecuteBacktest = async () => {
    if (!selectedStrategy) {
      toast.error('Please select a strategy');
      return;
    }

    setLoading(true);
    try {
      const payload = {
        strategy_id: selectedStrategy.id,
        symbol: formData.symbol,
        timeframe: formData.timeframe,
        start_date: formData.start_date,
        end_date: formData.end_date,
        initial_capital: parseFloat(formData.initial_capital),
        parameters,
      };

      const res = await fetch(`${API_BASE}/preset`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const error = await res.json();
        throw new Error(error.detail || 'Backtest failed');
      }

      const result = await res.json();
      setResult(result);
      toast.success('Backtest completed!');
    } catch (err) {
      toast.error(err.message || 'Backtest execution failed');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="backtest-page">
      <div className="backtest-layout">
        {/* Left Panel: Strategy Selection */}
        <Card className="strategy-panel">
          <div className="panel-header">
            <h2>Preset Strategies</h2>
            <p className="panel-hint">Select a strategy to begin</p>
          </div>
          <StrategySelector
            strategies={strategies}
            onSelect={handleStrategySelect}
            selectedId={selectedStrategy?.id}
          />
        </Card>

        {/* Right Panel: Configuration & Results */}
        <div className="config-results-panel">
          {/* Backtest Configuration */}
          <Card className="config-card">
            <div className="panel-header">
              <h2>Backtest Configuration</h2>
            </div>

            <div className="config-form">
              <div className="form-group">
                <label>Symbol</label>
                <input
                  type="text"
                  value={formData.symbol}
                  onChange={(e) => handleFormChange('symbol', e.target.value)}
                  placeholder="e.g., BTC-USD"
                  className="form-input"
                />
              </div>

              <div className="form-group">
                <label>Timeframe</label>
                <select
                  value={formData.timeframe}
                  onChange={(e) => handleFormChange('timeframe', e.target.value)}
                  className="form-input"
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
                    value={formData.start_date}
                    onChange={(e) => handleFormChange('start_date', e.target.value)}
                    className="form-input"
                  />
                </div>
                <div className="form-group">
                  <label>End Date</label>
                  <input
                    type="date"
                    value={formData.end_date}
                    onChange={(e) => handleFormChange('end_date', e.target.value)}
                    className="form-input"
                  />
                </div>
              </div>

              <div className="form-group">
                <label>Initial Capital</label>
                <input
                  type="number"
                  value={formData.initial_capital}
                  onChange={(e) => handleFormChange('initial_capital', e.target.value)}
                  min="100"
                  className="form-input"
                />
              </div>
            </div>
          </Card>

          {/* Strategy Parameters */}
          <Card className="params-card">
            <StrategyParamForm
              strategy={selectedStrategy}
              parameters={parameters}
              onParameterChange={handleParameterChange}
              onSubmit={handleExecuteBacktest}
              loading={loading}
            />
          </Card>

          {/* Results */}
          {result && (
            <Card className="results-card">
              <div className="panel-header">
                <h2>Backtest Results</h2>
              </div>

              <div className="results-metrics">
                <div className="metric">
                  <span className="metric-label">Total Return</span>
                  <span className={`metric-value ${result.total_return >= 0 ? 'positive' : 'negative'}`}>
                    {result.return_percent.toFixed(2)}%
                  </span>
                </div>

                <div className="metric">
                  <span className="metric-label">Sharpe Ratio</span>
                  <span className="metric-value">{result.sharpe_ratio.toFixed(2)}</span>
                </div>

                <div className="metric">
                  <span className="metric-label">Max Drawdown</span>
                  <span className="metric-value negative">{(result.max_drawdown * 100).toFixed(2)}%</span>
                </div>

                <div className="metric">
                  <span className="metric-label">Win Rate</span>
                  <span className="metric-value">{(result.win_rate * 100).toFixed(1)}%</span>
                </div>

                <div className="metric">
                  <span className="metric-label">Total Trades</span>
                  <span className="metric-value">{result.total_trades}</span>
                </div>

                <div className="metric">
                  <span className="metric-label">Profit Factor</span>
                  <span className="metric-value">{result.profit_factor.toFixed(2)}</span>
                </div>
              </div>

              {result.trades && result.trades.length > 0 && (
                <div className="trades-section">
                  <h3>Trades ({result.trades.length})</h3>
                  <div className="trades-table">
                    <div className="table-header">
                      <div>Entry</div>
                      <div>Exit</div>
                      <div>Entry Price</div>
                      <div>Exit Price</div>
                      <div>P&L</div>
                      <div>P&L %</div>
                    </div>
                    {result.trades.slice(0, 10).map((trade, idx) => (
                      <div key={idx} className="table-row">
                        <div>{new Date(trade.entry_time).toLocaleDateString()}</div>
                        <div>{new Date(trade.exit_time).toLocaleDateString()}</div>
                        <div className="mono">${trade.entry_price.toFixed(2)}</div>
                        <div className="mono">${trade.exit_price.toFixed(2)}</div>
                        <div className={`mono ${trade.pnl >= 0 ? 'positive' : 'negative'}`}>
                          ${trade.pnl.toFixed(2)}
                        </div>
                        <div className={`mono ${trade.pnl_percent >= 0 ? 'positive' : 'negative'}`}>
                          {trade.pnl_percent.toFixed(2)}%
                        </div>
                      </div>
                    ))}
                  </div>
                  {result.trades.length > 10 && (
                    <p className="trades-overflow">... and {result.trades.length - 10} more trades</p>
                  )}
                </div>
              )}
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
