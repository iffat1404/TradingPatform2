import React from 'react';
import './BacktestSidebar.css';

/**
 * BacktestSidebar - Left sidebar with strategy selection and parameter controls
 *
 * Props:
 *   - strategies: Array of strategy metadata
 *   - selectedStrategy: Currently selected strategy
 *   - formState: Current form state
 *   - onSelectStrategy: Callback for strategy selection
 *   - onUpdateField: Callback for form field updates
 *   - onUpdateParameter: Callback for parameter updates
 *   - onRunBacktest: Callback to execute backtest
 *   - loading: Whether backtest is running
 */
export function BacktestSidebar({
  strategies,
  selectedStrategy,
  formState,
  onSelectStrategy,
  onUpdateField,
  onUpdateParameter,
  onRunBacktest,
  loading,
}) {
  const getCategoryBadgeClass = (category) => {
    return `category-badge category-${category}`;
  };

  return (
    <div className="backtest-sidebar">
      {/* Strategy Selector */}
      <div className="sidebar-section">
        <h3 className="section-title">Strategy</h3>

        {strategies.length > 0 ? (
          <div className="strategy-selector">
            <select
              value={selectedStrategy?.id || ''}
              onChange={(e) => onSelectStrategy(e.target.value)}
              className="strategy-dropdown"
            >
              {strategies.map(strategy => (
                <option key={strategy.id} value={strategy.id}>
                  {strategy.name}
                </option>
              ))}
            </select>

            {selectedStrategy && (
              <div className="strategy-info">
                <div className="strategy-header">
                  <h4 className="strategy-name">{selectedStrategy.name}</h4>
                  <span className={getCategoryBadgeClass(selectedStrategy.category)}>
                    {selectedStrategy.category === 'trend' && '📈'}
                    {selectedStrategy.category === 'mean_reversion' && '🔄'}
                    {selectedStrategy.category === 'momentum' && '⚡'}
                    {selectedStrategy.category.replace('_', ' ').toUpperCase()}
                  </span>
                </div>
                <p className="strategy-description">{selectedStrategy.description}</p>
              </div>
            )}
          </div>
        ) : (
          <div className="loading-skeleton">Loading strategies...</div>
        )}
      </div>

      {/* Strategy Parameters */}
      {selectedStrategy && selectedStrategy.parameters.length > 0 && (
        <div className="sidebar-section">
          <h3 className="section-title">Parameters</h3>

          <div className="parameters-list">
            {selectedStrategy.parameters.map(param => (
              <div key={param.name} className="parameter-field">
                <label className="param-label">
                  {param.name}
                  <span className="param-type">({param.type})</span>
                </label>

                {param.type === 'int' || param.type === 'float' ? (
                  <div className="param-number-group">
                    <div className="number-input-with-buttons">
                      <button
                        className="step-btn"
                        onClick={() => {
                          const current = formState.parameters[param.name] || param.default;
                          const step = param.type === 'float' ? 0.1 : 1;
                          onUpdateParameter(param.name, Math.max(param.min_value, current - step));
                        }}
                      >
                        −
                      </button>

                      <input
                        type="number"
                        value={formState.parameters[param.name] ?? param.default}
                        onChange={(e) => onUpdateParameter(param.name, parseFloat(e.target.value) || param.default)}
                        min={param.min_value}
                        max={param.max_value}
                        step={param.step || (param.type === 'float' ? '0.1' : '1')}
                        className="number-input"
                      />

                      <button
                        className="step-btn"
                        onClick={() => {
                          const current = formState.parameters[param.name] || param.default;
                          const step = param.type === 'float' ? 0.1 : 1;
                          onUpdateParameter(param.name, Math.min(param.max_value, current + step));
                        }}
                      >
                        +
                      </button>
                    </div>

                    {param.min_value !== null && param.max_value !== null && (
                      <input
                        type="range"
                        min={param.min_value}
                        max={param.max_value}
                        step={param.step || 1}
                        value={formState.parameters[param.name] ?? param.default}
                        onChange={(e) => onUpdateParameter(param.name, parseFloat(e.target.value))}
                        className="param-slider"
                      />
                    )}

                    <p className="param-hint">{param.description}</p>
                  </div>
                ) : param.type === 'bool' ? (
                  <select
                    value={formState.parameters[param.name] ? 'true' : 'false'}
                    onChange={(e) => onUpdateParameter(param.name, e.target.value === 'true')}
                    className="param-select"
                  >
                    <option value="true">True</option>
                    <option value="false">False</option>
                  </select>
                ) : (
                  <input
                    type="text"
                    value={formState.parameters[param.name] ?? param.default}
                    onChange={(e) => onUpdateParameter(param.name, e.target.value)}
                    className="param-text-input"
                  />
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Global Settings */}
      <div className="sidebar-section">
        <h3 className="section-title">Settings</h3>

        <div className="settings-fields">
          <div className="settings-field">
            <label>Symbol</label>
            <input
              type="text"
              value={formState.symbol}
              onChange={(e) => onUpdateField('symbol', e.target.value)}
              placeholder="BTC-USD"
              className="settings-input"
            />
          </div>

          <div className="settings-field">
            <label>Timeframe</label>
            <select
              value={formState.timeframe}
              onChange={(e) => onUpdateField('timeframe', e.target.value)}
              className="settings-select"
            >
              <option value="1m">1 Minute</option>
              <option value="5m">5 Minutes</option>
              <option value="15m">15 Minutes</option>
              <option value="1h">1 Hour</option>
              <option value="1d">1 Day</option>
            </select>
          </div>

          <div className="settings-field">
            <label>Start Date</label>
            <input
              type="date"
              value={formState.startDate}
              onChange={(e) => onUpdateField('startDate', e.target.value)}
              className="settings-input"
            />
          </div>

          <div className="settings-field">
            <label>End Date</label>
            <input
              type="date"
              value={formState.endDate}
              onChange={(e) => onUpdateField('endDate', e.target.value)}
              className="settings-input"
            />
          </div>

          <div className="settings-field">
            <label>Initial Capital ($)</label>
            <input
              type="number"
              value={formState.initialCapital}
              onChange={(e) => onUpdateField('initialCapital', e.target.value)}
              min="100"
              step="100"
              className="settings-input"
            />
          </div>
        </div>
      </div>

      {/* Run Backtest Button */}
      <button
        className={`run-backtest-btn ${loading ? 'loading' : ''}`}
        onClick={onRunBacktest}
        disabled={loading}
      >
        {loading ? (
          <>
            <span className="spinner"></span>
            Running Backtest...
          </>
        ) : (
          'Run Backtest'
        )}
      </button>
    </div>
  );
}
