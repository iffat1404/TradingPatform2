import React, { useState, useEffect } from 'react';
import './StrategySelector.css';

/**
 * StrategySelector - Displays available preset strategies in a grid.
 *
 * Props:
 *   - strategies: Array of strategy metadata objects
 *   - onSelect: Callback when strategy is selected
 *   - selectedId: Currently selected strategy ID
 */
export function StrategySelector({ strategies, onSelect, selectedId }) {
  const categories = {
    trend: [],
    mean_reversion: [],
    momentum: [],
  };

  // Group strategies by category
  strategies.forEach(strategy => {
    const cat = strategy.category || 'trend';
    if (!categories[cat]) categories[cat] = [];
    categories[cat].push(strategy);
  });

  return (
    <div className="strategy-selector">
      {Object.entries(categories).map(([category, strats]) => (
        strats.length > 0 && (
          <div key={category} className="strategy-category">
            <h3 className="category-title">
              {category === 'trend' && '📈 Trend Following'}
              {category === 'mean_reversion' && '🔄 Mean Reversion'}
              {category === 'momentum' && '⚡ Momentum'}
            </h3>

            <div className="strategy-grid">
              {strats.map(strategy => (
                <div
                  key={strategy.id}
                  className={`strategy-card ${selectedId === strategy.id ? 'selected' : ''}`}
                  onClick={() => onSelect(strategy)}
                >
                  <div className="strategy-header">
                    <h4 className="strategy-name">{strategy.name}</h4>
                    <span className="strategy-id">#{strategy.id}</span>
                  </div>

                  <p className="strategy-description">{strategy.description}</p>

                  <div className="strategy-params-summary">
                    <small>
                      {strategy.parameters.length} parameters
                    </small>
                  </div>

                  {selectedId === strategy.id && (
                    <div className="selection-indicator">✓</div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )
      ))}
    </div>
  );
}
