"""
Trade-plan level monitoring.

Watches open positions against the target / stop the trader recorded on the order that
opened them. When a level is reached, automatically executes a market sell order to close
the position and raises an alert informing the trader.

Evaluation is lazy — `check_levels` runs when the alerts endpoint is polled rather than on a
background thread. The websocket incident earlier in this project showed how costly an
always-on loop holding DB sessions can be, and polling is accurate enough for an advisory.
"""
from typing import Any, Dict, List, Optional
import uuid

from sqlalchemy.orm import Session

from app.models.orm import LevelAlert, Order, OrderSide, OrderStatus, OrderType, Position
from app.services.market_clock import get_market_clock
from app.services.portfolio_engine import get_latest_market_prices


def _governing_order(db: Session, account_id: str, ticker: str, is_long: bool) -> Optional[Order]:
    """
    The order whose recorded plan governs this position.

    A holding can be built from several orders, so use the most recent filled entry on the
    correct side that actually has levels set — that is the trader's current stated plan.
    """
    entry_side = OrderSide.BUY if is_long else OrderSide.SELL
    return (
        db.query(Order)
        .filter(
            Order.account_id == account_id,
            Order.ticker == ticker,
            Order.side == entry_side,
            Order.status == OrderStatus.FILLED,
            Order.is_backtest == False,  # noqa: E712
            (Order.target_price.isnot(None)) | (Order.stop_loss.isnot(None)),
        )
        .order_by(Order.created_at.desc())
        .first()
    )


def _breaches(is_long: bool, price: float, target: Optional[float], stop: Optional[float]) -> List[str]:
    """
    Which levels the current price has reached.

    Long: target is above, stop is below. Short inverts both — a short's stop is a rising
    price, which is the case most likely to be got wrong.
    """
    hit = []
    if is_long:
        if target is not None and price >= target:
            hit.append("target")
        if stop is not None and price <= stop:
            hit.append("stop")
    else:
        if target is not None and price <= target:
            hit.append("target")
        if stop is not None and price >= stop:
            hit.append("stop")
    return hit


def check_levels(db: Session, account_id: str) -> List[LevelAlert]:
    """
    Compare every open position against its plan and record any newly reached levels.
    When a level is reached, automatically execute a market SELL order to close the position.

    Returns the alerts that are currently live (unresolved), newest first. Existing
    unresolved alerts are reused rather than duplicated, so a position sitting below its
    stop does not raise a fresh alert on every poll.
    """
    prices = get_latest_market_prices(db)
    now = get_market_clock().now()

    positions = (
        db.query(Position)
        .filter(
            Position.account_id == account_id,
            Position.is_backtest == False,  # noqa: E712
            Position.signed_qty != 0,
        )
        .all()
    )
    open_tickers = {p.ticker for p in positions}

    # A closed position can no longer breach anything; retire its alerts so the same level
    # can fire again if the trader re-enters later.
    stale = (
        db.query(LevelAlert)
        .filter(LevelAlert.account_id == account_id, LevelAlert.resolved == False)  # noqa: E712
        .all()
    )
    for alert in stale:
        if alert.ticker not in open_tickers:
            alert.resolved = True
            alert.resolved_at = now

    for position in positions:
        price = prices.get(position.ticker)
        if not price:
            continue

        is_long = position.signed_qty > 0
        order = _governing_order(db, account_id, position.ticker, is_long)
        if order is None:
            continue  # no plan recorded for this holding

        for kind in _breaches(is_long, price, order.target_price, order.stop_loss):
            already = (
                db.query(LevelAlert)
                .filter(
                    LevelAlert.account_id == account_id,
                    LevelAlert.ticker == position.ticker,
                    LevelAlert.kind == kind,
                    LevelAlert.resolved == False,  # noqa: E712
                )
                .first()
            )
            if already:
                continue

            # Create alert
            alert = LevelAlert(
                id=str(uuid.uuid4()),
                account_id=account_id,
                ticker=position.ticker,
                order_id=order.id,
                kind=kind,
                level_price=order.target_price if kind == "target" else order.stop_loss,
                trigger_price=price,
                signed_qty=position.signed_qty,
                created_at=now,
                auto_sold=True,  # Mark as auto-sold
            )
            db.add(alert)

            # Auto-execute: Create a market SELL order to close the position
            close_order = Order(
                id=str(uuid.uuid4()),
                account_id=account_id,
                ticker=position.ticker,
                side=OrderSide.SELL,
                type=OrderType.MARKET,
                qty=abs(position.signed_qty),
                limit_price=None,
                target_price=None,
                stop_loss=None,
                status=OrderStatus.FILLED,  # Market orders fill immediately
                is_backtest=False,
                created_at=now,
            )
            db.add(close_order)

    db.commit()

    return (
        db.query(LevelAlert)
        .filter(LevelAlert.account_id == account_id, LevelAlert.resolved == False)  # noqa: E712
        .order_by(LevelAlert.created_at.desc())
        .all()
    )


def serialize_alert(alert: LevelAlert) -> Dict[str, Any]:
    is_long = alert.signed_qty > 0
    if alert.kind == "target":
        message = (
            f"{alert.ticker} reached your target of {alert.level_price:.2f} "
            f"(triggered at {alert.trigger_price:.2f})."
        )
        action = "You planned to take profit here."
    else:
        message = (
            f"{alert.ticker} hit your stop at {alert.level_price:.2f} "
            f"(triggered at {alert.trigger_price:.2f})."
        )
        action = "You planned to cut the loss here."

    # Add auto-sell confirmation
    auto_sell_info = f" ✓ Your position ({abs(alert.signed_qty)} shares) has been automatically sold at market price."

    return {
        "id": alert.id,
        "ticker": alert.ticker,
        "order_id": alert.order_id,
        "kind": alert.kind,
        "level_price": round(alert.level_price, 2),
        "trigger_price": round(alert.trigger_price, 2),
        "signed_qty": alert.signed_qty,
        "direction": "long" if is_long else "short",
        "acknowledged": alert.acknowledged,
        "created_at": alert.created_at,
        "message": message,
        "action": action,
        "auto_sold_info": auto_sell_info,
        "auto_sold": getattr(alert, 'auto_sold', False),
    }
