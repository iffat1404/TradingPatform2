from typing import Optional

# `status` is already used as a query-parameter name below, so the FastAPI status codes are
# aliased to keep both available.
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi import status as fastapi_status
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.core.security import get_current_user
from app.models.orm import Account, Order, OrderStatus, OrderSide, OrderType
from app.models.schemas import OrderCreate, OrderResponse, OrderLevelsUpdate
from app.services.order_engine import process_order, OrderValidationError, transition_order_status
from app.services.portfolio_engine import get_latest_market_price
from app.services.market_clock import get_market_clock
import uuid
from datetime import datetime, timezone

router = APIRouter()


@router.post("/", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
def create_order(
    order_data: OrderCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new order.
    
    This includes check 0 - KYC approval validation.
    """
    # Get account
    account = db.query(Account).filter(Account.id == current_user["account_id"]).first()
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found"
        )
    
    # Create order object
    market_clock = get_market_clock()
    current_time = market_clock.now()
    
    order = Order(
        id=str(uuid.uuid4()),
        account_id=current_user["account_id"],
        ticker=order_data.ticker,
        side=order_data.side,
        type=order_data.type,
        qty=order_data.qty,
        limit_price=order_data.limit_price,
        target_price=order_data.target_price,
        stop_loss=order_data.stop_loss,
        status=OrderStatus.NEW,
        is_backtest=False,
        created_at=current_time  # MarketClock time
    )
    
    # Process order through state machine using the latest simulated market price
    current_price = get_latest_market_price(db, order_data.ticker if hasattr(order_data, 'ticker') else None)

    # Score the decision BEFORE execution, while the pre-trade market context is still
    # current. Purely advisory: a poor score never prevents the order from proceeding, and
    # any failure in here is swallowed so scoring can't break order entry.
    decision_scores = None
    try:
        from app.services.decision_engine import evaluate_trade
        from app.api.decision import _coverage
        decision_scores = evaluate_trade(
            db,
            account_id=current_user["account_id"],
            ticker=order.ticker,
            side=order.side,
            qty=order.qty,
            price=current_price,
            target_price=order.target_price,
            stop_loss=order.stop_loss,
            journaled_coverage_pct=_coverage(db, current_user["account_id"]),
        )
    except Exception as e:
        print(f"Pre-trade decision scoring failed: {e}")

    processed_order = process_order(db, order, current_price, account)

    # Persist the snapshot once the order row definitely exists.
    if decision_scores is not None:
        try:
            from app.api.decision import persist_decision
            persist_decision(db, current_user["account_id"], processed_order.id, decision_scores)
        except Exception as e:
            print(f"Failed to store trade decision: {e}")
    
    # If rejected, return 422 with error details
    if processed_order.status == OrderStatus.REJECTED:
        # Get the rejection reason from the last event
        from app.models.orm import OrderEvent
        last_event = db.query(OrderEvent).filter(
            OrderEvent.order_id == processed_order.id
        ).order_by(OrderEvent.timestamp.desc()).first()
        
        if last_event and last_event.reason:
            # Parse the error code from reason (format: "EVENT_TYPE|notes")
            reason_text = last_event.reason
            if "|" in reason_text:
                parts = reason_text.split("|", 1)
                error_code = parts[0].strip()
                message = parts[1].strip()
            else:
                error_code = reason_text
                message = reason_text
        else:
            error_code = "VALIDATION_FAILED"
            message = "Order validation failed"
        
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error_code": error_code,
                "message": message
            }
        )
    
    return processed_order


@router.get("/")
def get_orders(
    status: Optional[str] = Query(None, description="Filter by order status, e.g. FILLED"),
    ticker: Optional[str] = Query(None, description="Filter by ticker"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get orders for the authenticated user, newest first.

    The status/ticker filters are honoured server-side — callers (the Orders page filters,
    the journal's "link a filled trade" picker, the AI Assistant's rejected-order list) all
    pass them and previously had them silently ignored.
    """
    query = db.query(Order).filter(Order.account_id == current_user["account_id"])

    if status:
        try:
            query = query.filter(Order.status == OrderStatus(status.upper()))
        except ValueError:
            raise HTTPException(
                status_code=fastapi_status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown status '{status}'. Valid: {', '.join(s.value for s in OrderStatus)}",
            )
    if ticker:
        query = query.filter(Order.ticker == ticker.upper())

    orders = query.order_by(Order.created_at.desc()).all()

    return [
        {
            "id": order.id,
            "ticker": order.ticker,
            "side": order.side.value,
            "type": order.type.value,
            "qty": order.qty,
            "limit_price": order.limit_price,
            "target_price": order.target_price,
            "stop_loss": order.stop_loss,
            "status": order.status.value,
            "created_at": order.created_at
        }
        for order in orders
    ]


@router.get("/{order_id}")
def get_order(
    order_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific order"""
    order = db.query(Order).filter(
        Order.id == order_id,
        Order.account_id == current_user["account_id"]
    ).first()
    
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )
    
    return {
        "id": order.id,
        "ticker": order.ticker,
        "side": order.side.value,
        "type": order.type.value,
        "qty": order.qty,
        "limit_price": order.limit_price,
        "target_price": order.target_price,
        "stop_loss": order.stop_loss,
        "status": order.status.value,
        "created_at": order.created_at
    }


@router.delete("/{order_id}")
def cancel_order(
    order_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Cancel a resting limit order"""
    order = db.query(Order).filter(
        Order.id == order_id,
        Order.account_id == current_user["account_id"]
    ).first()
    
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )
    
    # Can only cancel VALIDATED orders
    if order.status != OrderStatus.VALIDATED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel order with status: {order.status.value}"
        )
    
    # Transition to CANCELLED
    transition_order_status(db, order, OrderStatus.CANCELLED, "CANCELLED", "Cancelled by user")
    db.commit()
    
    return {"message": "Order cancelled", "order_id": order_id}


@router.get("/{order_id}/events")
def get_order_events(
    order_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get the event trail for an order"""
    # Verify order belongs to user
    order = db.query(Order).filter(
        Order.id == order_id,
        Order.account_id == current_user["account_id"]
    ).first()
    
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )
    
    from app.models.orm import OrderEvent
    events = db.query(OrderEvent).filter(
        OrderEvent.order_id == order_id
    ).order_by(OrderEvent.timestamp.asc()).all()
    
    return [
        {
            "from_status": event.from_state.value,
            "to_status": event.to_state.value,
            "event_type": event.reason.split("|")[0] if event.reason and "|" in event.reason else event.reason,
            "notes": event.reason.split("|")[1].strip() if event.reason and "|" in event.reason else "",
            "timestamp": event.timestamp
        }
        for event in events
    ]

@router.patch("/{order_id}/levels")
def update_order_levels(
    order_id: str,
    levels: OrderLevelsUpdate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Adjust the target price / stop loss on an existing order.

    These levels are a record of intent, not instructions — nothing auto-exits on them.
    Each change is written to the order's event trail as LEVELS_UPDATED, which is what
    lets the journal detect repeated plan-moving.
    """
    order = db.query(Order).filter(
        Order.id == order_id,
        Order.account_id == current_user["account_id"]
    ).first()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    changes = []
    if levels.target_price is not None and levels.target_price != order.target_price:
        changes.append(f"target {order.target_price} -> {levels.target_price}")
        order.target_price = levels.target_price
    if levels.stop_loss is not None and levels.stop_loss != order.stop_loss:
        changes.append(f"stop {order.stop_loss} -> {levels.stop_loss}")
        order.stop_loss = levels.stop_loss

    if not changes:
        return {
            "id": order.id,
            "target_price": order.target_price,
            "stop_loss": order.stop_loss,
            "changed": False,
        }

    # Audit the edit without altering the order's lifecycle state.
    from app.services.order_engine import create_order_event
    create_order_event(
        db, order.id, order.status, order.status, "LEVELS_UPDATED", "; ".join(changes)
    )
    db.commit()
    db.refresh(order)

    return {
        "id": order.id,
        "target_price": order.target_price,
        "stop_loss": order.stop_loss,
        "changed": True,
        "changes": changes,
    }
