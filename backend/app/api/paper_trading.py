from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.core.security import get_current_user
from app.models.orm import BacktestStrategy, BacktestRun, Account
from app.services.backtest_engine import run_backtest
from datetime import datetime, timezone
import json
import uuid

router = APIRouter()


@router.post("/strategies")
def create_strategy(
    strategy_data: dict,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new backtest strategy.
    """
    strategy = BacktestStrategy(
        id=str(uuid.uuid4()),
        account_id=current_user["account_id"],
        name=strategy_data.get("name"),
        ticker=strategy_data.get("ticker"),
        entry_rule=json.dumps(strategy_data.get("entry_rule", {})),
        exit_rule=json.dumps(strategy_data.get("exit_rule", {})),
        position_size=strategy_data.get("position_size", 100)
    )
    
    db.add(strategy)
    db.commit()
    db.refresh(strategy)
    
    return {
        "id": strategy.id,
        "name": strategy.name,
        "ticker": strategy.ticker,
        "entry_rule": json.loads(strategy.entry_rule),
        "exit_rule": json.loads(strategy.exit_rule),
        "position_size": strategy.position_size,
        "is_active": strategy.is_active
    }


@router.get("/strategies")
def get_strategies(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List all strategies for the authenticated user.
    """
    strategies = db.query(BacktestStrategy).filter(
        BacktestStrategy.account_id == current_user["account_id"]
    ).all()
    
    return [
        {
            "id": s.id,
            "name": s.name,
            "ticker": s.ticker,
            "entry_rule": json.loads(s.entry_rule),
            "exit_rule": json.loads(s.exit_rule),
            "position_size": s.position_size,
            "is_active": s.is_active,
            "created_at": s.created_at.isoformat()
        }
        for s in strategies
    ]


@router.get("/backtest")
def get_backtest_runs(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List all backtest runs for the authenticated user.
    """
    try:
        runs = db.query(BacktestRun).filter(
            BacktestRun.account_id == current_user["account_id"]
        ).order_by(BacktestRun.created_at.desc()).all()
        
        return [
            {
                "id": run.id,
                "strategy_id": run.strategy_id,
                "start_date": run.start_date.isoformat() if run.start_date else None,
                "end_date": run.end_date.isoformat() if run.end_date else None,
                "status": run.status if hasattr(run, 'status') else "unknown",
                "total_return": run.total_return if hasattr(run, 'total_return') else None,
                "benchmark_return": run.benchmark_return if hasattr(run, 'benchmark_return') else None,
                "max_drawdown": run.max_drawdown if hasattr(run, 'max_drawdown') else None,
                "win_rate": run.win_rate if hasattr(run, 'win_rate') else None,
                "total_trades": run.total_trades if hasattr(run, 'total_trades') else None,
                "created_at": run.created_at.isoformat() if run.created_at else None,
                "completed_at": run.completed_at.isoformat() if run.completed_at else None
            }
            for run in runs
        ]
    except Exception as e:
        # Return empty list if table doesn't exist or other error
        return []


@router.post("/backtest/{strategy_id}/run")
def run_backtest_endpoint(
    strategy_id: str,
    run_params: dict,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Run a backtest for a strategy.
    """
    # Parse dates with UTC timezone per principle 12
    start_date = datetime.strptime(run_params.get("start_date"), "%Y-%m-%d").replace(tzinfo=timezone.utc)
    end_date = datetime.strptime(run_params.get("end_date"), "%Y-%m-%d").replace(tzinfo=timezone.utc)
    
    # Run backtest
    run = run_backtest(
        db,
        strategy_id,
        current_user["account_id"],
        start_date,
        end_date
    )
    
    return {
        "run_id": run.id,
        "strategy_id": run.strategy_id,
        "status": run.status,
        "start_date": run.start_date.isoformat(),
        "end_date": run.end_date.isoformat(),
        "total_return": run.total_return,
        "benchmark_return": run.benchmark_return,
        "max_drawdown": run.max_drawdown,
        "win_rate": run.win_rate,
        "total_trades": run.total_trades
    }


@router.get("/backtest/{run_id}/results")
def get_backtest_results(
    run_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get detailed results for a backtest run.
    """
    run = db.query(BacktestRun).filter(
        BacktestRun.id == run_id,
        BacktestRun.account_id == current_user["account_id"]
    ).first()
    
    if not run:
        raise HTTPException(status_code=404, detail="Backtest run not found")
    
    return {
        "run_id": run.id,
        "strategy_id": run.strategy_id,
        "start_date": run.start_date.isoformat(),
        "end_date": run.end_date.isoformat(),
        "starting_capital": run.starting_capital,
        "ending_capital": run.ending_capital,
        "total_return": run.total_return,
        "benchmark_return": run.benchmark_return,
        "max_drawdown": run.max_drawdown,
        "win_rate": run.win_rate,
        "total_trades": run.total_trades,
        "winning_trades": run.winning_trades,
        "status": run.status,
        "error_message": run.error_message,
        "created_at": run.created_at.isoformat()
    }