"""
Concrete Strategy Implementations - Preset trading strategies for backtesting.
"""

from typing import Tuple
import pandas as pd
import numpy as np
from app.strategies.base import BaseStrategy, StrategyMetadata, ParameterSchema


class SmaCrossoverStrategy(BaseStrategy):
    """
    Simple Moving Average Crossover Strategy.

    Generates buy signals when fast MA crosses above slow MA (bullish).
    Generates sell signals when fast MA crosses below slow MA (bearish).
    """

    @property
    def metadata(self) -> StrategyMetadata:
        return StrategyMetadata(
            id="sma_crossover",
            name="SMA Crossover",
            description="Buy when fast MA > slow MA, sell when fast MA < slow MA. Classic trend-following strategy.",
            category="trend",
            parameters=[
                ParameterSchema(
                    name="fast_window",
                    type="int",
                    default=20,
                    min_value=2,
                    max_value=100,
                    description="Fast moving average period",
                    step=1
                ),
                ParameterSchema(
                    name="slow_window",
                    type="int",
                    default=50,
                    min_value=2,
                    max_value=250,
                    description="Slow moving average period",
                    step=1
                ),
            ],
        )

    def generate_signals(self, df: pd.DataFrame, **params) -> Tuple[pd.Series, pd.Series]:
        """Generate SMA crossover signals."""
        fast_window = params.get("fast_window", 20)
        slow_window = params.get("slow_window", 50)

        # Validate
        if fast_window >= slow_window:
            raise ValueError("fast_window must be < slow_window")
        if len(df) < slow_window:
            raise ValueError(f"Need at least {slow_window} bars, got {len(df)}")

        close = df["close"]

        # Calculate MAs
        fast_ma = close.rolling(window=fast_window).mean()
        slow_ma = close.rolling(window=slow_window).mean()

        # Signals: True where crossover happens
        entries = (fast_ma > slow_ma) & (fast_ma.shift(1) <= slow_ma.shift(1))
        exits = (fast_ma < slow_ma) & (fast_ma.shift(1) >= slow_ma.shift(1))

        return entries.astype(float), exits.astype(float)


class RsiMeanReversionStrategy(BaseStrategy):
    """
    RSI Mean Reversion Strategy.

    Buys when RSI < oversold threshold (mean reversion up).
    Sells when RSI > overbought threshold (mean reversion down).
    """

    @property
    def metadata(self) -> StrategyMetadata:
        return StrategyMetadata(
            id="rsi_mean_reversion",
            name="RSI Mean Reversion",
            description="Buy on oversold (RSI < 30), sell on overbought (RSI > 70). Mean reversion strategy.",
            category="mean_reversion",
            parameters=[
                ParameterSchema(
                    name="rsi_period",
                    type="int",
                    default=14,
                    min_value=2,
                    max_value=50,
                    description="RSI period",
                    step=1
                ),
                ParameterSchema(
                    name="oversold",
                    type="int",
                    default=30,
                    min_value=1,
                    max_value=50,
                    description="Oversold threshold",
                    step=1
                ),
                ParameterSchema(
                    name="overbought",
                    type="int",
                    default=70,
                    min_value=50,
                    max_value=99,
                    description="Overbought threshold",
                    step=1
                ),
            ],
        )

    def generate_signals(self, df: pd.DataFrame, **params) -> Tuple[pd.Series, pd.Series]:
        """Generate RSI mean reversion signals."""
        rsi_period = params.get("rsi_period", 14)
        oversold = params.get("oversold", 30)
        overbought = params.get("overbought", 70)

        if len(df) < rsi_period:
            raise ValueError(f"Need at least {rsi_period} bars, got {len(df)}")
        if oversold >= overbought:
            raise ValueError("oversold must be < overbought")

        close = df["close"]

        # Calculate RSI
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=rsi_period).mean()
        rs = gain / loss.replace(0, 1e-10)
        rsi = 100 - (100 / (1 + rs))

        # Signals
        entries = rsi < oversold
        exits = rsi > overbought

        return entries.astype(float), exits.astype(float)


class MacdMomentumStrategy(BaseStrategy):
    """
    MACD Momentum Strategy.

    Buys when MACD crosses above signal line (bullish momentum).
    Sells when MACD crosses below signal line (bearish momentum).
    """

    @property
    def metadata(self) -> StrategyMetadata:
        return StrategyMetadata(
            id="macd_momentum",
            name="MACD Momentum",
            description="Buy when MACD > Signal, sell when MACD < Signal. Momentum-based strategy.",
            category="momentum",
            parameters=[
                ParameterSchema(
                    name="fast_period",
                    type="int",
                    default=12,
                    min_value=2,
                    max_value=50,
                    description="Fast EMA period",
                    step=1
                ),
                ParameterSchema(
                    name="slow_period",
                    type="int",
                    default=26,
                    min_value=2,
                    max_value=100,
                    description="Slow EMA period",
                    step=1
                ),
                ParameterSchema(
                    name="signal_period",
                    type="int",
                    default=9,
                    min_value=2,
                    max_value=30,
                    description="Signal line EMA period",
                    step=1
                ),
            ],
        )

    def generate_signals(self, df: pd.DataFrame, **params) -> Tuple[pd.Series, pd.Series]:
        """Generate MACD momentum signals."""
        fast_period = params.get("fast_period", 12)
        slow_period = params.get("slow_period", 26)
        signal_period = params.get("signal_period", 9)

        if len(df) < slow_period + signal_period:
            raise ValueError(
                f"Need at least {slow_period + signal_period} bars, got {len(df)}"
            )

        close = df["close"]

        # Calculate MACD
        fast_ema = close.ewm(span=fast_period).mean()
        slow_ema = close.ewm(span=slow_period).mean()
        macd = fast_ema - slow_ema
        signal = macd.ewm(span=signal_period).mean()

        # Signals: crossovers
        entries = (macd > signal) & (macd.shift(1) <= signal.shift(1))
        exits = (macd < signal) & (macd.shift(1) >= signal.shift(1))

        return entries.astype(float), exits.astype(float)


class SuperTrendStrategy(BaseStrategy):
    """
    SuperTrend Strategy.

    Uses ATR-based bands to identify trend changes.
    Buys on uptrend signal, sells on downtrend signal.
    """

    @property
    def metadata(self) -> StrategyMetadata:
        return StrategyMetadata(
            id="supertrend",
            name="SuperTrend",
            description="ATR-based trend following. Buy on uptrend, sell on downtrend.",
            category="trend",
            parameters=[
                ParameterSchema(
                    name="atr_period",
                    type="int",
                    default=10,
                    min_value=2,
                    max_value=50,
                    description="ATR period",
                    step=1
                ),
                ParameterSchema(
                    name="multiplier",
                    type="float",
                    default=3.0,
                    min_value=0.5,
                    max_value=10.0,
                    description="ATR multiplier for bands",
                    step=0.1
                ),
            ],
        )

    def generate_signals(self, df: pd.DataFrame, **params) -> Tuple[pd.Series, pd.Series]:
        """Generate SuperTrend signals."""
        atr_period = params.get("atr_period", 10)
        multiplier = params.get("multiplier", 3.0)

        if len(df) < atr_period:
            raise ValueError(f"Need at least {atr_period} bars, got {len(df)}")

        high = df["high"]
        low = df["low"]
        close = df["close"]

        # Calculate ATR
        tr = pd.concat([
            high - low,
            (high - close.shift()).abs(),
            (low - close.shift()).abs(),
        ], axis=1).max(axis=1)
        atr = tr.rolling(window=atr_period).mean()

        # Calculate basic bands
        hl_avg = (high + low) / 2
        basic_ub = hl_avg + multiplier * atr
        basic_lb = hl_avg - multiplier * atr

        # Calculate final bands (smoothed)
        final_ub = basic_ub.copy()
        final_lb = basic_lb.copy()

        for i in range(1, len(final_ub)):
            final_ub.iloc[i] = min(basic_ub.iloc[i], final_ub.iloc[i - 1]) if close.iloc[i - 1] > final_ub.iloc[i - 1] else basic_ub.iloc[i]
            final_lb.iloc[i] = max(basic_lb.iloc[i], final_lb.iloc[i - 1]) if close.iloc[i - 1] < final_lb.iloc[i - 1] else basic_lb.iloc[i]

        # Trend determination
        trend = pd.Series(0, index=close.index)
        for i in range(1, len(trend)):
            if close.iloc[i] <= final_ub.iloc[i]:
                trend.iloc[i] = 1
            else:
                trend.iloc[i] = -1

        # Signals
        entries = (trend == -1) & (trend.shift(1) == 1)
        exits = (trend == 1) & (trend.shift(1) == -1)

        return entries.astype(float), exits.astype(float)
