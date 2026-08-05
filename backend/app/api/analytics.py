from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.core.security import get_current_user
from app.services.analytics_engine import (
    get_technical_indicators,
    get_technical_alerts,
    check_sentiment_divergence
)

router = APIRouter()


@router.get("/{ticker}/indicators")
def get_indicators(
    ticker: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get technical indicators for a ticker.
    Includes SMA, EMA, RSI, MACD, and Bollinger Bands.
    """
    indicators = get_technical_indicators(db, ticker)
    
    if not indicators:
        raise HTTPException(status_code=404, detail=f"No data found for ticker: {ticker}")
    
    return indicators


@router.get("/{ticker}/alerts")
def get_alerts(
    ticker: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get technical alerts for a ticker.
    Includes RSI overbought/oversold, MACD crossovers, and Bollinger Band breakouts.
    """
    alerts = get_technical_alerts(db, ticker)
    
    return {
        "ticker": ticker,
        "alerts": alerts,
        "alert_count": len(alerts)
    }


@router.get("/{ticker}/sentiment-divergence")
def get_sentiment_divergence(
    ticker: str,
    date: str = Query(..., description="Date in YYYY-MM-DD format"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Check for sentiment divergence on a specific date.
    Returns divergence info if detected, empty result otherwise.
    """
    divergence = check_sentiment_divergence(db, ticker, date)
    
    if divergence:
        return {
            "ticker": ticker,
            "divergence": divergence
        }
    else:
        return {
            "ticker": ticker,
            "divergence": None,
            "message": "No sentiment divergence detected"
        }