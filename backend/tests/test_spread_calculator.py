"""
Unit tests for the Platform Spread Calculation Service.

Tests the spread calculation formulas, edge cases, and data contract.
"""

import pytest
from datetime import datetime, timezone
from app.services.spread_calculator import (
    SpreadConfig,
    PlatformSpreadCalculator,
    calculate_platform_spreads,
    set_global_volatility,
    get_spread_calculator
)


class TestSpreadConfig:
    """Test SpreadConfig initialization and updates."""

    def test_default_config(self):
        config = SpreadConfig()
        assert config.markup_percent == 0.08
        assert config.markup_fixed == 0.0
        assert config.volatility_multiplier == 1.0
        assert config.decimal_places == 3

    def test_custom_config(self):
        config = SpreadConfig(
            markup_percent=0.10,
            markup_fixed=0.02,
            volatility_multiplier=1.2,
            decimal_places=2
        )
        assert config.markup_percent == 0.10
        assert config.markup_fixed == 0.02
        assert config.volatility_multiplier == 1.2
        assert config.decimal_places == 2

    def test_volatility_multiplier_clamping(self):
        config = SpreadConfig()
        config.set_volatility_multiplier(0.1)  # Below 0.5
        assert config.volatility_multiplier == 0.5

        config.set_volatility_multiplier(3.0)  # Above 2.0
        assert config.volatility_multiplier == 2.0

        config.set_volatility_multiplier(1.5)  # Within range
        assert config.volatility_multiplier == 1.5


class TestPlatformSpreadCalculator:
    """Test core spread calculation logic."""

    def test_mid_price_calculation(self):
        calc = PlatformSpreadCalculator()
        mid = calc._calculate_mid_price(100.00, 100.10)
        assert mid == 100.05

    def test_mid_price_rounding(self):
        calc = PlatformSpreadCalculator()
        mid = calc._calculate_mid_price(100.001, 100.009)
        assert mid == 100.005

    def test_base_spread_width(self):
        calc = PlatformSpreadCalculator()
        spread = calc._calculate_base_spread_width(100.00, 100.10)
        assert spread == 0.1

    def test_invalid_bid_ask_raises_error(self):
        calc = PlatformSpreadCalculator()

        with pytest.raises(ValueError, match="Bid.*cannot exceed ask"):
            calc._calculate_mid_price(100.10, 100.00)

        with pytest.raises(ValueError, match="non-negative"):
            calc._calculate_mid_price(-100.00, 100.00)

    def test_calculate_quotes_basic(self):
        """Test basic spread calculation without volatility."""
        config = SpreadConfig(markup_percent=0.08, volatility_multiplier=1.0)
        calc = PlatformSpreadCalculator(config)

        spreads = calc.calculate_quotes(
            symbol="GOOG",
            raw_bid=183.200,
            raw_ask=183.282
        )

        assert spreads["symbol"] == "GOOG"
        assert spreads["midPrice"] == 183.241  # (183.200 + 183.282) / 2
        assert isinstance(spreads["bid"], float)
        assert isinstance(spreads["ask"], float)
        assert spreads["ask"] > spreads["bid"]
        assert spreads["bid"] < spreads["rawBid"]  # Platform bid lower than raw bid (worse for buyer)
        assert spreads["ask"] > spreads["rawAsk"]  # Platform ask higher than raw ask (worse for seller)
        assert spreads["spread"] > 0
        assert spreads["spreadPercentage"] > 0
        assert "timestamp" in spreads

    def test_spread_percentage_formula(self):
        """Verify spread percentage calculation: (spread / ask) * 100"""
        config = SpreadConfig(markup_percent=0.08)
        calc = PlatformSpreadCalculator(config)

        spreads = calc.calculate_quotes(
            symbol="GOOG",
            raw_bid=100.00,
            raw_ask=100.10
        )

        # Manually verify formula
        expected_percentage = (spreads["spread"] / spreads["ask"]) * 100
        assert abs(spreads["spreadPercentage"] - expected_percentage) < 0.001

    def test_volatility_multiplier_effect(self):
        """Verify volatility multiplier increases spreads."""
        config = SpreadConfig(markup_percent=0.08)
        calc = PlatformSpreadCalculator(config)

        spreads_normal = calc.calculate_quotes(
            symbol="GOOG",
            raw_bid=100.00,
            raw_ask=100.10,
            volatility_multiplier=1.0
        )

        spreads_high_vol = calc.calculate_quotes(
            symbol="GOOG",
            raw_bid=100.00,
            raw_ask=100.10,
            volatility_multiplier=1.5
        )

        # Higher volatility should result in wider spreads
        assert spreads_high_vol["spread"] > spreads_normal["spread"]
        assert spreads_high_vol["spreadPercentage"] > spreads_normal["spreadPercentage"]

    def test_decimal_precision(self):
        """Verify 3 decimal place precision for equities."""
        config = SpreadConfig(decimal_places=3)
        calc = PlatformSpreadCalculator(config)

        spreads = calc.calculate_quotes(
            symbol="GOOG",
            raw_bid=183.20001,
            raw_ask=183.28239
        )

        # Check that all prices have at most 3 decimal places
        for key in ["midPrice", "bid", "ask", "spread", "spreadPercentage"]:
            value_str = str(spreads[key])
            if "." in value_str:
                decimals = len(value_str.split(".")[1])
                assert decimals <= 3, f"{key} has {decimals} decimals: {value_str}"

    def test_timestamp_iso_format(self):
        """Verify timestamp is ISO 8601 format."""
        calc = PlatformSpreadCalculator()
        spreads = calc.calculate_quotes(
            symbol="GOOG",
            raw_bid=100.00,
            raw_ask=100.10
        )

        # Should be ISO format with T separator
        assert "T" in spreads["timestamp"]
        assert "Z" in spreads["timestamp"] or "+" in spreads["timestamp"]

    def test_custom_timestamp(self):
        """Verify custom timestamp is used."""
        calc = PlatformSpreadCalculator()
        ts = datetime(2026, 8, 6, 9, 25, 0, tzinfo=timezone.utc)

        spreads = calc.calculate_quotes(
            symbol="GOOG",
            raw_bid=100.00,
            raw_ask=100.10,
            timestamp=ts
        )

        assert "2026-08-06T09:25:00" in spreads["timestamp"]

    def test_quotes_from_close_price(self):
        """Test calculation from single close price."""
        config = SpreadConfig(markup_percent=0.08)
        calc = PlatformSpreadCalculator(config)

        spreads = calc.calculate_quotes_from_close(
            symbol="GOOG",
            close_price=183.241,
            spread_multiplier=0.5  # ±0.05%
        )

        assert spreads["symbol"] == "GOOG"
        assert spreads["midPrice"] == 183.241
        assert spreads["bid"] < spreads["midPrice"]
        assert spreads["ask"] > spreads["midPrice"]

    def test_data_contract_output_format(self):
        """Verify output matches the specified data contract."""
        calc = PlatformSpreadCalculator()
        spreads = calc.calculate_quotes(
            symbol="GOOG",
            raw_bid=183.200,
            raw_ask=183.282
        )

        # Required fields per spec
        required_fields = [
            "symbol",
            "midPrice",
            "bid",
            "ask",
            "spread",
            "spreadPercentage",
            "timestamp"
        ]

        for field in required_fields:
            assert field in spreads, f"Missing required field: {field}"
            assert spreads[field] is not None

    def test_markup_percent_effect(self):
        """Verify markup percentage is applied correctly."""
        # With 0.08% markup, mid is 100, the spread should increase
        config = SpreadConfig(markup_percent=0.08, markup_fixed=0.0)
        calc = PlatformSpreadCalculator(config)

        spreads = calc.calculate_quotes(
            symbol="TEST",
            raw_bid=100.00,
            raw_ask=100.00  # No market spread
        )

        # With 0.08% on each side of mid=100: 100 * 0.08 / 100 = 0.08
        # So bid should be ~100 - 0.04 = 99.96, ask ~100 + 0.04 = 100.04
        # Total spread should be 0.08
        assert spreads["bid"] < 100.0
        assert spreads["ask"] > 100.0
        assert spreads["spread"] > 0


class TestGlobalFunctions:
    """Test module-level convenience functions."""

    def test_calculate_platform_spreads(self):
        """Test convenience function."""
        spreads = calculate_platform_spreads(
            symbol="AAPL",
            raw_bid=150.00,
            raw_ask=150.10
        )

        assert spreads["symbol"] == "AAPL"
        assert isinstance(spreads["midPrice"], float)
        assert spreads["ask"] > spreads["bid"]

    def test_get_spread_calculator(self):
        """Test calculator factory function."""
        config = SpreadConfig(markup_percent=0.10)
        calc = get_spread_calculator(config)

        assert calc.config.markup_percent == 0.10

        default_calc = get_spread_calculator()
        assert default_calc is not None

    def test_set_global_volatility(self):
        """Test global volatility multiplier update."""
        set_global_volatility(1.5)
        spreads = calculate_platform_spreads(
            symbol="TEST",
            raw_bid=100.00,
            raw_ask=100.10
        )

        # Reset to default
        set_global_volatility(1.0)


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_very_small_prices(self):
        """Test with penny stocks."""
        calc = PlatformSpreadCalculator()
        spreads = calc.calculate_quotes(
            symbol="PENNY",
            raw_bid=0.10,
            raw_ask=0.15
        )

        assert spreads["bid"] > 0
        assert spreads["ask"] > spreads["bid"]
        assert spreads["spread"] > 0

    def test_very_large_prices(self):
        """Test with high-priced securities."""
        calc = PlatformSpreadCalculator()
        spreads = calc.calculate_quotes(
            symbol="BRK",
            raw_bid=500000.00,
            raw_ask=500100.00
        )

        assert spreads["ask"] > spreads["bid"]
        assert spreads["spread"] > 0

    def test_tight_market_spread(self):
        """Test with market spread < 1 cent."""
        calc = PlatformSpreadCalculator()
        spreads = calc.calculate_quotes(
            symbol="GOOG",
            raw_bid=183.24,
            raw_ask=183.25  # 1 cent spread
        )

        assert spreads["ask"] > spreads["bid"]
        assert spreads["spread"] > 0

    def test_identical_bid_ask(self):
        """Test when bid = ask (market limit scenario)."""
        calc = PlatformSpreadCalculator()
        spreads = calc.calculate_quotes(
            symbol="TEST",
            raw_bid=100.00,
            raw_ask=100.00
        )

        assert spreads["midPrice"] == 100.0
        assert spreads["bid"] < 100.0
        assert spreads["ask"] > 100.0
        assert spreads["spread"] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
