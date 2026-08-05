from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.core.security import get_current_user
from app.services.portfolio_engine import get_position_lots, calculate_portfolio_metrics, get_latest_market_prices
from app.models.orm import Position, Account

router = APIRouter()


@router.get("/")
def get_portfolio(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get portfolio summary including positions, cash, and net worth.
    Uses current prices from feed simulator based on system time.
    """
    # Get current prices from feed simulator
    current_prices = get_latest_market_prices(db)
    
    # Get positions
    positions = db.query(Position).filter(
        Position.account_id == current_user["account_id"],
        Position.is_backtest == False
    ).all()
    
    # Calculate portfolio metrics manually
    market_value = 0.0
    unrealized_pnl = 0.0
    realized_pnl = 0.0
    
    position_details = []
    for pos in positions:
        current_price = current_prices.get(pos.ticker, 0.0)
        position_market_value = pos.signed_qty * current_price
        position_unrealized_pnl = pos.signed_qty * (current_price - pos.avg_cost)
        
        market_value += position_market_value
        unrealized_pnl += position_unrealized_pnl
        realized_pnl += pos.realized_pnl
        
        position_details.append({
            "ticker": pos.ticker,
            "signed_qty": pos.signed_qty,
            "avg_cost": pos.avg_cost,
            "market_value": position_market_value,
            "unrealized_pnl": position_unrealized_pnl,
            "realized_pnl": pos.realized_pnl
        })
    
    # Get account cash balance
    account = db.query(Account).filter(Account.id == current_user["account_id"]).first()
    cash_balance = account.cash_balance if account else 0.0
    
    net_worth = cash_balance + market_value
    
    return {
        "cash_balance": cash_balance,
        "net_worth": net_worth,
        "market_value": market_value,
        "unrealized_pnl": unrealized_pnl,
        "realized_pnl": realized_pnl,
        "positions": position_details
    }


@router.get("/pnl")
def get_portfolio_pnl(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get portfolio P&L breakdown.
    Uses current prices from feed simulator based on system time.
    """
    # Get current prices from feed simulator
    current_prices = get_latest_market_prices(db)
    
    # Get positions
    positions = db.query(Position).filter(
        Position.account_id == current_user["account_id"],
        Position.is_backtest == False
    ).all()
    
    # Calculate P&L manually
    unrealized_pnl = 0.0
    realized_pnl = 0.0
    
    for pos in positions:
        current_price = current_prices.get(pos.ticker, 0.0)
        unrealized_pnl += pos.signed_qty * (current_price - pos.avg_cost)
        realized_pnl += pos.realized_pnl
    
    return {
        "unrealized_pnl": unrealized_pnl,
        "realized_pnl": realized_pnl,
        "total_pnl": unrealized_pnl + realized_pnl
    }


@router.get("/exposure")
def get_portfolio_exposure(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get portfolio exposure by ticker and sector.
    Uses current prices from feed simulator based on system time.
    """
    # Get current prices from feed simulator
    current_prices = get_latest_market_prices(db)
    
    metrics = calculate_portfolio_metrics(db, current_user["account_id"], current_prices)
    
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
    
    # Convert ticker exposure to array format for frontend
    ticker_exposure_list = []
    ticker_exposure = metrics.get("ticker_exposure", {})
    gross_exposure = metrics.get("gross_exposure", 0.0)
    
    for ticker, exposure_value in ticker_exposure.items():
        sector = SECTOR_MAPPING.get(ticker, "Other")
        exposure_pct = (exposure_value / gross_exposure * 100) if gross_exposure > 0 else 0.0
        ticker_exposure_list.append({
            "ticker": ticker,
            "sector": sector,
            "exposure": exposure_value,
            "exposure_pct": exposure_pct
        })
    
    return ticker_exposure_list


@router.get("/{ticker}/lots")
def get_ticker_lots(
    ticker: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get FIFO lots for a specific ticker.
    """
    lots = get_position_lots(db, current_user["account_id"], ticker)
    
    return [
        {
            "id": lot.id,
            "side": lot.side.value,
            "qty": lot.qty,
            "cost": lot.cost,
            "opened_at": lot.opened_at,
            "closed_at": lot.closed_at,
            "is_open": lot.closed_at is None
        }
        for lot in lots
    ]


@router.get("/positions")
def get_all_positions(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all positions for the authenticated user.
    """
    from app.models.orm import Position
    
    # Get current prices from feed simulator
    current_prices = get_latest_market_prices(db)
    
    # Get positions
    positions = db.query(Position).filter(
        Position.account_id == current_user["account_id"],
        Position.is_backtest == False
    ).all()
    
    position_details = []
    for pos in positions:
        current_price = current_prices.get(pos.ticker, 0.0)
        position_market_value = pos.signed_qty * current_price
        position_unrealized_pnl = pos.signed_qty * (current_price - pos.avg_cost)
        
        position_details.append({
            "ticker": pos.ticker,
            "signed_qty": pos.signed_qty,
            "avg_cost": pos.avg_cost,
            "current_price": current_price,
            "market_value": position_market_value,
            "unrealized_pnl": position_unrealized_pnl,
            "realized_pnl": pos.realized_pnl,
            "collateral_reserved": pos.collateral_reserved
        })
    
    return {"positions": position_details}