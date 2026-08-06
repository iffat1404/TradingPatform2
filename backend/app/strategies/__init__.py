"""Strategies package - modular strategy engine for backtesting."""

from app.strategies.base import BaseStrategy, StrategyMetadata, ParameterSchema
from app.strategies.registry import (
    register_strategy,
    get_registry,
    StrategyRegistry,
)
from app.strategies.presets import (
    SmaCrossoverStrategy,
    RsiMeanReversionStrategy,
    MacdMomentumStrategy,
    SuperTrendStrategy,
)

__all__ = [
    "BaseStrategy",
    "StrategyMetadata",
    "ParameterSchema",
    "register_strategy",
    "get_registry",
    "StrategyRegistry",
    "SmaCrossoverStrategy",
    "RsiMeanReversionStrategy",
    "MacdMomentumStrategy",
    "SuperTrendStrategy",
]
