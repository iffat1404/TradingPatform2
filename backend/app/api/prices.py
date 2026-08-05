from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.models.orm import PriceHistoryDaily, PriceHistoryMinute
from app.services.feed_simulator import get_current_tick_for_ticker, get_all_current_ticks
import pandas as pd
from datetime import datetime, timezone

router = APIRouter()


@router.get("/{ticker}/latest")
def get_latest_price(
    ticker: str,
    db: Session = Depends(get_db)
):
    """Get the current minute-level price snapshot for a ticker based on system time."""
    current_tick = get_current_tick_for_ticker(ticker, db)
    
    if not current_tick:
        raise HTTPException(status_code=404, detail=f"No intraday data found for ticker: {ticker}")

    return {
        "ticker": ticker,
        "timestamp": current_tick["timestamp"].strftime("%Y-%m-%d %H:%M:%S"),
        "open": current_tick["open"],
        "high": current_tick["high"],
        "low": current_tick["low"],
        "close": current_tick["close"],
        "volume": current_tick["volume"],
        "system_time": datetime.now(timezone.utc).isoformat()
    }


@router.get("/market/current")
def get_all_current_prices(
    db: Session = Depends(get_db)
):
    """Get current prices for all tickers based on system time."""
    all_ticks = get_all_current_ticks(db)
    
    result = {}
    for ticker, tick in all_ticks.items():
        result[ticker] = {
            "timestamp": tick["timestamp"].strftime("%Y-%m-%d %H:%M:%S"),
            "open": tick["open"],
            "high": tick["high"],
            "low": tick["low"],
            "close": tick["close"],
            "volume": tick["volume"]
        }
    
    result["system_time"] = datetime.now(timezone.utc).isoformat()
    return result


@router.get("/{ticker}/daily")
def get_daily_prices(
    ticker: str,
    db: Session = Depends(get_db)
):
    """
    Get daily OHLCV data for a ticker from historical CSVs.
    Returns exactly 130 bars per ticker (matching source).
    """
    # Query daily price history
    prices = db.query(PriceHistoryDaily).filter(
        PriceHistoryDaily.ticker == ticker
    ).order_by(PriceHistoryDaily.date.asc()).all()
    
    if not prices:
        raise HTTPException(status_code=404, detail=f"No daily data found for ticker: {ticker}")
    
    return [
        {
            "date": price.date.strftime("%Y-%m-%d"),
            "open": price.open,
            "high": price.high,
            "low": price.low,
            "close": price.close,
            "volume": price.volume
        }
        for price in prices
    ]


@router.get("/{ticker}/intraday")
def get_intraday_prices(
    ticker: str,
    interval: str = Query("5m", description="Interval: 1m, 5m, 15m, or 60m"),
    db: Session = Depends(get_db)
):
    """
    Get intraday OHLCV data with resampling using pandas.
    Supports intervals: 1m, 5m, 15m, 60m.
    """
    # Validate interval
    valid_intervals = ["1m", "5m", "15m", "60m"]
    if interval not in valid_intervals:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid interval. Must be one of: {', '.join(valid_intervals)}"
        )
    
    # Query minute-level price history
    prices = db.query(PriceHistoryMinute).filter(
        PriceHistoryMinute.ticker == ticker
    ).order_by(PriceHistoryMinute.timestamp.asc()).all()
    
    if not prices:
        raise HTTPException(status_code=404, detail=f"No intraday data found for ticker: {ticker}")
    
    # Convert to DataFrame for resampling
    df = pd.DataFrame([
        {
            "timestamp": price.timestamp,
            "open": price.open,
            "high": price.high,
            "low": price.low,
            "close": price.close,
            "volume": price.volume
        }
        for price in prices
    ])
    
    # Set timestamp as index
    df.set_index("timestamp", inplace=True)
    
    # Map interval string to pandas offset
    interval_map = {
        "1m": "1min",
        "5m": "5min",
        "15m": "15min",
        "60m": "60min"
    }
    pandas_interval = interval_map[interval]
    
    # Resample using pandas
    resampled = df.resample(pandas_interval).agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum"
    }).dropna()
    
    # Convert back to list of dicts
    return [
        {
            "timestamp": idx.strftime("%Y-%m-%d %H:%M:%S"),
            "open": row["open"],
            "high": row["high"],
            "low": row["low"],
            "close": row["close"],
            "volume": row["volume"]
        }
        for idx, row in resampled.iterrows()
    ]