"""
Backtest API Endpoints - REST API for strategy discovery and backtest execution.
"""

from typing import List, Dict, Any
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user
from app.strategies import get_registry
from app.strategies.base import StrategyMetadata, ParameterSchema
from app.services.backtest_executor import BacktestExecutor, BacktestResult
from app.services.feed_simulator import get_price_history_ohlcv

router = APIRouter()


# ============================================================================
# Pydantic Models for API
# ============================================================================

class ParameterSchemaResponse(BaseModel):
    """API response for parameter schema."""
    name: str
    type: str
    default: Any
    min_value: float | None = None
    max_value: float | None = None
    description: str = ""
    step: float | None = None


class StrategyMetadataResponse(BaseModel):
    """API response for strategy metadata."""
    id: str
    name: str
    description: str
    category: str
    version: str
    parameters: List[ParameterSchemaResponse]


class BacktestRequestPayload(BaseModel):
    """Payload for backtest execution request."""
    strategy_id: str = Field(..., description="Strategy ID (e.g., 'sma_crossover')")
    symbol: str = Field(..., description="Symbol to backtest (e.g., 'BTC-USD')")
    timeframe: str = Field(default="1d", description="Timeframe (e.g., '1d', '1h')")
    start_date: str = Field(..., description="Start date (YYYY-MM-DD)")
    end_date: str = Field(..., description="End date (YYYY-MM-DD)")
    initial_capital: float = Field(default=10000.0, ge=100.0, description="Initial capital")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Strategy parameters")


class TradeRecord(BaseModel):
    """Single trade record."""
    entry_time: str
    exit_time: str
    entry_price: float
    exit_price: float
    size: float
    pnl: float
    pnl_percent: float
    duration_bars: int


class BacktestResponsePayload(BaseModel):
    """Backtest execution result."""
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
    trades: List[TradeRecord]
    parameters: Dict[str, Any]


# ============================================================================
# API Endpoints
# ============================================================================

@router.get(
    "/strategies",
    response_model=List[StrategyMetadataResponse],
    summary="List all available preset strategies",
    tags=["strategies"]
)
def list_strategies():
    """
    Returns all registered preset strategies with their metadata and parameter schemas.

    Dynamically discovers strategies without hardcoding endpoint logic.
    """
    registry = get_registry()
    metadata_list = registry.list_strategies()

    return [
        StrategyMetadataResponse(
            id=m.id,
            name=m.name,
            description=m.description,
            category=m.category,
            version=m.version,
            parameters=[
                ParameterSchemaResponse(
                    name=p.name,
                    type=p.type,
                    default=p.default,
                    min_value=p.min_value,
                    max_value=p.max_value,
                    description=p.description,
                    step=p.step,
                )
                for p in m.parameters
            ],
        )
        for m in metadata_list
    ]


@router.get(
    "/strategies/{strategy_id}",
    response_model=StrategyMetadataResponse,
    summary="Get strategy metadata by ID",
    tags=["strategies"]
)
def get_strategy_metadata(strategy_id: str):
    """Returns metadata for a single strategy by ID."""
    registry = get_registry()
    meta = registry.get_metadata(strategy_id)

    if not meta:
        raise HTTPException(
            status_code=404,
            detail=f"Strategy '{strategy_id}' not found"
        )

    return StrategyMetadataResponse(
        id=meta.id,
        name=meta.name,
        description=meta.description,
        category=meta.category,
        version=meta.version,
        parameters=[
            ParameterSchemaResponse(
                name=p.name,
                type=p.type,
                default=p.default,
                min_value=p.min_value,
                max_value=p.max_value,
                description=p.description,
                step=p.step,
            )
            for p in meta.parameters
        ],
    )


@router.post(
    "/preset",
    response_model=BacktestResponsePayload,
    summary="Execute a backtest with a preset strategy",
    tags=["backtest"]
)
def backtest_preset(
    payload: BacktestRequestPayload,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Execute a backtest with preset parameters.

    Process:
    1. Fetch historical OHLCV data for the symbol
    2. Retrieve strategy from registry
    3. Generate signals and run VectorBT portfolio simulation
    4. Calculate performance metrics
    5. Return equity curve and trade log for charting

    Args:
        payload: Backtest configuration

    Returns:
        BacktestResult with metrics and trade data
    """
    try:
        # Fetch price data
        df = get_price_history_ohlcv(
            db,
            symbol=payload.symbol,
            timeframe=payload.timeframe,
            start_date=payload.start_date,
            end_date=payload.end_date,
        )

        if df is None or len(df) == 0:
            raise HTTPException(
                status_code=400,
                detail=f"No price data found for {payload.symbol}"
            )

        # Get strategy from registry
        registry = get_registry()
        strategy = registry.get_strategy(payload.strategy_id)

        # Execute backtest
        result = BacktestExecutor.execute(
            strategy=strategy,
            df=df,
            symbol=payload.symbol,
            timeframe=payload.timeframe,
            start_date=payload.start_date,
            end_date=payload.end_date,
            initial_capital=payload.initial_capital,
            **payload.parameters
        )

        # Convert to response
        return BacktestResponsePayload(
            strategy_id=result.strategy_id,
            symbol=result.symbol,
            timeframe=result.timeframe,
            start_date=result.start_date,
            end_date=result.end_date,
            initial_capital=result.initial_capital,
            final_value=result.final_value,
            total_return=result.total_return,
            return_percent=result.return_percent,
            sharpe_ratio=result.sharpe_ratio,
            max_drawdown=result.max_drawdown,
            win_rate=result.win_rate,
            total_trades=result.total_trades,
            winning_trades=result.winning_trades,
            losing_trades=result.losing_trades,
            avg_trade_return=result.avg_trade_return,
            best_trade=result.best_trade,
            worst_trade=result.worst_trade,
            profit_factor=result.profit_factor,
            equity_curve=result.equity_curve,
            timestamps=result.timestamps,
            trades=[
                TradeRecord(
                    entry_time=t["entry_time"],
                    exit_time=t["exit_time"],
                    entry_price=t["entry_price"],
                    exit_price=t["exit_price"],
                    size=t["size"],
                    pnl=t["pnl"],
                    pnl_percent=t["pnl_percent"],
                    duration_bars=t["duration_bars"],
                )
                for t in result.trades
            ],
            parameters=result.parameters,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        error_msg = str(e) if str(e) else type(e).__name__
        traceback.print_exc()
        print(f"Backtest error: {error_msg}")
        raise HTTPException(status_code=500, detail=f"Backtest execution failed: {error_msg}")
