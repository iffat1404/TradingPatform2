from typing import Dict, List, Optional
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from app.models.orm import (
    Account, BacktestStrategy, BacktestRun, Order, OrderType, OrderSide,
    PriceHistoryDaily, Position, CashLedger
)
from app.services.portfolio_engine import update_position_with_lots, update_cash_ledger
from app.services.analytics_engine import calculate_rsi
import json
import uuid


def calculate_backtest_metrics(
    starting_capital: float,
    ending_capital: float,
    trades: List[Dict],
    equity_curve: List[float]
) -> Dict[str, any]:
    """
    Calculate backtest performance metrics.
    """
    total_return = (ending_capital - starting_capital) / starting_capital
    
    # Calculate max drawdown
    peak = equity_curve[0]
    max_drawdown = 0.0
    for value in equity_curve:
        if value > peak:
            peak = value
        drawdown = (peak - value) / peak
        if drawdown > max_drawdown:
            max_drawdown = drawdown
    
    # Calculate win rate
    winning_trades = sum(1 for t in trades if t.get("pnl", 0) > 0)
    total_trades = len(trades)
    win_rate = winning_trades / total_trades if total_trades > 0 else 0.0
    
    return {
        "total_return": total_return,
        "max_drawdown": max_drawdown,
        "win_rate": win_rate,
        "total_trades": total_trades,
        "winning_trades": winning_trades
    }


def calculate_benchmark_return(
    ticker: str,
    start_date: datetime,
    end_date: datetime,
    db: Session
) -> float:
    """
    Calculate buy-and-hold benchmark return for the same ticker and date range.
    """
    # Get price at start and end of period
    start_price = db.query(PriceHistoryDaily).filter(
        PriceHistoryDaily.ticker == ticker,
        PriceHistoryDaily.date >= start_date
    ).order_by(PriceHistoryDaily.date.asc()).first()
    
    end_price = db.query(PriceHistoryDaily).filter(
        PriceHistoryDaily.ticker == ticker,
        PriceHistoryDaily.date <= end_date
    ).order_by(PriceHistoryDaily.date.desc()).first()
    
    if not start_price or not end_price:
        return 0.0
    
    return (end_price.close - start_price.open) / start_price.open


def run_backtest(
    db: Session,
    strategy_id: str,
    account_id: str,
    start_date: datetime,
    end_date: datetime
) -> BacktestRun:
    """
    Run a backtest for a strategy using historical data.
    Uses the same order_engine as live trading but with is_backtest=True.
    """
    import uuid
    
    # Get strategy
    strategy = db.query(BacktestStrategy).filter(
        BacktestStrategy.id == strategy_id
    ).first()
    
    if not strategy:
        raise ValueError(f"Strategy not found: {strategy_id}")
    
    # Get account
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise ValueError(f"Account not found: {account_id}")
    
    # Create backtest run record
    run = BacktestRun(
        id=str(uuid.uuid4()),
        strategy_id=strategy_id,
        account_id=account_id,
        start_date=start_date,
        end_date=end_date,
        starting_capital=account.starting_capital,
        ending_capital=account.starting_capital,
        total_return=0.0,
        benchmark_return=0.0,
        max_drawdown=0.0,
        win_rate=0.0,
        total_trades=0,
        winning_trades=0,
        status="running"
    )
    db.add(run)
    db.commit()
    
    try:
        # Get historical price data
        prices = db.query(PriceHistoryDaily).filter(
            PriceHistoryDaily.ticker == strategy.ticker,
            PriceHistoryDaily.date >= start_date,
            PriceHistoryDaily.date <= end_date
        ).order_by(PriceHistoryDaily.date.asc()).all()
        
        if len(prices) < 20:
            raise ValueError("Insufficient historical data for backtest")
        
        # Calculate RSI for the period
        close_prices = [p.close for p in prices]
        rsi_values = calculate_rsi(close_prices, 14)
        
        # Parse strategy rules
        entry_rule = json.loads(strategy.entry_rule)
        exit_rule = json.loads(strategy.exit_rule)
        
        # Initialize backtest state
        current_capital = account.starting_capital
        position = None  # (entry_price, qty)
        trades = []
        equity_curve = [current_capital]
        
        # Simulate trading day by day
        for i, price in enumerate(prices):
            if i < 14:  # Need at least 14 days for RSI
                equity_curve.append(current_capital)
                continue
            
            current_rsi = rsi_values[i]
            if current_rsi is None:
                equity_curve.append(current_capital)
                continue
            
            # Check entry conditions (simplified RSI strategy)
            should_enter = False
            should_exit = False
            
            # Example: RSI < 30 for buy entry, RSI > 70 for sell entry
            if entry_rule.get("type") == "rsi_oversold":
                if current_rsi < entry_rule.get("threshold", 30):
                    should_enter = True
            elif entry_rule.get("type") == "rsi_overbought":
                if current_rsi > entry_rule.get("threshold", 70):
                    should_enter = True
            
            # Check exit conditions
            if position:
                if exit_rule.get("type") == "rsi_overbought":
                    if current_rsi > exit_rule.get("threshold", 70):
                        should_exit = True
                elif exit_rule.get("type") == "rsi_oversold":
                    if current_rsi < exit_rule.get("threshold", 30):
                        should_exit = True
            
            # Execute entry
            if should_enter and not position:
                entry_price = price.open
                qty = strategy.position_size
                cost = qty * entry_price
                
                if current_capital >= cost:
                    # Create backtest order (simulated, not through full order_engine for simplicity)
                    position = {
                        "entry_price": entry_price,
                        "qty": qty,
                        "entry_date": price.date
                    }
                    current_capital -= cost
                    
                    # Record trade (will be closed on exit)
            
            # Execute exit
            elif should_exit and position:
                exit_price = price.close
                qty = position["qty"]
                proceeds = qty * exit_price
                pnl = proceeds - (position["qty"] * position["entry_price"])
                
                current_capital += proceeds
                
                trades.append({
                    "entry_price": position["entry_price"],
                    "exit_price": exit_price,
                    "qty": qty,
                    "pnl": pnl,
                    "entry_date": position["entry_date"],
                    "exit_date": price.date
                })
                
                position = None
            
            equity_curve.append(current_capital)
        
        # Close any remaining position at end
        if position:
            exit_price = prices[-1].close
            qty = position["qty"]
            proceeds = qty * exit_price
            pnl = proceeds - (position["qty"] * position["entry_price"])
            
            current_capital += proceeds
            
            trades.append({
                "entry_price": position["entry_price"],
                "exit_price": exit_price,
                "qty": qty,
                "pnl": pnl,
                "entry_date": position["entry_date"],
                "exit_date": prices[-1].date
            })
        
        # Calculate metrics
        metrics = calculate_backtest_metrics(
            account.starting_capital,
            current_capital,
            trades,
            equity_curve
        )
        
        # Calculate benchmark
        benchmark_return = calculate_benchmark_return(
            strategy.ticker,
            start_date,
            end_date,
            db
        )
        
        # Update run record
        run.ending_capital = current_capital
        run.total_return = metrics["total_return"]
        run.benchmark_return = benchmark_return
        run.max_drawdown = metrics["max_drawdown"]
        run.win_rate = metrics["win_rate"]
        run.total_trades = metrics["total_trades"]
        run.winning_trades = metrics["winning_trades"]
        run.status = "completed"
        
        db.commit()
        db.refresh(run)
        
        return run
        
    except Exception as e:
        run.status = "failed"
        run.error_message = str(e)
        db.commit()
        raise e