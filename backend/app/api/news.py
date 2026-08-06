"""
Market news API.

Serves the individual headlines behind the simulated market, so a trader can read the news
that is driving prices, cite it in their journal, and later be shown whether it actually
moved the stock.

Time integrity: headlines are never returned from beyond the MarketClock's current
simulated moment. Showing a trader a story that has not been published yet in their
simulation would let them "predict" a move they should not be able to see — the same rule
the intraday chart follows.
"""
from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user
from app.models.orm import NewsArticle
from app.services.market_clock import get_market_clock

router = APIRouter()

# Bearish -> Bullish, for turning a label into a direction without re-deriving from score.
LABEL_DIRECTION = {
    "Bearish": -1,
    "Somewhat-Bearish": -1,
    "Neutral": 0,
    "Somewhat-Bullish": 1,
    "Bullish": 1,
}


def serialize_article(a: NewsArticle) -> dict:
    return {
        "id": a.id,
        "ticker": a.ticker,
        "title": a.title,
        "date": a.date.strftime("%Y-%m-%d") if a.date else None,
        "published_at": a.published_at,
        "relevance_score": round(a.relevance_score, 3),
        "sentiment_score": round(a.sentiment_score, 3),
        "sentiment_label": a.sentiment_label,
        "direction": LABEL_DIRECTION.get(a.sentiment_label, 0),
        "topics": [t for t in (a.topics or "").split(",") if t],
    }


@router.get("/")
def list_news(
    ticker: Optional[str] = Query(None, description="Filter to one ticker"),
    days: int = Query(1, ge=1, le=14, description="How many trading days back to include"),
    limit: int = Query(30, ge=1, le=100),
    min_relevance: float = Query(0.0, ge=0.0, le=1.0, description="Drop passing mentions"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Headlines up to the current simulated moment, most relevant first.

    Returns `simulated_date` alongside the articles so the UI can say which session day the
    trader is looking at — and explain an empty feed (the news dataset starts 2026-07-01,
    while the MarketClock's default start is 2026-06-30).
    """
    now = get_market_clock().now()
    # Compare naive-to-naive: these DateTime columns are stored without tzinfo.
    now_naive = now.replace(tzinfo=None)
    window_start = (now_naive - timedelta(days=days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)

    query = db.query(NewsArticle).filter(
        NewsArticle.date >= window_start,
        # Never reveal a story published later than "now" in the simulation.
        NewsArticle.published_at <= now_naive,
    )
    if ticker:
        query = query.filter(NewsArticle.ticker == ticker.upper())
    if min_relevance:
        query = query.filter(NewsArticle.relevance_score >= min_relevance)

    articles = (
        query.order_by(NewsArticle.published_at.desc(), NewsArticle.relevance_score.desc())
        .limit(limit)
        .all()
    )

    return {
        "simulated_date": now_naive.strftime("%Y-%m-%d"),
        "simulated_time": now_naive.strftime("%H:%M:%S"),
        "window_days": days,
        "count": len(articles),
        "articles": [serialize_article(a) for a in articles],
    }


@router.get("/{article_id}")
def get_article(
    article_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """One headline, for a journal entry that cites it."""
    article = db.query(NewsArticle).filter(NewsArticle.id == article_id).first()
    if not article:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")
    return serialize_article(article)
