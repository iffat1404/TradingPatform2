"""
Base Strategy Class - Abstract foundation for all trading strategies.

Defines the interface for signal generation and parameter schema.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Tuple, Optional, List
from dataclasses import dataclass, field
import pandas as pd


@dataclass
class ParameterSchema:
    """Describes a single strategy parameter."""
    name: str
    type: str  # 'int', 'float', 'bool', 'string'
    default: Any
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    description: str = ""
    step: Optional[float] = None  # For slider UI


@dataclass
class StrategyMetadata:
    """Metadata about a strategy for display and discovery."""
    id: str
    name: str
    description: str
    category: str  # 'trend', 'mean_reversion', 'momentum'
    parameters: List[ParameterSchema] = field(default_factory=list)
    version: str = "1.0.0"


class BaseStrategy(ABC):
    """
    Abstract base class for all trading strategies.

    Strategies implement signal generation logic and define their parameter schema.
    """

    def __init__(self, **kwargs):
        """Initialize strategy with optional parameters."""
        self.params = kwargs

    @property
    @abstractmethod
    def metadata(self) -> StrategyMetadata:
        """Return strategy metadata for display and parameter validation."""
        pass

    @abstractmethod
    def generate_signals(
        self,
        df: pd.DataFrame,
        **params
    ) -> Tuple[pd.Series, pd.Series]:
        """
        Generate entry and exit signals for the given OHLCV data.

        Args:
            df: DataFrame with OHLCV columns (open, high, low, close, volume)
            **params: Strategy-specific parameters

        Returns:
            Tuple of (entries, exits) as boolean Series or float signals.
            True/1.0 = signal, False/0.0 = no signal.

        Raises:
            ValueError: If parameters are invalid or DataFrame is malformed.
        """
        pass

    def validate_parameters(self, params: Dict[str, Any]) -> None:
        """
        Validate parameters against schema.

        Raises:
            ValueError: If any parameter is invalid.
        """
        meta = self.metadata
        schema_map = {p.name: p for p in meta.parameters}

        for param_name, param_value in params.items():
            if param_name not in schema_map:
                raise ValueError(f"Unknown parameter: {param_name}")

            schema = schema_map[param_name]

            # Type checking
            expected_type = {
                'int': int,
                'float': (int, float),
                'bool': bool,
                'string': str,
            }.get(schema.type)

            if expected_type and not isinstance(param_value, expected_type):
                raise ValueError(
                    f"Parameter {param_name} must be {schema.type}, "
                    f"got {type(param_value).__name__}"
                )

            # Range checking
            if isinstance(param_value, (int, float)):
                if schema.min_value is not None and param_value < schema.min_value:
                    raise ValueError(
                        f"Parameter {param_name} must be >= {schema.min_value}, "
                        f"got {param_value}"
                    )
                if schema.max_value is not None and param_value > schema.max_value:
                    raise ValueError(
                        f"Parameter {param_name} must be <= {schema.max_value}, "
                        f"got {param_value}"
                    )

    def get_default_parameters(self) -> Dict[str, Any]:
        """Get all default parameters as a dict."""
        meta = self.metadata
        return {p.name: p.default for p in meta.parameters}
