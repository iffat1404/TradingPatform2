from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, timezone
import uuid
from app.core.db import get_db
from app.core.security import require_admin, get_current_user
from app.core.config import settings
from app.models.orm import Account, KYCSubmission, KYCStatus, OrderEvent, Order, Fill, MarketSession
from app.models.schemas import KYCSubmissionResponse, KYCReviewRequest
from app.services.portfolio_engine import calculate_portfolio_metrics, get_latest_market_prices
from app.services.feed_simulator import reset_feed_simulator
from app.services.market_clock import get_market_clock

router = APIRouter()


@router.get("/kyc", dependencies=[Depends(require_admin)])
def get_kyc_queue(
    status_filter: Optional[str] = "PENDING_REVIEW",
    db: Session = Depends(get_db)
):
    """
    Get KYC submission queue for admin review.
    
    Can filter by status (default: PENDING_REVIEW).
    """
    query = db.query(KYCSubmission)
    
    if status_filter:
        try:
            status_enum = KYCStatus(status_filter)
            query = query.filter(KYCSubmission.status == status_enum)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {status_filter}"
            )
    
    submissions = query.order_by(KYCSubmission.submitted_at.desc()).all()
    
    return [
        {
            "id": sub.id,
            "account_id": sub.account_id,
            "id_type": sub.id_type,
            "status": sub.status.value,
            "auto_check_passed": sub.auto_check_passed,
            "auto_check_notes": sub.auto_check_notes,
            "submitted_at": sub.submitted_at,
            "extraction_confidence": sub.extraction_confidence
        }
        for sub in submissions
    ]


@router.get("/kyc/{submission_id}", dependencies=[Depends(require_admin)])
def get_kyc_submission(
    submission_id: str,
    db: Session = Depends(get_db)
):
    """
    Get detailed KYC submission for admin review.
    """
    submission = db.query(KYCSubmission).filter(
        KYCSubmission.id == submission_id
    ).first()
    
    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="KYC submission not found"
        )
    
    # Get account info for comparison
    account = db.query(Account).filter(Account.id == submission.account_id).first()
    
    return {
        "id": submission.id,
        "account_id": submission.account_id,
        "account_username": account.username if account else None,
        "id_type": submission.id_type,
        "document_path": submission.document_path,
        "extracted_full_name": submission.extracted_full_name,
        "extracted_dob": submission.extracted_dob,
        "extracted_id_number": submission.extracted_id_number,
        "extracted_expiry_date": submission.extracted_expiry_date,
        "extracted_issuing_country": submission.extracted_issuing_country,
        "extraction_confidence": submission.extraction_confidence,
        "auto_check_passed": submission.auto_check_passed,
        "auto_check_notes": submission.auto_check_notes,
        "status": submission.status.value,
        "submitted_at": submission.submitted_at,
        "reviewed_at": submission.reviewed_at
    }


@router.post("/kyc/{submission_id}/approve", dependencies=[Depends(require_admin)])
def approve_kyc(
    submission_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Approve a KYC submission.
    
    Per principle 8, only Admin can approve KYC. This is a human decision,
    not automated.
    """
    submission = db.query(KYCSubmission).filter(
        KYCSubmission.id == submission_id
    ).first()
    
    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="KYC submission not found"
        )
    
    if submission.status != KYCStatus.PENDING_REVIEW:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot approve submission with status: {submission.status.value}"
        )
    
    # Update submission
    submission.status = KYCStatus.APPROVED
    submission.reviewed_by_admin_id = current_user["account_id"]
    submission.reviewed_at = datetime.now(timezone.utc)
    
    # Update account KYC status
    account = db.query(Account).filter(Account.id == submission.account_id).first()
    if account:
        account.kyc_status = KYCStatus.APPROVED
    
    db.commit()
    
    return {"message": "KYC submission approved", "submission_id": submission_id}


@router.post("/kyc/{submission_id}/reject", dependencies=[Depends(require_admin)])
def reject_kyc(
    submission_id: str,
    review_data: KYCReviewRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Reject a KYC submission with a reason.
    
    Per principle 8, only Admin can reject KYC. A reason is required.
    """
    if not review_data.reason:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reason is required for rejection"
        )
    
    submission = db.query(KYCSubmission).filter(
        KYCSubmission.id == submission_id
    ).first()
    
    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="KYC submission not found"
        )
    
    if submission.status != KYCStatus.PENDING_REVIEW:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot reject submission with status: {submission.status.value}"
        )
    
    # Update submission
    submission.status = KYCStatus.REJECTED
    submission.reviewed_by_admin_id = current_user["account_id"]
    submission.review_notes = review_data.reason
    submission.reviewed_at = datetime.now(timezone.utc)
    
    # Update account KYC status
    account = db.query(Account).filter(Account.id == submission.account_id).first()
    if account:
        account.kyc_status = KYCStatus.REJECTED
    
    db.commit()
    
    return {"message": "KYC submission rejected", "submission_id": submission_id}


@router.get("/accounts", dependencies=[Depends(require_admin)])
def get_accounts(db: Session = Depends(get_db)):
    """Return an admin-facing overview of trader and admin accounts."""
    accounts = db.query(Account).all()
    current_prices = get_latest_market_prices(db)

    result = []
    for acc in accounts:
        metrics = calculate_portfolio_metrics(db, acc.id, current_prices)
        order_count = (
            db.query(Order)
            .filter(Order.account_id == acc.id, Order.is_backtest == False)
            .count()
        )
        result.append({
            "id": acc.id,
            "username": acc.username,
            "role": acc.role.value,
            "kyc_status": acc.kyc_status.value,
            "starting_capital": acc.starting_capital,
            "cash_balance": acc.cash_balance,
            "net_worth": metrics.get("net_worth", acc.cash_balance),
            "order_count": order_count,
            "created_at": acc.created_at,
        })

    return result


@router.get("/audit-logs", dependencies=[Depends(require_admin)])
def get_audit_logs(
    account_id: Optional[str] = None,
    ticker: Optional[str] = None,
    from_: Optional[datetime] = None,
    to: Optional[datetime] = None,
    reason_code: Optional[str] = None,
    include_backtest: bool = False,
    db: Session = Depends(get_db),
):
    """Return admin audit logs across accounts, excluding backtest rows by default."""
    query = db.query(OrderEvent)

    if not include_backtest:
        query = query.filter(OrderEvent.is_backtest == False)
    if account_id:
        query = query.join(Order).filter(Order.account_id == account_id)
    if ticker:
        query = query.join(Order).filter(Order.ticker == ticker)
    if from_:
        query = query.filter(OrderEvent.timestamp >= from_)
    if to:
        query = query.filter(OrderEvent.timestamp <= to)
    if reason_code:
        query = query.filter(OrderEvent.reason.contains(reason_code))

    events = query.order_by(OrderEvent.timestamp.asc()).all()
    return [
        {
            "id": event.id,
            "account_id": event.order.account_id,
            "order_id": event.order_id,
            "from_state": event.from_state.value if event.from_state else None,
            "to_state": event.to_state.value,
            "reason": event.reason,
            "timestamp": event.timestamp.isoformat().replace('+00:00', 'Z') if event.timestamp else None,
            "is_backtest": event.is_backtest,
        }
        for event in events
    ]


@router.get("/trade-logs", dependencies=[Depends(require_admin)])
def get_trade_logs(
    account_id: Optional[str] = None,
    ticker: Optional[str] = None,
    from_: Optional[datetime] = None,
    to: Optional[datetime] = None,
    include_backtest: bool = False,
    db: Session = Depends(get_db),
):
    """Return admin trade logs across accounts, excluding backtest rows by default."""
    query = db.query(Fill).join(Order)

    if not include_backtest:
        query = query.filter(Fill.is_backtest == False)
    if account_id:
        query = query.filter(Order.account_id == account_id)
    if ticker:
        query = query.filter(Order.ticker == ticker)
    if from_:
        query = query.filter(Fill.timestamp >= from_)
    if to:
        query = query.filter(Fill.timestamp <= to)

    fills = query.order_by(Fill.timestamp.asc()).all()
    return [
        {
            "id": fill.id,
            "account_id": fill.order.account_id,
            "order_id": fill.order_id,
            "ticker": fill.order.ticker,
            "fill_price": fill.fill_price,
            "fill_qty": fill.fill_qty,
            "fees": fill.fees,
            "timestamp": fill.timestamp.isoformat().replace('+00:00', 'Z') if fill.timestamp else None,
            "is_backtest": fill.is_backtest,
        }
        for fill in fills
    ]


@router.get("/flags", dependencies=[Depends(require_admin)])
def get_compliance_flags(db: Session = Depends(get_db)):
    """Return a combined compliance view of wash-trade flags and KYC issues."""
    flags = []

    # Add KYC review flags.
    submissions = (
        db.query(KYCSubmission)
        .filter(KYCSubmission.auto_check_passed == False)
        .order_by(KYCSubmission.submitted_at.desc())
        .all()
    )
    for submission in submissions:
        flags.append({
            "type": "KYC_REVIEW",
            "submission_id": submission.id,
            "account_id": submission.account_id,
            "reason": submission.auto_check_notes,
            "status": submission.status.value,
        })

    # Add basic wash-trade flags based on reason codes in order events.
    events = (
        db.query(OrderEvent)
        .filter(OrderEvent.reason != None)
        .filter(OrderEvent.reason.contains("WASH_TRADE"))
        .order_by(OrderEvent.timestamp.desc())
        .all()
    )
    for event in events:
        flags.append({
            "type": "WASH_TRADE",
            "order_id": event.order_id,
            "account_id": event.order.account_id,
            "reason": event.reason,
            "timestamp": event.timestamp.isoformat().replace('+00:00', 'Z') if event.timestamp else None,
        })

    return flags


@router.post("/feed/reset", dependencies=[Depends(require_admin)])
def reset_feed(db: Session = Depends(get_db)):
    """Reset the feed simulator to the start of the dataset per Section 9.6."""
    reset_feed_simulator()
    
    # Get updated cache info
    cache_info = get_feed_cache_info()
    
    return {
        "message": "Feed simulator reset to start of dataset",
        "cache_info": cache_info,
        "system_time": datetime.now(timezone.utc).isoformat()
    }


@router.get("/feed/status", dependencies=[Depends(require_admin)])
def get_feed_status(db: Session = Depends(get_db)):
    """Return the current simulator state (using MarketClock)."""
    market_clock = get_market_clock()
    clock_status = market_clock.get_status()
    
    return {
        "market_clock": clock_status,
        "system_time": datetime.now(timezone.utc).isoformat(),
        "running": True
    }


# Market Session Control Endpoints (Section 17.5.2)

@router.post("/session/time", dependencies=[Depends(require_admin)])
def set_session_time(time_data: dict, db: Session = Depends(get_db)):
    """
    Set the simulated session time.
    Admin-only operation.
    
    Request body:
    {
        "date": "2026-07-15",
        "time": "09:15:00"
    }
    """
    try:
        market_clock = get_market_clock()
        
        # Parse date and time
        date_str = time_data.get("date")
        time_str = time_data.get("time")
        
        if not date_str or not time_str:
            raise HTTPException(status_code=400, detail="Both 'date' and 'time' are required")
        
        # Parse datetime
        target_time = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")
        target_time = target_time.replace(tzinfo=timezone.utc)
        
        # Set the time
        market_clock.set_time(target_time)
        
        # Record session in database
        session = MarketSession(
            id=str(uuid.uuid4()),
            start_timestamp=market_clock._start_timestamp,
            current_timestamp=target_time,
            speed_multiplier=market_clock._speed_multiplier,
            market_status=market_clock._market_status
        )
        db.add(session)
        db.commit()
        
        # Broadcast session update via WebSocket
        # TODO: Implement WebSocket broadcast in session update endpoint
        
        return market_clock.get_status()
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date/time format: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error setting session time: {e}")


@router.post("/session/reset", dependencies=[Depends(require_admin)])
def reset_session(db: Session = Depends(get_db)):
    """
    Reset the session to the start of the dataset.
    Admin-only operation.
    """
    try:
        market_clock = get_market_clock()
        market_clock.reset()
        
        # Record session in database
        session = MarketSession(
            id=str(uuid.uuid4()),
            start_timestamp=market_clock._start_timestamp,
            current_timestamp=market_clock._current_timestamp,
            speed_multiplier=market_clock._speed_multiplier,
            market_status=market_clock._market_status
        )
        db.add(session)
        db.commit()
        
        # Broadcast session update via WebSocket
        # TODO: Implement WebSocket broadcast
        
        return market_clock.get_status()
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error resetting session: {e}")


@router.post("/session/speed", dependencies=[Depends(require_admin)])
def set_session_speed(speed_data: dict, db: Session = Depends(get_db)):
    """
    Set the speed multiplier for the session.
    Admin-only operation.
    
    Request body:
    {
        "multiplier": 2  // 1, 2, 5, 12, or 30
    }
    """
    try:
        market_clock = get_market_clock()
        multiplier = speed_data.get("multiplier")
        
        if multiplier is None:
            raise HTTPException(status_code=400, detail="'multiplier' is required")
        
        # Set the speed multiplier
        market_clock.set_speed_multiplier(multiplier)
        
        # Update current session in database
        session = db.query(MarketSession).order_by(MarketSession.created_at.desc()).first()
        if session:
            session.speed_multiplier = multiplier
            session.current_timestamp = market_clock._current_timestamp
            db.commit()
        
        # Broadcast session update via WebSocket
        # TODO: Implement WebSocket broadcast
        
        return market_clock.get_status()
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid speed multiplier: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error setting speed multiplier: {e}")


@router.get("/session/status", dependencies=[Depends(require_admin)])
def get_session_status(db: Session = Depends(get_db)):
    """
    Get the current session status.
    Admin-only operation.
    """
    try:
        market_clock = get_market_clock()
        return market_clock.get_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting session status: {e}")