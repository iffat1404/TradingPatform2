from typing import Dict, Any, Optional
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.orm import (
    Account, Order, OrderStatus, KYCStatus, OrderSide, OrderType,
    OrderEvent, Position, Fill, CashLedger, PriceHistoryMinute
)
from app.services.feed_simulator import get_current_tick_for_ticker
from app.services.market_clock import get_market_clock


class OrderValidationError(Exception):
    """Custom exception for order validation failures"""
    def __init__(self, reason_code: str, message: str):
        self.reason_code = reason_code
        self.message = message
        super().__init__(message)


def calculate_synthetic_prices(last_price: float) -> Dict[str, float]:
    """
    Calculate synthetic bid/ask prices from last price per Section A.3.
    
    spread = last_price × SPREAD_BPS / 10000
    synthetic_ask = last_price + spread / 2
    synthetic_bid = last_price − spread / 2
    """
    spread = last_price * settings.SPREAD_BPS / 10000
    synthetic_ask = last_price + spread / 2
    synthetic_bid = last_price - spread / 2
    
    return {
        "spread": spread,
        "synthetic_ask": synthetic_ask,
        "synthetic_bid": synthetic_bid
    }


def create_order_event(
    db: Session,
    order_id: str,
    from_status: OrderStatus,
    to_status: OrderStatus,
    event_type: str,
    notes: Optional[str] = None
) -> OrderEvent:
    """
    Create an order event for the audit trail per principle 6.
    """
    import uuid
    # Store both event type and notes in reason field
    if notes:
        reason = f"{event_type}|{notes}"
    else:
        reason = event_type
    
    # Use MarketClock for timestamps
    market_clock = get_market_clock()
    current_time = market_clock.now()
    
    event = OrderEvent(
        id=str(uuid.uuid4()),
        order_id=order_id,
        from_state=from_status,
        to_state=to_status,
        reason=reason,
        timestamp=current_time  # MarketClock time
    )
    db.add(event)
    return event


def transition_order_status(
    db: Session,
    order: Order,
    new_status: OrderStatus,
    event_type: str,
    notes: Optional[str] = None
) -> Order:
    """
    Transition an order to a new status and create an audit trail event.
    """
    old_status = order.status
    order.status = new_status
    order.updated_at = datetime.now(timezone.utc)
    
    create_order_event(db, order.id, old_status, new_status, event_type, notes)
    
    return order


def fill_order(
    db: Session,
    order: Order,
    fill_price: float,
    synthetic_prices: Dict[str, float]
) -> Fill:
    """
    Fill an order and create associated fill record.
    Per principle 3: no partial fills - always fill or rest in full.
    """
    from app.services.portfolio_engine import update_position_with_lots, update_cash_ledger
    import uuid
    
    # Use MarketClock for timestamps
    market_clock = get_market_clock()
    current_time = market_clock.now()
    
    # Create fill record
    fill = Fill(
        id=str(uuid.uuid4()),
        order_id=order.id,
        fill_price=fill_price,
        fill_qty=order.qty,
        fees=settings.COMMISSION_FLAT_FEE,
        timestamp=current_time  # MarketClock time
    )
    db.add(fill)
    
    # Update position with FIFO lot tracking
    update_position_with_lots(db, order.account_id, order.ticker, order.side, order.qty, fill_price)
    
    # Update cash ledger
    if order.side == OrderSide.BUY:
        notional = order.qty * fill_price
        debit = notional + settings.COMMISSION_FLAT_FEE
        update_cash_ledger(db, order.account_id, -debit, "BUY_FILL")
    else:  # SELL
        notional = order.qty * fill_price
        credit = notional - settings.COMMISSION_FLAT_FEE
        update_cash_ledger(db, order.account_id, credit, "SELL_FILL")
    
    # Transition order to FILLED
    transition_order_status(db, order, OrderStatus.FILLED, "FILL", f"Filled at ${fill_price:.2f}")
    
    return fill


def _get_current_market_timestamp(db: Session) -> Optional[datetime]:
    """Get current market timestamp based on system time."""
    # Use current system time per spec requirements
    return datetime.now(timezone.utc)


def validate_order(
    order_data: Dict[str, Any],
    account: Account,
    db: Session,
    current_price: Optional[float] = None
) -> Dict[str, Any]:
    """
    Validate an order according to the complete validation chain per Section 10.4.
    
    This is check 0 in the chain - KYC approval must come first.
    
    Validation chain (ordered, first failure short-circuits):
    0. KYC approved - account.kyc_status == "APPROVED"
    1. Valid ticker - one of the 7 supported tickers
    2. Market hours - within MARKET_OPEN–MARKET_CLOSE
    3. Price collar - limit price within ±PRICE_COLLAR_PCT of last price
    4. Notional cap - qty × price ≤ MAX_NOTIONAL_PER_ORDER
    5. Concentration limit - resulting position value ≤ MAX_CONCENTRATION_PCT of net worth
    6. Cash/collateral - buy: cash ≥ notional + fees, short: reserve collateral
    7. Rate limit - ≤ ORDER_RATE_LIMIT_PER_MINUTE/account/minute
    8. Wash-trade pattern - opposite-side same-ticker order within WASH_TRADE_WINDOW_SECONDS
    
    Returns:
        Dict with validation result
        
    Raises:
        OrderValidationError if validation fails
    """
    supported_tickers = ["AAPL", "GOOG", "IBM", "MSFT", "TSLA", "UL", "WMT"]
    
    # Check 0: KYC approved (first check per Section 10.4)
    if account.kyc_status != KYCStatus.APPROVED:
        raise OrderValidationError(
            reason_code="KYC_NOT_APPROVED",
            message="Your identity verification is still pending review. You can't place orders until it's approved."
        )
    
    # Check 1: Valid ticker
    ticker = order_data.get("ticker")
    if ticker not in supported_tickers:
        raise OrderValidationError(
            reason_code="INVALID_TICKER",
            message=f"Invalid ticker. Supported tickers are: {', '.join(supported_tickers)}"
        )
    
    # Check 2: Market hours, measured on the MarketClock — the platform's authoritative
    # time source. Using real wall-clock time here would reject every order whenever the
    # operator's real-world UTC time falls outside 9:30-16:00, regardless of where the
    # simulated session actually is.
    current_time = get_market_clock().now()
    market_open = current_time.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = current_time.replace(hour=16, minute=0, second=0, microsecond=0)
    if not (market_open <= current_time <= market_close):
        raise OrderValidationError(
            reason_code="MARKET_CLOSED",
            message=(
                f"Market is closed (9:30 AM - 4:00 PM UTC). "
                f"Simulated session time is {current_time.strftime('%Y-%m-%d %H:%M')} UTC."
            )
        )
    
    # Check 3: Price collar (for limit orders)
    order_type = order_data.get("type")
    limit_price = order_data.get("limit_price")
    
    if isinstance(order_type, str):
        order_type = OrderType(order_type)
    
    if order_type == OrderType.LIMIT and limit_price and current_price:
        collar_pct = settings.PRICE_COLLAR_PCT / 100
        lower_bound = current_price * (1 - collar_pct)
        upper_bound = current_price * (1 + collar_pct)
        
        if not (lower_bound <= limit_price <= upper_bound):
            raise OrderValidationError(
                reason_code="PRICE_COLLAR_BREACH",
                message=f"Limit price must be within ±{settings.PRICE_COLLAR_PCT}% of current price (${current_price:.2f})"
            )
    
    # Check 4: Notional cap
    qty = order_data.get("qty")
    price = limit_price if order_type == OrderType.LIMIT else current_price
    
    if price:
        notional = qty * price
        if notional > settings.MAX_NOTIONAL_PER_ORDER:
            raise OrderValidationError(
                reason_code="NOTIONAL_LIMIT_EXCEEDED",
                message=f"Order notional (${notional:,.2f}) exceeds maximum of ${settings.MAX_NOTIONAL_PER_ORDER:,.2f}"
            )
    
    # Check 5: Concentration limit
    positions = db.query(Position).filter(Position.account_id == account.id, Position.is_backtest == False).all()
    market_value = sum(pos.signed_qty * (current_price or 0.0) for pos in positions)
    net_worth = account.cash_balance + market_value
    if net_worth > 0:
        proposed_value = (qty or 0) * (price or 0)
        if proposed_value > settings.MAX_CONCENTRATION_PCT / 100 * net_worth:
            raise OrderValidationError(
                reason_code="CONCENTRATION_LIMIT_EXCEEDED",
                message="Order would exceed the maximum concentration limit for this account."
            )
    
    # Check 6: Cash/collateral
    side = order_data.get("side")
    if isinstance(side, str):
        side = OrderSide(side)
    
    if side == OrderSide.BUY and price:
        required = qty * price + settings.COMMISSION_FLAT_FEE
        if account.cash_balance < required:
            raise OrderValidationError(
                reason_code="INSUFFICIENT_BUYING_POWER",
                message=f"Insufficient buying power. Required: ${required:,.2f}, Available: ${account.cash_balance:,.2f}"
            )
    elif side == OrderSide.SELL and price:
        # Short selling would require collateral reservation
        notional = qty * price
        required_collateral = notional * settings.SHORT_COLLATERAL_MULTIPLIER
        if account.cash_balance < required_collateral:
            raise OrderValidationError(
                reason_code="INSUFFICIENT_BUYING_POWER",
                message=f"Insufficient collateral for short sale. Required: ${required_collateral:,.2f}, Available: ${account.cash_balance:,.2f}"
            )
    
    # Check 7: Rate limit
    # Check recent orders in the last minute
    one_minute_ago = datetime.now(timezone.utc) - timedelta(minutes=1)
    recent_orders = db.query(Order).filter(
        Order.account_id == account.id,
        Order.created_at >= one_minute_ago
    ).count()
    
    if recent_orders >= settings.ORDER_RATE_LIMIT_PER_MINUTE:
        raise OrderValidationError(
            reason_code="ORDER_RATE_LIMIT_EXCEEDED",
            message=f"Rate limit exceeded. Maximum {settings.ORDER_RATE_LIMIT_PER_MINUTE} orders per minute."
        )
    
    # Check 8: Wash-trade pattern (Tier 2 stretch)
    recent_opposite_orders = (
        db.query(Order)
        .filter(
            Order.account_id == account.id,
            Order.ticker == ticker,
            Order.side != side,
            Order.created_at >= datetime.now(timezone.utc) - timedelta(seconds=settings.WASH_TRADE_WINDOW_SECONDS),
        )
        .count()
    )
    if recent_opposite_orders > 0:
        return {"valid": True, "warnings": ["WASH_TRADE_FLAGGED"]}
    
    # If all checks pass
    return {
        "valid": True,
        "warnings": []
    }


def process_order(
    db: Session,
    order: Order,
    current_price: Optional[float] = None,
    account: Optional[Account] = None
) -> Order:
    """
    Process an order through the state machine.
    
    State machine per Section A.5:
    NEW → VALIDATED → ROUTED → FILLED
    NEW → REJECTED
    VALIDATED → CANCELLED
    """
    try:
        # Start in NEW status
        order.status = OrderStatus.NEW
        order.created_at = datetime.now(timezone.utc)
        db.add(order)
        db.commit()
        
        # Validate
        order_data = {
            "ticker": order.ticker,
            "side": order.side,
            "type": order.type,
            "qty": order.qty,
            "limit_price": order.limit_price
        }
        
        if not account:
            account = db.query(Account).filter(Account.id == order.account_id).first()
        
        validate_order(order_data, account, db, current_price)
        
        # Transition to VALIDATED
        transition_order_status(db, order, OrderStatus.VALIDATED, "VALIDATION_PASSED")
        
        # Check if marketable on arrival (for limit orders)
        if order.type == OrderType.LIMIT and order.limit_price and current_price:
            synthetic_prices = calculate_synthetic_prices(current_price)
            
            if order.side == OrderSide.BUY:
                # Limit buy is marketable if limit_price >= synthetic_ask
                if order.limit_price >= synthetic_prices["synthetic_ask"]:
                    # Fill immediately at limit price (or better)
                    fill_price = min(order.limit_price, synthetic_prices["synthetic_ask"])
                    transition_order_status(db, order, OrderStatus.ROUTED, "ROUTED", "Marketable on arrival")
                    fill_order(db, order, fill_price, synthetic_prices)
            else:  # SELL
                # Limit sell is marketable if limit_price <= synthetic_bid
                if order.limit_price <= synthetic_prices["synthetic_bid"]:
                    # Fill immediately at limit price (or better)
                    fill_price = max(order.limit_price, synthetic_prices["synthetic_bid"])
                    transition_order_status(db, order, OrderStatus.ROUTED, "ROUTED", "Marketable on arrival")
                    fill_order(db, order, fill_price, synthetic_prices)
        elif order.type == OrderType.MARKET and current_price:
            # Market orders fill on next tick (synthetic bid/ask)
            synthetic_prices = calculate_synthetic_prices(current_price)
            
            if order.side == OrderSide.BUY:
                fill_price = synthetic_prices["synthetic_ask"]
            else:  # SELL
                fill_price = synthetic_prices["synthetic_bid"]
            
            transition_order_status(db, order, OrderStatus.ROUTED, "ROUTED", "Market order")
            fill_order(db, order, fill_price, synthetic_prices)
        
        db.commit()
        db.refresh(order)
        return order
        
    except OrderValidationError as e:
        # Transition to REJECTED with the actual error code as event type
        transition_order_status(db, order, OrderStatus.REJECTED, e.reason_code, e.message)
        db.commit()
        db.refresh(order)
        return order