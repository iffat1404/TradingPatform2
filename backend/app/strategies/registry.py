"""
Strategy Registry - Central registry for discovering and instantiating strategies.

Uses a decorator pattern to auto-register strategy classes.
"""

from typing import Dict, List, Type, Optional
from app.strategies.base import BaseStrategy, StrategyMetadata
from app.strategies.presets import (
    SmaCrossoverStrategy,
    RsiMeanReversionStrategy,
    MacdMomentumStrategy,
    SuperTrendStrategy,
)


class StrategyRegistry:
    """
    Singleton registry for managing available strategies.

    Strategies are auto-registered via @register decorator or manual registration.
    """

    def __init__(self):
        self._strategies: Dict[str, Type[BaseStrategy]] = {}
        self._metadata_cache: Dict[str, StrategyMetadata] = {}

    def register(self, strategy_class: Type[BaseStrategy]) -> Type[BaseStrategy]:
        """
        Register a strategy class.

        Can be used as a decorator or called directly.
        """
        # Instantiate to get metadata
        instance = strategy_class()
        meta = instance.metadata

        self._strategies[meta.id] = strategy_class
        self._metadata_cache[meta.id] = meta

        print(f"Registered strategy: {meta.id} ({meta.name})")
        return strategy_class

    def list_strategies(self) -> List[StrategyMetadata]:
        """Return metadata for all registered strategies."""
        return list(self._metadata_cache.values())

    def get_strategy(self, strategy_id: str) -> BaseStrategy:
        """
        Instantiate and return a strategy by ID.

        Raises:
            ValueError: If strategy ID not found.
        """
        if strategy_id not in self._strategies:
            available = ", ".join(self._strategies.keys())
            raise ValueError(
                f"Strategy {strategy_id} not found. Available: {available}"
            )
        strategy_class = self._strategies[strategy_id]
        return strategy_class()

    def get_metadata(self, strategy_id: str) -> Optional[StrategyMetadata]:
        """Get metadata for a strategy by ID."""
        return self._metadata_cache.get(strategy_id)


# Global registry instance
_registry = StrategyRegistry()


def register_strategy(strategy_class: Type[BaseStrategy]) -> Type[BaseStrategy]:
    """Decorator to register a strategy."""
    return _registry.register(strategy_class)


def get_registry() -> StrategyRegistry:
    """Get the global strategy registry instance."""
    return _registry


# Auto-register built-in strategies
_registry.register(SmaCrossoverStrategy)
_registry.register(RsiMeanReversionStrategy)
_registry.register(MacdMomentumStrategy)
_registry.register(SuperTrendStrategy)
