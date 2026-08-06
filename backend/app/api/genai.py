import os
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user

from app.services.market_clock import get_market_clock

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
    # The MarketClock is the platform's authoritative time source; the operator's real
    # calendar date is meaningless inside a 2026 simulation.
    selected_date = date or get_market_clock().now().date().isoformat()
    return explain_news_sentiment(ticker, selected_date)


@router.post("/explain-rejection")
def explain_rejection(
    payload: dict[str, Any] | None = None,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Explain why an order was rejected in plain English.

    The reason is read from the order's own event trail rather than taken from the request:
    callers only know the order id, and a caller-supplied reason used to reach the model as
    the literal string "unknown", which it then rationalised into a non-existent
    "technical glitch". Scoped to the caller's account so an order id cannot be used to read
    another trader's rejections.
    """
    from app.models.orm import Order, OrderEvent, OrderStatus

    order_id = (payload or {}).get("order_id")
    if not order_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="order_id is required")

    order = (
        db.query(Order)
        .filter(Order.id == order_id, Order.account_id == current_user["account_id"])
        .first()
    )
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if order.status != OrderStatus.REJECTED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Order is {order.status.value}, not REJECTED - there is nothing to explain.",
        )

    # transition_order_status records the reason as "REASON_CODE|message".
    event = (
        db.query(OrderEvent)
        .filter(OrderEvent.order_id == order.id, OrderEvent.to_state == OrderStatus.REJECTED)
        .order_by(OrderEvent.timestamp.desc())
        .first()
    )
    reason_code, reason_detail = "VALIDATION_FAILED", None
    if event and event.reason:
        if "|" in event.reason:
            code, message = event.reason.split("|", 1)
            reason_code, reason_detail = code.strip(), message.strip()
        else:
            reason_code = event.reason.strip()

    return explain_order_rejection(order.id, reason_code, reason_detail)


@router.post("/portfolio-summary")
def get_portfolio_summary(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get a concise AI portfolio summary for the authenticated account.

    The portfolio is read server-side rather than taken from the request body. Callers only
    ever posted an empty object, so the model was being asked to summarise a portfolio with
    no positions and zero value - which is what it dutifully described.
    """
    from app.api.portfolio import get_portfolio

    snapshot = get_portfolio(current_user=current_user, db=db)
    return generate_portfolio_summary(
        {
            "positions": snapshot["positions"],
            # The service names this total_value; the portfolio route calls it net_worth.
            "total_value": snapshot["net_worth"],
            "cash_balance": snapshot["cash_balance"],
            "unrealized_pnl": snapshot["unrealized_pnl"],
            "realized_pnl": snapshot["realized_pnl"],
        }
    )


@router.post("/extract-id")
def extract_id_fields(
    payload: dict[str, Any] | None = None,
    current_user: dict = Depends(get_current_user),
):
    """
    Extract fields from an ID document this account has uploaded.

    The path is confined to the caller's own KYC upload directory. The service base64s the
    named file and sends it to the model, so an unauthenticated caller passing an arbitrary
    path could have used this to read any file the server process can open.
    """
    file_path = (payload or {}).get("file_path", "")
    content_type = (payload or {}).get("content_type", "application/octet-stream")

    account_dir = os.path.abspath(os.path.join("uploads", "kyc", str(current_user["account_id"])))
    requested = os.path.abspath(file_path) if file_path else ""
    if not requested or os.path.commonpath([account_dir, requested]) != account_dir:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="file_path must be a document uploaded by this account.",
        )

    return extract_id_document_fields(requested, content_type)