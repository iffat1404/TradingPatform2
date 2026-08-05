from typing import Dict, Optional
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from app.models.orm import PriceHistoryMinute
from app.core.config import settings
from app.services.market_clock import get_market_clock


def get_current_tick_for_ticker(ticker: str, db: Session) -> Optional[Dict]:
    """
    Get the current tick for a ticker based on MarketClock simulated time.
    Queries the database directly without caching.
    Maps simulated time to the corresponding historical tick.
    """
    # Get current simulated time from MarketClock
    market_clock = get_market_clock()
    now = market_clock.now()
    
    # Get the time portion (hour, minute, second) - preserve timezone
    time_of_day = now.replace(hour=now.hour, minute=now.minute, second=now.second, microsecond=0, tzinfo=timezone.utc)
    
    # Query the database for the closest tick to the current simulated time
    # Get ticks within a 5-minute window around the target time
    target_time_minus_5min = time_of_day - timedelta(minutes=5)
    target_time_plus_5min = time_of_day + timedelta(minutes=5)
    
    # Query for ticks in the time window
    prices = db.query(PriceHistoryMinute).filter(
        PriceHistoryMinute.ticker == ticker,
        PriceHistoryMinute.timestamp >= target_time_minus_5min,
        PriceHistoryMinute.timestamp <= target_time_plus_5min
    ).order_by(PriceHistoryMinute.timestamp.asc()).all()
    
    if not prices:
        return None
    
    # Find the closest tick to the target time
    closest_price = None
    min_diff = float('inf')
    
    for price in prices:
        # Ensure both timestamps have timezone info
        price_time = price.timestamp
        if price_time.tzinfo is None:
            price_time = price_time.replace(tzinfo=timezone.utc)
        
        diff = abs((price_time - time_of_day).total_seconds())
        if diff < min_diff:
            min_diff = diff
            closest_price = price
    
    if closest_price:
        price_time = closest_price.timestamp
        if price_time.tzinfo is None:
            price_time = price_time.replace(tzinfo=timezone.utc)
            
        return {
            "timestamp": price_time,
            "open": closest_price.open,
            "high": closest_price.high,
            "low": closest_price.low,
            "close": closest_price.close,
            "volume": closest_price.volume
        }
    
    return None


def get_all_current_ticks(db: Session) -> Dict[str, Dict]:
    """
    Get current ticks for all supported tickers.
    Queries the database directly without caching.
    """
    tickers = ["AAPL", "GOOG", "IBM", "MSFT", "TSLA", "UL", "WMT"]
    result = {}
    
    for ticker in tickers:
        tick = get_current_tick_for_ticker(ticker, db)
        if tick:
            result[ticker] = tick
    
    return result


def get_tick_for_ticker_at_time(ticker: str, target_time: datetime, db: Session) -> Optional[Dict]:
    """
    Get a specific tick for a ticker at a given timestamp.
    Used for historical queries and backtesting.
    Queries the database directly without caching.
    """
    # Ensure target_time has timezone info
    if target_time.tzinfo is None:
        target_time = target_time.replace(tzinfo=timezone.utc)
    
    # Query for the exact tick at the target time
    price = db.query(PriceHistoryMinute).filter(
        PriceHistoryMinute.ticker == ticker,
        PriceHistoryMinute.timestamp == target_time
    ).first()
    
    if price:
        price_time = price.timestamp
        if price_time.tzinfo is None:
            price_time = price_time.replace(tzinfo=timezone.utc)
            
        return {
            "timestamp": price_time,
            "open": price.open,
            "high": price.high,
            "low": price.low,
            "close": price.close,
            "volume": price.volume
        }
    
    # If no exact match, find closest within 5 minutes
    target_time_minus_5min = target_time - timedelta(minutes=5)
    target_time_plus_5min = target_time + timedelta(minutes=5)
    
    prices = db.query(PriceHistoryMinute).filter(
        PriceHistoryMinute.ticker == ticker,
        PriceHistoryMinute.timestamp >= target_time_minus_5min,
        PriceHistoryMinute.timestamp <= target_time_plus_5min
    ).order_by(PriceHistoryMinute.timestamp.asc()).all()
    
    if not prices:
        return None
    
    # Find the closest tick
    closest_price = None
    min_diff = float('inf')
    
    for price in prices:
        price_time = price.timestamp
        if price_time.tzinfo is None:
            price_time = price_time.replace(tzinfo=timezone.utc)
            
        diff = abs((price_time - target_time).total_seconds())
        if diff < min_diff:
            min_diff = diff
            closest_price = price
    
    if closest_price:
        price_time = closest_price.timestamp
        if price_time.tzinfo is None:
            price_time = price_time.replace(tzinfo=timezone.utc)
            
        return {
            "timestamp": price_time,
            "open": closest_price.open,
            "high": closest_price.high,
            "low": closest_price.low,
            "close": closest_price.close,
            "volume": closest_price.volume
        }
    
    return None


def reset_feed_simulator() -> None:
    """
    Reset the feed simulator to start from the beginning of the dataset.
    Admin-only function per spec Section 9.6.
    Also resets the MarketClock.
    """
    # Reset MarketClock as well
    market_clock = get_market_clock()
    market_clock.reset()
    print("MarketClock reset to start of dataset")