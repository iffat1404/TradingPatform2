from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.core.security import get_current_user
from app.services.portfolio_engine import calculate_portfolio_metrics, get_latest_market_prices
import csv
from io import StringIO
from datetime import datetime, timezone

router = APIRouter()


@router.get("/portfolio")
def get_portfolio_report(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate on-demand portfolio report.
    Includes positions, P&L, and net worth at current time.
    """
    current_prices = get_latest_market_prices(db)
    
    # Calculate portfolio metrics
    metrics = calculate_portfolio_metrics(db, current_user["account_id"], current_prices)
    
    # Get positions
    from app.models.orm import Position
    positions = db.query(Position).filter(
        Position.account_id == current_user["account_id"],
        Position.is_backtest == False
    ).all()
    
    position_details = []
    for pos in positions:
        current_price = current_prices.get(pos.ticker, 0.0)
        position_details.append({
            "ticker": pos.ticker,
            "signed_qty": pos.signed_qty,
            "avg_cost": pos.avg_cost,
            "current_price": current_price,
            "market_value": pos.signed_qty * current_price,
            "unrealized_pnl": pos.signed_qty * (current_price - pos.avg_cost),
            "realized_pnl": pos.realized_pnl
        })
    
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "account_id": current_user["account_id"],
        "metrics": metrics,
        "positions": position_details
    }


@router.get("/portfolio/export")
def export_portfolio_report(
    format: str = Query("csv", description="Export format: csv"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Export portfolio report to CSV.
    PDF export is deferred until content is stable.
    """
    if format != "csv":
        raise HTTPException(status_code=400, detail="Only CSV format is currently supported")
    
    # Get portfolio data
    report = get_portfolio_report(current_user, db)
    
    # Create CSV
    output = StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(["Position Report", "", "", f"Generated: {report['generated_at']}"])
    writer.writerow([])
    writer.writerow(["Ticker", "Quantity", "Avg Cost", "Current Price", "Market Value", "Unrealized P&L", "Realized P&L"])
    
    # Write positions
    for pos in report["positions"]:
        writer.writerow([
            pos["ticker"],
            pos["signed_qty"],
            f"{pos['avg_cost']:.2f}",
            f"{pos['current_price']:.2f}",
            f"{pos['market_value']:.2f}",
            f"{pos['unrealized_pnl']:.2f}",
            f"{pos['realized_pnl']:.2f}"
        ])
    
    # Write summary
    writer.writerow([])
    writer.writerow(["Summary", "", "", "", "", "", ""])
    writer.writerow(["Cash Balance", f"{report['metrics']['cash_balance']:.2f}"])
    writer.writerow(["Market Value", f"{report['metrics']['market_value']:.2f}"])
    writer.writerow(["Unrealized P&L", f"{report['metrics']['unrealized_pnl']:.2f}"])
    writer.writerow(["Realized P&L", f"{report['metrics']['realized_pnl']:.2f}"])
    writer.writerow(["Net Worth", f"{report['metrics']['net_worth']:.2f}"])
    
    # Return as streaming response
    output.seek(0)
    response = StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=portfolio_report_{current_user['account_id']}.csv"}
    )
    
    return response