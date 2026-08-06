"""
Backtest Execution Service - Runs strategies with VectorBT and calculates performance metrics.
"""

from typing import Dict, Any, Tuple, Optional, List
from dataclasses import dataclass
from datetime import datetime
import pandas as pd
import numpy as np

try:
    import vectorbt as vbt
except ImportError:
    vbt = None


@dataclass
class BacktestResult:
    """Results from a backtest execution."""
    strategy_id: str
    symbol: str
    timeframe: str
    start_date: str
    end_date: str
    initial_capital: float
    final_value: float
    total_return: float
    return_percent: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    avg_trade_return: float
    best_trade: float
    worst_trade: float
    profit_factor: float
    equity_curve: List[float]
    timestamps: List[str]
    trades: List[Dict[str, Any]]
    parameters: Dict[str, Any]


class BacktestExecutor:
    """Executes strategies with VectorBT portfolio simulation."""

    @staticmethod
    def execute(
        strategy,
        df: pd.DataFrame,
        symbol: str,
        timeframe: str,
        start_date: str,
        end_date: str,
        initial_capital: float = 10000.0,
        **strategy_params
    ) -> BacktestResult:
        """
        Execute a backtest.

        Args:
            strategy: BaseStrategy instance
            df: OHLCV DataFrame with datetime index
            symbol: Symbol being tested
            timeframe: Timeframe (e.g., '1d', '1h')
            start_date: Start date string
            end_date: End date string
            initial_capital: Initial capital for backtest
            **strategy_params: Strategy-specific parameters

        Returns:
            BacktestResult with performance metrics.
        """
        if vbt is None:
            raise ImportError("vectorbt not installed. Install with: pip install vectorbt")

        # Validate strategy parameters
        strategy.validate_parameters(strategy_params)

        # Generate signals
        entries, exits = strategy.generate_signals(df, **strategy_params)

        # Ensure signals are clean (no NaN, convert to bool)
        entries = entries.fillna(False).astype(bool)
        exits = exits.fillna(False).astype(bool)

        # Create portfolio
        portfolio = vbt.Portfolio.from_signals(
            close=df["close"],
            entries=entries,
            exits=exits,
            init_cash=initial_capital,
            fees=0.001,  # 0.1% fee
            freq="D" if timeframe == "1d" else "H",
        )

        # Calculate metrics
        total_return = portfolio.total_return()
        sharpe_ratio = portfolio.sharpe_ratio()
        max_drawdown = portfolio.max_drawdown()

        # Trade statistics
        trades_df = portfolio.trades.records
        total_trades = len(trades_df) if trades_df is not None and len(trades_df) > 0 else 0
        winning_trades = 0
        losing_trades = 0
        winning_sum = 0.0
        losing_sum = 0.0
        best_trade = 0.0
        worst_trade = 0.0
        all_pnl = []

        if total_trades > 0:
            for idx, trade in trades_df.iterrows():
                pnl = float(trade['pnl'])
                all_pnl.append(pnl)
                if pnl > 0:
                    winning_trades += 1
                    winning_sum += pnl
                    best_trade = max(best_trade, pnl)
                elif pnl < 0:
                    losing_trades += 1
                    losing_sum += pnl
                    worst_trade = min(worst_trade, pnl)

        win_rate = winning_trades / total_trades if total_trades > 0 else 0.0
        avg_trade_return = np.mean(all_pnl) if all_pnl else 0.0
        profit_factor = abs(winning_sum / losing_sum) if losing_sum != 0 else 0.0

        # Extract trade log
        trade_log = BacktestExecutor._extract_trade_log(portfolio, df)

        # Equity curve
        equity_curve = portfolio.value().values.tolist()
        timestamps = [ts.isoformat() for ts in df.index]

        final_value = portfolio.final_value()

        return BacktestResult(
            strategy_id=strategy.metadata.id,
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital,
            final_value=float(final_value),
            total_return=float(total_return),
            return_percent=float(total_return * 100),
            sharpe_ratio=float(sharpe_ratio) if not np.isnan(sharpe_ratio) else 0.0,
            max_drawdown=float(max_drawdown) if not np.isnan(max_drawdown) else 0.0,
            win_rate=float(win_rate),
            total_trades=int(total_trades),
            winning_trades=int(winning_trades),
            losing_trades=int(losing_trades),
            avg_trade_return=float(avg_trade_return),
            best_trade=float(best_trade),
            worst_trade=float(worst_trade),
            profit_factor=float(profit_factor),
            equity_curve=equity_curve,
            timestamps=timestamps,
            trades=trade_log,
            parameters=strategy_params,
        )

    @staticmethod
    def _extract_trade_log(portfolio, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Extract trade log from portfolio."""
        trades_list = []
        trades_df = portfolio.trades.records

        if trades_df is None or len(trades_df) == 0:
            return trades_list

        for idx, trade in trades_df.iterrows():
            entry_idx = int(trade['entry_idx'])
            exit_idx = int(trade['exit_idx'])

            entry_time = df.index[entry_idx].isoformat() if entry_idx < len(df) else ""
            exit_time = df.index[exit_idx].isoformat() if exit_idx < len(df) else ""

            entry_price = float(trade['entry_price'])
            exit_price = float(trade['exit_price'])
            pnl = float(trade['pnl'])
            pnl_percent = (pnl / (entry_price * float(trade['size']))) * 100 if entry_price > 0 else 0.0

            trades_list.append({
                "entry_time": entry_time,
                "exit_time": exit_time,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "size": float(trade['size']),
                "pnl": pnl,
                "pnl_percent": pnl_percent,
                "duration_bars": exit_idx - entry_idx,
            })

        return trades_list
