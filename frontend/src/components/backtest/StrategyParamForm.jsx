import React, { useEffect } from 'react';
import './StrategyParamForm.css';

/**
 * StrategyParamForm - Dynamic form for strategy parameters.
 *
 * Props:
 *   - strategy: Selected strategy with metadata
 *   - parameters: Current parameter values
 *   - onParameterChange: Callback when parameter changes
 *   - onSubmit: Callback when form is submitted
 *   - loading: Whether backtest is running
 */
export function StrategyParamForm({
  strategy,
  parameters,
  onParameterChange,
  onSubmit,
  loading = false,
}) {
  if (!strategy) {
    return <div className="param-form empty">Select a strategy to configure parameters</div>;
  }

  const handleParamChange = (paramName, value) => {
    // Convert value to correct type
    const param = strategy.parameters.find(p => p.name === paramName);
    let convertedValue = value;

    if (param.type === 'int') {
      convertedValue = parseInt(value, 10);
    } else if (param.type === 'float') {
      convertedValue = parseFloat(value);
    } else if (param.type === 'bool') {
      convertedValue = value === 'true';
    }

    onParameterChange(paramName, convertedValue);
  };

  return (
    <form className="param-form" onSubmit={(e) => { e.preventDefault(); onSubmit(); }}>
      <div className="form-header">
        <h3>Configure {strategy.name}</h3>
      </div>

      {strategy.parameters.length === 0 ? (
        <p className="no-params">This strategy has no configurable parameters.</p>
      ) : (
        <div className="param-inputs">
          {strategy.parameters.map((param) => {
            const value = parameters[param.name] ?? param.default;

            return (
              <div key={param.name} className="param-group">
                <label htmlFor={`param-${param.name}`} className="param-label">
                  {param.name}
                  <span className="param-type">({param.type})</span>
                </label>

                <p className="param-description">{param.description}</p>

                {param.type === 'bool' ? (
                  <select
                    id={`param-${param.name}`}
                    className="param-select"
                    value={value ? 'true' : 'false'}
                    onChange={(e) => handleParamChange(param.name, e.target.value)}
                  >
                    <option value="true">True</option>
                    <option value="false">False</option>
                  </select>
                ) : param.type === 'int' || param.type === 'float' ? (
                  <>
                    <div className="param-input-row">
                      <input
                        id={`param-${param.name}`}
                        type={param.type === 'float' ? 'number' : 'number'}
                        step={param.step || (param.type === 'float' ? '0.01' : '1')}
                        min={param.min_value ?? undefined}
                        max={param.max_value ?? undefined}
                        value={value}
                        className="param-input"
                        onChange={(e) => handleParamChange(param.name, e.target.value)}
                      />
                      <span className="param-value">{value}</span>
                    </div>

                    {param.min_value !== null && param.max_value !== null && (
                      <input
                        type="range"
                        min={param.min_value}
                        max={param.max_value}
                        step={param.step || 1}
                        value={value}
                        className="param-slider"
                        onChange={(e) => handleParamChange(param.name, e.target.value)}
                      />
                    )}

                    {param.min_value !== null && (
                      <small className="param-hint">
                        Range: {param.min_value} - {param.max_value}
                      </small>
                    )}
                  </>
                ) : (
                  <input
                    id={`param-${param.name}`}
                    type="text"
                    value={value}
                    className="param-input"
                    onChange={(e) => handleParamChange(param.name, e.target.value)}
                  />
                )}
              </div>
            );
          })}
        </div>
      )}

      <button
        type="submit"
        className="submit-btn"
        disabled={loading}
      >
        {loading ? 'Running backtest...' : 'Run backtest'}
      </button>
    </form>
  );
}
