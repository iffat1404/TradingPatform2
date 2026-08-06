import React from 'react';
import { BacktestDashboard } from '../../components/backtest/BacktestDashboard';
import './trader-pages.css';

/**
 * BacktestingPage - Main backtesting interface
 *
 * Renders the complete backtesting dashboard with:
 * - Strategy selection sidebar
 * - Performance KPI cards
 * - Interactive equity curve
 * - Trade execution log
 */
export function BacktestingPage() {
  return (
    <div className="backtesting-page">
      <BacktestDashboard />
    </div>
  );
}
