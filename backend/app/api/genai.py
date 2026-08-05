from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter

from app.services.genai_client import (
    explain_news_sentiment,
    explain_order_rejection,
    extract_id_document_fields,
    generate_portfolio_summary,
    parse_order_command,
)

router = APIRouter()


@router.post("/parse-order")
def parse_order(payload: dict[str, Any] | None = None):
    """Parse a natural language order request into a draft order."""
    text = (payload or {}).get("text", "")
    return parse_order_command(text)


@router.get("/explain/{ticker}")
def explain_ticker(ticker: str, date: str | None = None):
    """Explain news sentiment for the provided ticker."""
    selected_date = date or datetime.now(timezone.utc).date().isoformat()
    return explain_news_sentiment(ticker, selected_date)


@router.post("/explain-rejection")
def explain_rejection(payload: dict[str, Any] | None = None):
    """Explain why an order was rejected in plain English."""
    order_id = (payload or {}).get("order_id", "unknown")
    reason_code = (payload or {}).get("reason_code", "unknown")
    return explain_order_rejection(order_id, reason_code)


@router.post("/portfolio-summary")
def get_portfolio_summary(payload: dict[str, Any] | None = None):
    """Get a concise AI portfolio summary."""
    portfolio_data = payload or {}
    return generate_portfolio_summary(portfolio_data)


@router.post("/extract-id")
def extract_id_fields(payload: dict[str, Any] | None = None):
    """Extract fields from an uploaded ID document."""
    file_path = (payload or {}).get("file_path", "")
    content_type = (payload or {}).get("content_type", "application/octet-stream")
    return extract_id_document_fields(file_path, content_type)