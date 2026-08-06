"""
ATR-Based Dynamic Spread Calculation Service

Calculates bid/ask quotes and platform spreads using Average True Range (ATR)
to scale markup based on real-time market volatility.

Every 1-minute candle tick updates the rolling ATR and recalculates spreads dynamically.
"""

from typing import Dict, Optional, Tuple, List
from collections import deque
from datetime import datetime, timezone
import math


class ATRCalculator:
    """Calculates 14-period rolling ATR from OHLCV data."""

    def __init__(self, baseline_atr: float = 0.5):
        """
        Initialize ATR calculator.

        Args:
            baseline_atr: Baseline ATR for calm market conditions (default 0.5)
        """
        self.baseline_atr = baseline_atr
        self.tr_buffer: deque = deque(maxlen=14)  # Rolling window of True Range
        self.atr14 = None  # Current 14-period ATR
        self.prev_close = None  # Previous candle close for TR calculation

    def calculate_true_range(self, high: float, low: float, close: float) -> float:
        """
        Calculate True Range for current candle.

        Formula: TR = max(High - Low, |High - Close_prev|, |Low - Close_prev|)
        """
        if self.prev_close is None:
            # First candle, use high-low range
            tr = high - low
        else:
            tr = max(
                high - low,
                abs(high - self.prev_close),
                abs(low - self.prev_close)
            )
        return tr

    def update(self, high: float, low: float, close: float) -> None:
        """
        Update ATR with new candle data.

        Maintains 14-period rolling window and calculates smoothed ATR.
        """
        # Calculate True Range
        tr = self.calculate_true_range(high, low, close)
        self.tr_buffer.append(tr)

        # Calculate or update ATR
        if len(self.tr_buffer) == 14:
            if self.atr14 is None:
                # Initial ATR: simple average of first 14 TR values
                self.atr14 = sum(self.tr_buffer) / 14
            else:
                # Smoothed ATR: Wilder's smoothing formula
                self.atr14 = ((self.atr14 * 13) + tr) / 14

        # Update previous close for next iteration
        self.prev_close = close

    def get_atr14(self) -> Optional[float]:
        """Get current 14-period ATR, None if not yet warmed up."""
        return self.atr14

    def get_volatility_multiplier(self) -> float:
        """
        Get volatility multiplier M = ATR14 / Baseline ATR.
        Returns at least 1.0 (no compression).
        """
        if self.atr14 is None:
            return 1.0
        return max(1.0, self.atr14 / self.baseline_atr)

    def is_warmed_up(self) -> bool:
        """Check if ATR calculation has enough data (14+ candles)."""
        return len(self.tr_buffer) >= 14


class ATRBasedSpreadCalculator:
    """Calculates dynamic bid/ask quotes using ATR-based volatility scaling."""

    def __init__(
        self,
        base_markup_percent: float = 0.05,
        baseline_atr: float = 0.5,
        decimal_places: int = 3
    ):
        """
        Initialize ATR-based spread calculator.

        Args:
            base_markup_percent: Base spread markup as percentage of close (0.05 = 5 bps)
            baseline_atr: Baseline ATR for normal market conditions
            decimal_places: Decimal places for rounding (3 for equities)
        """
        self.base_markup_percent = base_markup_percent
        self.baseline_atr = baseline_atr
        self.decimal_places = decimal_places
        self.atr_calc = ATRCalculator(baseline_atr)

    def _round_price(self, price: float) -> float:
        """Round price to configured decimal places."""
        factor = 10 ** self.decimal_places
        return round(price * factor) / factor

    def calculate_quotes(
        self,
        symbol: str,
        close: float,
        high: float,
        low: float,
        timestamp: Optional[datetime] = None
    ) -> Dict:
        """
        Calculate dynamic bid/ask quotes based on ATR.

        Args:
            symbol: Stock ticker symbol
            close: Current close price
            high: Current candle high
            low: Current candle low
            timestamp: Optional ISO timestamp

        Returns:
            Dictionary with bid, ask, spread, ATR, and volatility metrics
        """
        if close <= 0 or high <= 0 or low <= 0:
            raise ValueError("Prices must be positive")
        if high < low:
            raise ValueError(f"High ({high}) cannot be less than low ({low})")
        if close < low or close > high:
            raise ValueError(f"Close ({close}) must be between low ({low}) and high ({high})")

        # Update ATR with latest candle
        self.atr_calc.update(high, low, close)

        # Get current ATR and volatility multiplier
        atr14 = self.atr_calc.get_atr14() or 0.0
        volatility_multiplier = self.atr_calc.get_volatility_multiplier()

        # Calculate base spread (as percentage of close price)
        base_spread_width = close * (self.base_markup_percent / 100)

        # Apply volatility multiplier
        total_spread = base_spread_width * volatility_multiplier
        half_spread = total_spread / 2

        # Calculate platform quotes
        platform_bid = self._round_price(close - half_spread)
        platform_ask = self._round_price(close + half_spread)
        absolute_spread = self._round_price(platform_ask - platform_bid)
        spread_percentage = (
            (absolute_spread / platform_ask * 100) if platform_ask > 0 else 0.0
        )
        spread_percentage = self._round_price(spread_percentage)

        # Timestamp
        ts = timestamp or datetime.now(timezone.utc)
        iso_timestamp = ts.isoformat()

        return {
            "symbol": symbol,
            "close": self._round_price(close),
            "bid": platform_bid,
            "ask": platform_ask,
            "spread": absolute_spread,
            "spreadPercentage": spread_percentage,
            "atr14": self._round_price(atr14),
            "volatilityMultiplier": self._round_price(volatility_multiplier),
            "timestamp": iso_timestamp,
            "isWarmUp": not self.atr_calc.is_warmed_up(),
        }

    def get_volatility_status(self) -> str:
        """Get volatility status label based on multiplier."""
        m = self.atr_calc.get_volatility_multiplier()
        if m >= 1.5:
            return "Very High Volatility"
        elif m >= 1.2:
            return "High Volatility"
        elif m >= 1.0:
            return "Normal Volatility"
        else:
            return "Low Volatility"


# Global instance manager for per-ticker ATR tracking
_calculator_instances: Dict[str, ATRBasedSpreadCalculator] = {}


def get_spread_calculator(
    ticker: str,
    base_markup_percent: float = 0.05,
    baseline_atr: float = 0.5
) -> ATRBasedSpreadCalculator:
    """
    Get or create an ATR-based calculator for a specific ticker.

    Each ticker maintains its own independent ATR history.
    """
    if ticker not in _calculator_instances:
        _calculator_instances[ticker] = ATRBasedSpreadCalculator(
            base_markup_percent=base_markup_percent,
            baseline_atr=baseline_atr
        )
    return _calculator_instances[ticker]


def calculate_atr_spreads(
    symbol: str,
    close: float,
    high: float,
    low: float
) -> Dict:
    """
    Convenience function to calculate spreads for a ticker.

    Maintains per-ticker ATR history automatically.
    """
    calculator = get_spread_calculator(symbol)
    timestamp = datetime.now(timezone.utc)
    return calculator.calculate_quotes(
        symbol=symbol,
        close=close,
        high=high,
        low=low,
        timestamp=timestamp
    )


def reset_ticker_atr(ticker: str) -> None:
    """Reset ATR calculator for a ticker (e.g., at market open)."""
    if ticker in _calculator_instances:
        del _calculator_instances[ticker]


def get_all_atr_states() -> Dict[str, Dict]:
    """Get current ATR state for all tracked tickers for monitoring."""
    return {
        ticker: {
            "atr14": calc.atr_calc.get_atr14(),
            "volatilityMultiplier": calc.atr_calc.get_volatility_multiplier(),
            "isWarmUp": not calc.atr_calc.is_warmed_up(),
            "bufferSize": len(calc.atr_calc.tr_buffer),
        }
        for ticker, calc in _calculator_instances.items()
    }
