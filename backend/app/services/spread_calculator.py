"""
Dynamic Platform Spread Calculation Service

Calculates bid/ask quotes and platform spreads for market data.
Applies volatility-adjusted markup to raw market data.
"""

from typing import Dict, Optional, Tuple
from datetime import datetime, timezone
import math


class SpreadConfig:
    """Configuration for spread calculation."""

    def __init__(
        self,
        markup_percent: float = 0.08,
        markup_fixed: float = 0.0,
        volatility_multiplier: float = 1.0,
        decimal_places: int = 3
    ):
        """
        Initialize spread configuration.

        Args:
            markup_percent: Platform markup as percentage (e.g., 0.08 for 0.08%)
            markup_fixed: Fixed markup per side in currency units (e.g., $0.02)
            volatility_multiplier: Multiplier based on ATR or VIX (default 1.0 = normal)
            decimal_places: Decimal places for rounding (default 3 for equities)
        """
        self.markup_percent = markup_percent
        self.markup_fixed = markup_fixed
        self.volatility_multiplier = max(0.5, volatility_multiplier)  # Clamp to 0.5-2.0 range
        self.decimal_places = decimal_places

    def set_volatility_multiplier(self, multiplier: float) -> None:
        """Update volatility multiplier based on market conditions."""
        self.volatility_multiplier = max(0.5, min(2.0, multiplier))


class PlatformSpreadCalculator:
    """Calculates dynamic bid/ask quotes and platform spreads."""

    def __init__(self, config: Optional[SpreadConfig] = None):
        """
        Initialize calculator with optional custom config.

        Args:
            config: SpreadConfig instance. Uses defaults if not provided.
        """
        self.config = config or SpreadConfig()

    def _round_price(self, price: float) -> float:
        """Round price to configured decimal places."""
        factor = 10 ** self.config.decimal_places
        return round(price * factor) / factor

    def _calculate_mid_price(self, raw_bid: float, raw_ask: float) -> float:
        """
        Calculate mid price from bid/ask.

        Formula: Mid = (Raw_Bid + Raw_Ask) / 2
        """
        if raw_bid < 0 or raw_ask < 0:
            raise ValueError("Bid and ask prices must be non-negative")
        if raw_bid > raw_ask:
            raise ValueError(f"Bid ({raw_bid}) cannot exceed ask ({raw_ask})")

        mid = (raw_bid + raw_ask) / 2
        return self._round_price(mid)

    def _calculate_base_spread_width(self, raw_bid: float, raw_ask: float) -> float:
        """
        Calculate base spread width from market data.

        Formula: Spread_Width = Raw_Ask - Raw_Bid
        """
        spread = raw_ask - raw_bid
        return self._round_price(spread)

    def _calculate_total_spread(
        self,
        base_spread: float,
        mid_price: float
    ) -> Tuple[float, float]:
        """
        Calculate total spread with platform markup and volatility adjustment.

        Returns:
            Tuple of (total_spread_width, spread_per_side)
        """
        # Calculate markup per side
        markup_from_percent = (mid_price * self.config.markup_percent / 100) / 2
        markup_per_side = markup_from_percent + (self.config.markup_fixed / 2)

        # Apply volatility multiplier
        adjusted_markup = markup_per_side * self.config.volatility_multiplier

        # Total spread = base spread + (markup per side * 2)
        total_spread = base_spread + (adjusted_markup * 2)

        return self._round_price(total_spread), self._round_price(adjusted_markup)

    def calculate_quotes(
        self,
        symbol: str,
        raw_bid: float,
        raw_ask: float,
        timestamp: Optional[datetime] = None,
        volatility_multiplier: Optional[float] = None
    ) -> Dict[str, float | str]:
        """
        Calculate platform bid/ask quotes and spread metrics.

        Args:
            symbol: Stock ticker symbol
            raw_bid: Raw market bid price
            raw_ask: Raw market ask price
            timestamp: Optional ISO timestamp. Uses current UTC if not provided.
            volatility_multiplier: Optional volatility adjustment (overrides config)

        Returns:
            Dictionary with platform quotes and spread metrics

        Raises:
            ValueError: If prices are invalid or bid > ask
        """
        # Use provided multiplier or config default
        if volatility_multiplier is not None:
            old_multiplier = self.config.volatility_multiplier
            self.config.set_volatility_multiplier(volatility_multiplier)

        try:
            # Calculate mid price
            mid = self._calculate_mid_price(raw_bid, raw_ask)

            # Calculate base spread width
            base_spread = self._calculate_base_spread_width(raw_bid, raw_ask)

            # Calculate total spread with markup
            total_spread, spread_per_side = self._calculate_total_spread(
                base_spread, mid
            )

            # Calculate platform quotes
            platform_bid = self._round_price(mid - (total_spread / 2))
            platform_ask = self._round_price(mid + (total_spread / 2))

            # Verify quotes
            absolute_spread = self._round_price(platform_ask - platform_bid)
            spread_percentage = (
                (absolute_spread / platform_ask * 100)
                if platform_ask > 0
                else 0.0
            )
            spread_percentage = self._round_price(spread_percentage)

            # Use provided timestamp or current UTC
            ts = timestamp or datetime.now(timezone.utc)
            iso_timestamp = ts.isoformat()

            return {
                "symbol": symbol,
                "midPrice": mid,
                "bid": platform_bid,
                "ask": platform_ask,
                "spread": absolute_spread,
                "spreadPercentage": spread_percentage,
                "timestamp": iso_timestamp,
                # Additional metrics for debugging/monitoring
                "rawBid": self._round_price(raw_bid),
                "rawAsk": self._round_price(raw_ask),
                "baseSpreadWidth": base_spread,
                "volatilityMultiplier": self.config.volatility_multiplier,
            }
        finally:
            # Restore original multiplier if it was overridden
            if volatility_multiplier is not None:
                self.config.volatility_multiplier = old_multiplier

    def calculate_quotes_from_close(
        self,
        symbol: str,
        close_price: float,
        spread_multiplier: float = 1.0,
        timestamp: Optional[datetime] = None,
        volatility_multiplier: Optional[float] = None
    ) -> Dict[str, float | str]:
        """
        Calculate quotes when only a close/trade price is available.
        Derives bid/ask from close price using spread_multiplier.

        Args:
            symbol: Stock ticker symbol
            close_price: Single market price (close, last trade, etc.)
            spread_multiplier: Multiplier to derive bid/ask (default 0.5 for ±0.05%)
            timestamp: Optional ISO timestamp
            volatility_multiplier: Optional volatility adjustment

        Returns:
            Dictionary with platform quotes and spread metrics
        """
        # Derive symmetric bid/ask from close price
        half_spread = close_price * spread_multiplier / 100
        raw_bid = close_price - half_spread
        raw_ask = close_price + half_spread

        return self.calculate_quotes(
            symbol=symbol,
            raw_bid=raw_bid,
            raw_ask=raw_ask,
            timestamp=timestamp,
            volatility_multiplier=volatility_multiplier
        )


# Global instance with default config
_default_calculator = PlatformSpreadCalculator()


def get_spread_calculator(config: Optional[SpreadConfig] = None) -> PlatformSpreadCalculator:
    """Get a spread calculator instance."""
    if config:
        return PlatformSpreadCalculator(config)
    return _default_calculator


def set_global_volatility(multiplier: float) -> None:
    """Update global volatility multiplier for all calculations."""
    _default_calculator.config.set_volatility_multiplier(multiplier)


def calculate_platform_spreads(
    symbol: str,
    raw_bid: float,
    raw_ask: float,
    volatility_multiplier: Optional[float] = None
) -> Dict[str, float | str]:
    """
    Convenience function to calculate platform spreads using default calculator.

    Args:
        symbol: Stock ticker symbol
        raw_bid: Raw market bid price
        raw_ask: Raw market ask price
        volatility_multiplier: Optional volatility adjustment

    Returns:
        Dictionary with platform quotes and spread metrics
    """
    timestamp = datetime.now(timezone.utc)
    return _default_calculator.calculate_quotes(
        symbol=symbol,
        raw_bid=raw_bid,
        raw_ask=raw_ask,
        timestamp=timestamp,
        volatility_multiplier=volatility_multiplier
    )
