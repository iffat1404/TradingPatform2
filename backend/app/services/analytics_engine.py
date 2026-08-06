from typing import Dict, List, Optional
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from app.models.orm import PriceHistoryDaily, NewsSentimentDaily
from app.core.config import settings


def _last_valid(values) -> Optional[float]:
    """Most recent non-None value from an indicator series."""
    if not values:
        return None
    return next((v for v in reversed(values) if v is not None), None)


def _latest_scalars(indicators: Dict) -> Dict[str, Optional[float]]:
    """Collapse the parallel indicator arrays down to their latest scalar values."""
    if not indicators:
        return {k: None for k in (
            "close", "sma_20", "sma_50", "ema_12", "ema_26", "rsi_14",
            "macd", "macd_signal", "macd_hist", "bb_upper", "bb_middle", "bb_lower",
        )}

    macd = indicators.get("macd") or {}
    bands = indicators.get("bollinger_bands") or {}
    closes = indicators.get("close") or []

    return {
        "close": closes[-1] if closes else None,
        "sma_20": _last_valid(indicators.get("sma_20")),
        "sma_50": _last_valid(indicators.get("sma_50")),
        "ema_12": _last_valid(indicators.get("ema_12")),
        "ema_26": _last_valid(indicators.get("ema_26")),
        "rsi_14": _last_valid(indicators.get("rsi_14")),
        "macd": _last_valid(macd.get("macd")),
        "macd_signal": _last_valid(macd.get("signal")),
        "macd_hist": _last_valid(macd.get("histogram")),
        "bb_upper": _last_valid(bands.get("upper")),
        "bb_middle": _last_valid(bands.get("middle")),
        "bb_lower": _last_valid(bands.get("lower")),
    }


def get_latest_indicators(db: Session, ticker: str) -> Dict[str, Optional[float]]:
    """
    Latest scalar value of every indicator for a ticker.

    get_technical_indicators returns full parallel time-series arrays; scoring and
    coaching only ever need the most recent point of each.
    """
    return _latest_scalars(get_technical_indicators(db, ticker))


def get_recent_daily_bars(db: Session, ticker: str, limit: int = 30) -> List[PriceHistoryDaily]:
    """Most recent `limit` daily OHLC bars for a ticker, oldest-first."""
    rows = (
        db.query(PriceHistoryDaily)
        .filter(PriceHistoryDaily.ticker == ticker.upper())
        .order_by(PriceHistoryDaily.date.desc())
        .limit(limit)
        .all()
    )
    return list(reversed(rows))


def calculate_atr(db: Session, ticker: str, period: int = 14) -> Optional[float]:
    """
    Average True Range over the last `period` daily bars.

    True range is the widest of: today's high-low, and each of high/low measured against
    the previous close — so it captures overnight gaps that a plain high-low range misses.
    """
    bars = get_recent_daily_bars(db, ticker, limit=period + 1)
    if len(bars) < 2:
        return None

    true_ranges = []
    for previous, current in zip(bars, bars[1:]):
        true_ranges.append(max(
            current.high - current.low,
            abs(current.high - previous.close),
            abs(current.low - previous.close),
        ))

    if not true_ranges:
        return None
    return sum(true_ranges) / len(true_ranges)


def calculate_atr_percent(db: Session, ticker: str, period: int = 14) -> Optional[float]:
    """ATR as a percentage of the latest close — comparable across differently priced names."""
    atr = calculate_atr(db, ticker, period)
    if atr is None:
        return None
    bars = get_recent_daily_bars(db, ticker, limit=1)
    if not bars or not bars[-1].close:
        return None
    return (atr / bars[-1].close) * 100.0


def get_latest_sentiment(db: Session, ticker: str) -> Optional[Dict]:
    """
    Newest news-sentiment row for a ticker.

    Centralises a query that was previously inlined in several places.
    """
    record = (
        db.query(NewsSentimentDaily)
        .filter(NewsSentimentDaily.ticker == ticker.upper())
        .order_by(NewsSentimentDaily.date.desc())
        .first()
    )
    if not record:
        return None
    return {
        "ticker": record.ticker,
        "date": record.date.strftime("%Y-%m-%d") if record.date else None,
        "avg_sentiment": record.avg_sentiment,
        "headline_count": record.headline_count,
    }


def calculate_sma(prices: List[float], period: int) -> List[Optional[float]]:
    """
    Calculate Simple Moving Average (SMA).
    Returns None for periods where SMA is not yet valid.
    """
    df = pd.Series(prices)
    sma = df.rolling(window=period).mean()
    # Convert NaN to None
    return [None if pd.isna(v) else v for v in sma.tolist()]


def calculate_ema(prices: List[float], period: int) -> List[Optional[float]]:
    """
    Calculate Exponential Moving Average (EMA) using standard exponential smoothing.
    """
    df = pd.Series(prices)
    ema = df.ewm(span=period, adjust=False).mean()
    return [None if pd.isna(v) else v for v in ema.tolist()]


def calculate_rsi(prices: List[float], period: int = 14) -> List[Optional[float]]:
    """
    Calculate RSI using Wilder's method.
    """
    df = pd.Series(prices)
    
    # Calculate price changes
    delta = df.diff()
    
    # Separate gains and losses
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    
    # Calculate average gain and loss using Wilder's smoothing
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    
    # Calculate RSI
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    return [None if pd.isna(v) else v for v in rsi.tolist()]


def calculate_macd(prices: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, List[Optional[float]]]:
    """
    Calculate MACD (Moving Average Convergence Divergence).
    Returns dict with 'macd', 'signal', and 'histogram'.
    """
    df = pd.Series(prices)
    
    # Calculate EMAs
    ema_fast = df.ewm(span=fast, adjust=False).mean()
    ema_slow = df.ewm(span=slow, adjust=False).mean()
    
    # Calculate MACD line
    macd = ema_fast - ema_slow
    
    # Calculate Signal line
    signal = macd.ewm(span=signal, adjust=False).mean()
    
    # Calculate Histogram
    histogram = macd - signal
    
    return {
        "macd": [None if pd.isna(v) else v for v in macd.tolist()],
        "signal": [None if pd.isna(v) else v for v in signal.tolist()],
        "histogram": [None if pd.isna(v) else v for v in histogram.tolist()]
    }


def calculate_bollinger_bands(prices: List[float], period: int = 20, std_dev: float = 2.0) -> Dict[str, List[Optional[float]]]:
    """
    Calculate Bollinger Bands.
    Returns dict with 'upper', 'middle' (SMA), and 'lower'.
    """
    df = pd.Series(prices)
    
    # Calculate middle band (SMA)
    middle = df.rolling(window=period).mean()
    
    # Calculate standard deviation
    std = df.rolling(window=period).std()
    
    # Calculate upper and lower bands
    upper = middle + (std * std_dev)
    lower = middle - (std * std_dev)
    
    return {
        "upper": [None if pd.isna(v) else v for v in upper.tolist()],
        "middle": [None if pd.isna(v) else v for v in middle.tolist()],
        "lower": [None if pd.isna(v) else v for v in lower.tolist()]
    }


def get_technical_indicators(
    db: Session,
    ticker: str
) -> Dict[str, any]:
    """
    Calculate all technical indicators for a ticker from daily price history.
    """
    # Get daily price history
    prices = db.query(PriceHistoryDaily).filter(
        PriceHistoryDaily.ticker == ticker
    ).order_by(PriceHistoryDaily.date.asc()).all()
    
    if not prices:
        return {}
    
    # Extract close prices
    close_prices = [p.close for p in prices]
    dates = [p.date.strftime("%Y-%m-%d") for p in prices]
    
    # Calculate indicators
    sma_20 = calculate_sma(close_prices, 20)
    sma_50 = calculate_sma(close_prices, 50)
    ema_12 = calculate_ema(close_prices, 12)
    ema_26 = calculate_ema(close_prices, 26)
    rsi_14 = calculate_rsi(close_prices, 14)
    macd = calculate_macd(close_prices, 12, 26, 9)
    bollinger = calculate_bollinger_bands(close_prices, 20, 2)
    
    return {
        "dates": dates,
        "close": close_prices,
        "sma_20": sma_20,
        "sma_50": sma_50,
        "ema_12": ema_12,
        "ema_26": ema_26,
        "rsi_14": rsi_14,
        "macd": macd,
        "bollinger_bands": bollinger
    }


def get_technical_alerts(
    db: Session,
    ticker: str
) -> List[Dict[str, any]]:
    """
    Generate technical alerts for a ticker.
    Returns list of active alerts.
    """
    indicators = get_technical_indicators(db, ticker)
    
    if not indicators:
        return []
    
    alerts = []
    macd_data = indicators["macd"]

    latest = _latest_scalars(indicators)
    latest_rsi = latest["rsi_14"]
    latest_macd = latest["macd"]
    latest_signal = latest["macd_signal"]
    latest_close = latest["close"]
    latest_upper = latest["bb_upper"]
    latest_lower = latest["bb_lower"]

    # RSI alerts
    if latest_rsi:
        if latest_rsi > settings.RSI_OVERBOUGHT:
            alerts.append({
                "type": "RSI_OVERBOUGHT",
                "message": f"RSI ({latest_rsi:.2f}) is overbought (> {settings.RSI_OVERBOUGHT})",
                "severity": "high"
            })
        elif latest_rsi < settings.RSI_OVERSOLD:
            alerts.append({
                "type": "RSI_OVERSOLD",
                "message": f"RSI ({latest_rsi:.2f}) is oversold (< {settings.RSI_OVERSOLD})",
                "severity": "medium"
            })
    
    # MACD crossover (check if MACD crossed signal recently)
    if len(macd_data["macd"]) > 1 and len(macd_data["signal"]) > 1:
        # Get last two valid values
        macd_vals = [v for v in macd_data["macd"][-2:] if v is not None]
        signal_vals = [v for v in macd_data["signal"][-2:] if v is not None]
        
        if len(macd_vals) == 2 and len(signal_vals) == 2:
            # Bullish crossover: MACD crosses above signal
            if macd_vals[0] <= signal_vals[0] and macd_vals[1] > signal_vals[1]:
                alerts.append({
                    "type": "MACD_BULLISH_CROSSOVER",
                    "message": "MACD crossed above signal line (bullish)",
                    "severity": "medium"
                })
            # Bearish crossover: MACD crosses below signal
            elif macd_vals[0] >= signal_vals[0] and macd_vals[1] < signal_vals[1]:
                alerts.append({
                    "type": "MACD_BEARISH_CROSSOVER",
                    "message": "MACD crossed below signal line (bearish)",
                    "severity": "medium"
                })
    
    # Bollinger Bands crossing
    if latest_close and latest_upper and latest_lower:
        if latest_close > latest_upper:
            alerts.append({
                "type": "BOLLINGER_UPPER_BREAKOUT",
                "message": f"Price ({latest_close:.2f}) crossed above upper Bollinger Band ({latest_upper:.2f})",
                "severity": "high"
            })
        elif latest_close < latest_lower:
            alerts.append({
                "type": "BOLLINGER_LOWER_BREAKOUT",
                "message": f"Price ({latest_close:.2f}) crossed below lower Bollinger Band ({latest_lower:.2f})",
                "severity": "high"
            })
    
    return alerts


def check_sentiment_divergence(
    db: Session,
    ticker: str,
    date: str
) -> Optional[Dict[str, any]]:
    """
    Check for sentiment divergence on a specific date.
    Returns divergence info if detected, None otherwise.
    """
    # Parse date with UTC timezone per principle 12
    try:
        date_dt = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    
    # Get sentiment data for the date
    sentiment = db.query(NewsSentimentDaily).filter(
        NewsSentimentDaily.ticker == ticker,
        NewsSentimentDaily.date == date_dt
    ).first()
    
    if not sentiment:
        return None
    
    # Get price data for the date and previous day
    target_date = datetime.strptime(date, "%Y-%m-%d").date()
    prev_date = target_date - timedelta(days=1)
    
    prices = db.query(PriceHistoryDaily).filter(
        PriceHistoryDaily.ticker == ticker,
        PriceHistoryDaily.date.in_([prev_date, target_date])
    ).order_by(PriceHistoryDaily.date.asc()).all()
    
    if len(prices) < 2:
        return None
    
    # Calculate price return
    price_return = (prices[1].close - prices[0].close) / prices[0].close
    
    # Check for divergence
    avg_sentiment = sentiment.avg_sentiment
    
    if abs(avg_sentiment) > settings.SENTIMENT_DIVERGENCE_THRESHOLD:
        # Check if sentiment and price return signs disagree
        if (avg_sentiment > 0 and price_return < 0) or (avg_sentiment < 0 and price_return > 0):
            return {
                "date": date,
                "avg_sentiment": avg_sentiment,
                "price_return": price_return,
                "divergence_type": "bullish" if avg_sentiment < 0 else "bearish",
                "message": f"Sentiment divergence detected: sentiment={avg_sentiment:.2f}, price_return={price_return:.2%}"
            }
    
    return None