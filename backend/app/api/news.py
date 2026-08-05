from fastapi import APIRouter, Query, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from app.core.db import get_db
from app.models.orm import NewsItem, NewsSentimentDaily
from sqlalchemy import desc, func

router = APIRouter()


@router.get("/{ticker}/recent")
def get_recent_news(
    ticker: str,
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Get recent news articles for a ticker, ordered by published_at DESC."""
    ticker = ticker.upper()
    articles = (
        db.query(NewsItem)
        .filter(NewsItem.ticker == ticker)
        .order_by(desc(NewsItem.published_at))
        .limit(limit)
        .all()
    )
    return [
        {
            "id": a.id,
            "title": a.title,
            "ticker": a.ticker,
            "sentiment_score": a.sentiment_score,
            "sentiment_label": a.sentiment_label,
            "relevance_score": a.relevance_score,
            "published_at": a.published_at.isoformat() if a.published_at else None,
            "source": a.source,
            "primary_topic": a.primary_topic,
        }
        for a in articles
    ]


@router.get("/{ticker}/sentiment")
def get_sentiment_summary(
    ticker: str,
    days: int = Query(7, ge=1, le=365),
    db: Session = Depends(get_db)
):
    """Get aggregated sentiment summary for a ticker over the last N days."""
    ticker = ticker.upper()

    # Get the date N days ago
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

    # Query recent news items
    articles = (
        db.query(NewsItem)
        .filter(
            NewsItem.ticker == ticker,
            NewsItem.published_at >= cutoff_date
        )
        .all()
    )

    if not articles:
        return {
            "ticker": ticker,
            "days": days,
            "total_articles": 0,
            "avg_sentiment": 0.0,
            "sentiment_distribution": {
                "bullish": 0,
                "neutral": 0,
                "bearish": 0
            }
        }

    # Calculate statistics
    total = len(articles)
    avg_sentiment = sum(a.sentiment_score for a in articles) / total if total > 0 else 0

    sentiment_dist = {
        "bullish": sum(1 for a in articles if a.sentiment_label == "Bullish"),
        "neutral": sum(1 for a in articles if a.sentiment_label == "Neutral"),
        "bearish": sum(1 for a in articles if a.sentiment_label == "Bearish"),
    }

    return {
        "ticker": ticker,
        "days": days,
        "total_articles": total,
        "avg_sentiment": round(avg_sentiment, 3),
        "sentiment_distribution": sentiment_dist
    }
