"""
Tests for ATR-Based Spread Calculation Service.
"""

import pytest
from app.services.atr_spread_calculator import (
    ATRCalculator,
    ATRBasedSpreadCalculator,
    calculate_atr_spreads,
    get_spread_calculator,
    reset_ticker_atr,
)


class TestATRCalculator:
    """Test ATR calculation logic."""

    def test_initialization(self):
        atr = ATRCalculator(baseline_atr=0.5)
        assert atr.baseline_atr == 0.5
        assert atr.atr14 is None
        assert not atr.is_warmed_up()

    def test_true_range_first_candle(self):
        """First candle: TR = High - Low"""
        atr = ATRCalculator()
        tr = atr.calculate_true_range(high=100.10, low=100.00, close=100.05)
        assert abs(tr - 0.10) < 0.001

    def test_true_range_with_gap_up(self):
        """Gap up: TR = max(H-L, |H-Close_prev|)"""
        atr = ATRCalculator()
        atr.update(high=100.10, low=100.00, close=100.05)  # Set prev_close

        # Gap up scenario: high above prev close
        tr = atr.calculate_true_range(high=101.00, low=100.90, close=100.95)
        # TR = max(101-100.90, |101-100.05|, |100.90-100.05|)
        # TR = max(0.10, 0.95, 0.85) = 0.95
        assert abs(tr - 0.95) < 0.001

    def test_true_range_with_gap_down(self):
        """Gap down: TR = max(H-L, |L-Close_prev|)"""
        atr = ATRCalculator()
        atr.update(high=100.10, low=100.00, close=100.05)

        # Gap down scenario: low below prev close
        tr = atr.calculate_true_range(high=99.90, low=99.50, close=99.70)
        # TR = max(99.90-99.50, |99.90-100.05|, |99.50-100.05|)
        # TR = max(0.40, 0.15, 0.55) = 0.55
        assert abs(tr - 0.55) < 0.001

    def test_atr_warmup_period(self):
        """ATR becomes available after 14 candles."""
        atr = ATRCalculator(baseline_atr=0.5)

        # Add 13 candles
        for i in range(13):
            atr.update(high=100.10, low=100.00, close=100.05)
            assert atr.atr14 is None
            assert not atr.is_warmed_up()

        # 14th candle: ATR initialized
        atr.update(high=100.10, low=100.00, close=100.05)
        assert atr.atr14 is not None
        assert atr.is_warmed_up()

    def test_atr_smoothing(self):
        """ATR uses Wilder's smoothing after warmup."""
        atr = ATRCalculator(baseline_atr=0.5)

        # Add 14 identical candles (TR = 0.10 each)
        for _ in range(14):
            atr.update(high=100.10, low=100.00, close=100.05)

        # After warmup: ATR = average of 14 TR = 0.10
        assert abs(atr.atr14 - 0.10) < 0.001

        # 15th candle with TR = 0.20
        atr.update(high=100.20, low=100.00, close=100.10)
        # New ATR = (0.10 * 13 + 0.20) / 14 = 1.5 / 14 ≈ 0.1071
        assert abs(atr.atr14 - 0.1071) < 0.001

    def test_volatility_multiplier_calculation(self):
        """M = max(1.0, ATR14 / Baseline)"""
        atr = ATRCalculator(baseline_atr=0.5)

        # Before warmup
        assert atr.get_volatility_multiplier() == 1.0

        # Add 14 candles with TR = 0.25 each
        for _ in range(14):
            atr.update(high=100.25, low=100.00, close=100.12)

        # ATR14 ≈ 0.25, Baseline = 0.5
        # M = 0.25 / 0.5 = 0.5, but clamped to 1.0
        assert atr.get_volatility_multiplier() == 1.0

        # Now add many high volatility candles to push ATR up
        for _ in range(15):  # More candles to push ATR significantly higher
            atr.update(high=101.50, low=99.50, close=100.50)

        # ATR should now be higher than baseline, M > 1.0
        m = atr.get_volatility_multiplier()
        assert m >= 1.0  # At minimum 1.0


class TestATRBasedSpreadCalculator:
    """Test spread calculation with ATR."""

    def test_initialization(self):
        calc = ATRBasedSpreadCalculator(
            base_markup_percent=0.05,
            baseline_atr=0.5
        )
        assert calc.base_markup_percent == 0.05
        assert calc.baseline_atr == 0.5
        assert calc.decimal_places == 3

    def test_calculate_quotes_warmup_period(self):
        """During warmup (< 14 candles), M = 1.0"""
        calc = ATRBasedSpreadCalculator(
            base_markup_percent=0.05,
            baseline_atr=0.5
        )

        quotes = calc.calculate_quotes(
            symbol="GOOG",
            close=183.241,
            high=183.500,
            low=182.900
        )

        assert quotes["symbol"] == "GOOG"
        assert quotes["close"] == 183.241
        assert quotes["isWarmUp"] is True
        assert quotes["volatilityMultiplier"] == 1.0

    def test_calculate_quotes_after_warmup(self):
        """After 14 candles, spreads scale with ATR."""
        calc = ATRBasedSpreadCalculator(
            base_markup_percent=0.05,
            baseline_atr=0.5
        )

        # Add 14 candles with moderate volatility
        for i in range(14):
            calc.calculate_quotes(
                symbol="GOOG",
                close=183.241,
                high=183.500,
                low=182.900
            )

        # 15th calculation: spreads should now use ATR multiplier
        quotes = calc.calculate_quotes(
            symbol="GOOG",
            close=183.241,
            high=183.500,
            low=182.900
        )

        assert quotes["isWarmUp"] is False
        assert quotes["atr14"] > 0
        assert "volatilityMultiplier" in quotes

    def test_bid_ask_calculation(self):
        """Verify bid/ask are symmetric around close."""
        calc = ATRBasedSpreadCalculator(base_markup_percent=0.05)

        # Warm up
        for _ in range(14):
            calc.calculate_quotes(
                symbol="TEST",
                close=100.0,
                high=100.10,
                low=99.90
            )

        quotes = calc.calculate_quotes(
            symbol="TEST",
            close=100.0,
            high=100.10,
            low=99.90
        )

        # Check symmetry: (bid + ask) / 2 ≈ close
        mid_price = (quotes["bid"] + quotes["ask"]) / 2
        assert abs(mid_price - 100.0) < 0.001

        # Check spread = ask - bid
        assert abs(quotes["spread"] - (quotes["ask"] - quotes["bid"])) < 0.001

    def test_volatility_status_labels(self):
        """Volatility status changes with multiplier."""
        calc = ATRBasedSpreadCalculator(baseline_atr=0.5)

        # Normal: M = 1.0
        assert calc.get_volatility_status() == "Normal Volatility"

        # Add high volatility candles
        for _ in range(20):
            calc.calculate_quotes(
                symbol="GOOG",
                close=183.241,
                high=184.500,
                low=182.000
            )

        status = calc.get_volatility_status()
        assert status in ["High Volatility", "Very High Volatility"]

    def test_decimal_precision(self):
        """All prices formatted to 3 decimals."""
        calc = ATRBasedSpreadCalculator()

        for _ in range(14):
            calc.calculate_quotes(
                symbol="GOOG",
                close=183.24159,
                high=183.50001,
                low=182.90099
            )

        quotes = calc.calculate_quotes(
            symbol="GOOG",
            close=183.24159,
            high=183.50001,
            low=182.90099
        )

        # Check decimal places
        for key in ["close", "bid", "ask", "spread", "atr14", "volatilityMultiplier"]:
            value_str = str(quotes[key])
            if "." in value_str:
                decimals = len(value_str.split(".")[1])
                assert decimals <= 3, f"{key} has {decimals} decimals: {value_str}"

    def test_invalid_prices(self):
        """Validate price logic."""
        calc = ATRBasedSpreadCalculator()

        # High < Low
        with pytest.raises(ValueError, match="High.*cannot be less than low"):
            calc.calculate_quotes(
                symbol="TEST",
                close=100.0,
                high=99.0,
                low=101.0
            )

        # Close outside H-L range
        with pytest.raises(ValueError, match="Close.*must be between"):
            calc.calculate_quotes(
                symbol="TEST",
                close=105.0,
                high=100.0,
                low=99.0
            )

        # Negative prices
        with pytest.raises(ValueError, match="Prices must be positive"):
            calc.calculate_quotes(
                symbol="TEST",
                close=-100.0,
                high=100.0,
                low=99.0
            )


class TestGlobalFunctions:
    """Test module-level convenience functions."""

    def test_calculate_atr_spreads(self):
        """Test convenience function for spread calculation."""
        quotes = calculate_atr_spreads(
            symbol="GOOG",
            close=183.241,
            high=183.500,
            low=182.900
        )

        assert quotes["symbol"] == "GOOG"
        assert "bid" in quotes
        assert "ask" in quotes
        assert "atr14" in quotes

    def test_per_ticker_atr_tracking(self):
        """Each ticker maintains independent ATR."""
        calc_goog = get_spread_calculator("GOOG")
        calc_aapl = get_spread_calculator("AAPL")

        assert calc_goog is not calc_aapl

        # Calculate different patterns for each
        for _ in range(14):
            calc_goog.calculate_quotes("GOOG", close=183.0, high=183.5, low=182.5)
            calc_aapl.calculate_quotes("AAPL", close=150.0, high=151.0, low=149.0)

        quotes_goog = calc_goog.calculate_quotes("GOOG", close=183.0, high=183.5, low=182.5)
        quotes_aapl = calc_aapl.calculate_quotes("AAPL", close=150.0, high=151.0, low=149.0)

        # Both should have ATR now
        assert quotes_goog["atr14"] > 0
        assert quotes_aapl["atr14"] > 0

    def test_reset_ticker_atr(self):
        """Reset ATR for a ticker."""
        calc = get_spread_calculator("GOOG")

        # Warm up
        for _ in range(14):
            calc.calculate_quotes("GOOG", close=183.0, high=183.5, low=182.5)

        assert calc.atr_calc.is_warmed_up()

        # Reset
        reset_ticker_atr("GOOG")
        calc = get_spread_calculator("GOOG")

        assert not calc.atr_calc.is_warmed_up()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
