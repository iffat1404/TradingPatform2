from typing import Optional, List, Dict
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.orm import Account, Position, PositionLot, CashLedger, OrderSide, PriceHistoryMinute
from app.services.feed_simulator import get_current_tick_for_ticker, get_all_current_ticks


def get_latest_market_price(db: Session, ticker: Optional[str]) -> Optional[float]:
    """Return the current close price for a ticker from the feed simulator based on system time."""
    if not ticker:
        return None
    current_tick = get_current_tick_for_ticker(ticker.upper(), db)
    return current_tick["close"] if current_tick else None


def get_latest_market_prices(db: Session) -> Dict[str, float]:
    """Return the current close price for all supported tickers from the feed simulator."""
    all_ticks = get_all_current_ticks(db)
    return {ticker: tick["close"] for ticker, tick in all_ticks.items()}


def update_position_with_lots(
    db: Session,
    account_id: str,
    ticker: str,
    side: OrderSide,
    qty: int,
    price: float
) -> Position:
    """
    Update or create a position based on a fill, tracking FIFO lots.
    Uses FIFO cost basis per principle 5.
    """
    import uuid
    
    # Get or create position
    position = db.query(Position).filter(
        Position.account_id == account_id,
        Position.ticker == ticker,
        Position.is_backtest == False
    ).first()
    
    if not position:
        # New position
        import uuid
        signed_qty = qty if side == OrderSide.BUY else -qty
        avg_cost = price
        position = Position(
            id=str(uuid.uuid4()),
            account_id=account_id,
            ticker=ticker,
            signed_qty=signed_qty,
            avg_cost=avg_cost,
            is_backtest=False
        )
        db.add(position)
        db.flush()  # Get the ID
        
        # Create the first lot
        lot = PositionLot(
            id=str(uuid.uuid4()),
            position_id=position.id,
            ticker=ticker,
            side=side,
            qty=qty,
            cost=price,
            is_backtest=False
        )
        db.add(lot)
    else:
        # Update existing position with FIFO lot management
        current_qty = position.signed_qty
        new_qty = qty if side == OrderSide.BUY else -qty
        total_qty = current_qty + new_qty
        
        if side == OrderSide.BUY:
            # Adding to position - create new lot
            lot = PositionLot(
                id=str(uuid.uuid4()),
                position_id=position.id,
                ticker=ticker,
                side=side,
                qty=qty,
                cost=price,
                is_backtest=False
            )
            db.add(lot)
            
            # Recalculate average cost
            # Simple average for simplicity (could be weighted average)
            total_cost = (abs(current_qty) * position.avg_cost) + (qty * price)
            avg_cost = total_cost / abs(total_qty) if total_qty != 0 else price
        else:  # SELL
            # Handle collateral reservation for short positions
            if total_qty < 0:
                # Position became short or more short - reserve collateral
                notional = abs(total_qty) * price
                collateral_to_reserve = notional * settings.SHORT_COLLATERAL_MULTIPLIER
                position.collateral_reserved = collateral_to_reserve
            elif total_qty >= 0:
                # Position closed or flipped to long - release collateral
                position.collateral_reserved = 0.0
            
            # Closing position - close oldest lots first (FIFO)
            remaining_to_close = qty
            realized_pnl = 0.0
            
            # Get open lots ordered by opened_at (oldest first)
            open_lots = db.query(PositionLot).filter(
                PositionLot.position_id == position.id,
                PositionLot.closed_at.is_(None)
            ).order_by(PositionLot.opened_at.asc()).all()
            
            for lot in open_lots:
                if remaining_to_close <= 0:
                    break
                
                lot_qty = lot.qty
                close_qty = min(lot_qty, remaining_to_close)
                
                # Calculate realized P&L for this lot
                if lot.side == OrderSide.BUY:
                    # Closing a long position
                    pnl = (price - lot.cost) * close_qty
                else:
                    # Closing a short position
                    pnl = (lot.cost - price) * close_qty
                
                realized_pnl += pnl
                
                if close_qty == lot_qty:
                    # Fully close this lot
                    lot.closed_at = datetime.now(timezone.utc)
                else:
                    # Partially close this lot
                    lot.qty = lot_qty - close_qty
                
                remaining_to_close -= close_qty
            
            # Update position realized P&L
            position.realized_pnl += realized_pnl
            
            # Recalculate average cost for remaining position
            if total_qty != 0:
                # Get remaining open lots
                remaining_lots = db.query(PositionLot).filter(
                    PositionLot.position_id == position.id,
                    PositionLot.closed_at.is_(None)
                ).all()
                
                if remaining_lots:
                    total_remaining_qty = sum(lot.qty for lot in remaining_lots)
                    total_remaining_cost = sum(lot.qty * lot.cost for lot in remaining_lots)
                    avg_cost = total_remaining_cost / total_remaining_qty
                else:
                    avg_cost = 0
            else:
                avg_cost = 0
        
        position.signed_qty = total_qty
        position.avg_cost = avg_cost
        position.updated_at = datetime.now(timezone.utc)
    
    db.commit()
    db.refresh(position)
    return position


def get_position_lots(
    db: Session,
    account_id: str,
    ticker: str
) -> List[PositionLot]:
    """
    Get all lots for a position, ordered by opened_at.
    """
    position = db.query(Position).filter(
        Position.account_id == account_id,
        Position.ticker == ticker,
        Position.is_backtest == False
    ).first()
    
    if not position:
        return []
    
    lots = db.query(PositionLot).filter(
        PositionLot.position_id == position.id
    ).order_by(PositionLot.opened_at.asc()).all()
    
    return lots


def calculate_portfolio_metrics(
    db: Session,
    account_id: str,
    current_prices: Dict[str, float]
) -> Dict[str, any]:
    """
    Calculate portfolio metrics including net worth, P&L, and exposure.
    """
    # Get account
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        return {}
    
    # Get all positions
    positions = db.query(Position).filter(
        Position.account_id == account_id,
        Position.is_backtest == False
    ).all()
    
    # Calculate metrics
    cash_balance = account.cash_balance
    total_collateral_reserved = sum(pos.collateral_reserved for pos in positions)
    
    unrealized_pnl = 0.0
    market_value = 0.0
    gross_exposure = 0.0
    net_exposure = 0.0
    
    ticker_exposure = {}
    sector_exposure = {}
    
    # Hardcoded sector mapping per Section B.4
    SECTOR_MAPPING = {
        "AAPL": "Technology",
        "MSFT": "Technology",
        "IBM": "Technology",
        "GOOG": "Communication Services",
        "TSLA": "Consumer Discretionary",
        "WMT": "Consumer Staples",
        "UL": "Consumer Staples"
    }
    
    for position in positions:
        ticker = position.ticker
        current_price = current_prices.get(ticker, 0.0)
        
        if current_price == 0.0:
            continue
        
        # Unrealized P&L: signed_qty × (last_price − avg_cost)
        position_unrealized_pnl = position.signed_qty * (current_price - position.avg_cost)
        unrealized_pnl += position_unrealized_pnl
        
        # Market value: signed_qty × last_price
        position_market_value = position.signed_qty * current_price
        market_value += position_market_value
        
        # Exposure calculations
        absolute_value = abs(position_market_value)
        gross_exposure += absolute_value
        net_exposure += position_market_value
        
        # Ticker exposure
        ticker_exposure[ticker] = ticker_exposure.get(ticker, 0.0) + absolute_value
        
        # Sector exposure
        sector = SECTOR_MAPPING.get(ticker, "Other")
        sector_exposure[sector] = sector_exposure.get(sector, 0.0) + absolute_value
    
    # Net worth = cash + market value - collateral_reserved
    net_worth = cash_balance + market_value - total_collateral_reserved
    
    return {
        "cash_balance": cash_balance,
        "market_value": market_value,
        "unrealized_pnl": unrealized_pnl,
        "realized_pnl": sum(pos.realized_pnl for pos in positions),
        "net_worth": net_worth,
        "collateral_reserved": total_collateral_reserved,
        "gross_exposure": gross_exposure,
        "net_exposure": net_exposure,
        "ticker_exposure": ticker_exposure,
        "sector_exposure": sector_exposure,
        "position_count": len(positions)
    }


def update_cash_ledger(
    db: Session,
    account_id: str,
    amount: float,
    reason: str
) -> CashLedger:
    """
    Update cash balance and create ledger entry.
    """
    import uuid
    # Create ledger entry
    ledger = CashLedger(
        id=str(uuid.uuid4()),
        account_id=account_id,
        amount=amount,
        reason=reason,
        timestamp=datetime.now(timezone.utc)
    )
    db.add(ledger)
    
    # Update account cash balance
    account = db.query(Account).filter(Account.id == account_id).first()
    if account:
        account.cash_balance += amount
        account.updated_at = datetime.now(timezone.utc)
    
    db.commit()
    db.refresh(ledger)
    return ledger