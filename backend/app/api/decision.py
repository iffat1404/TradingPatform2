"""
Decision Intelligence API.

Pre-trade decision scoring and stored decision snapshots. Everything here is advisory —
no endpoint in this module can prevent an order from being placed.
"""
import json
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user
from app.models.orm import TradeDecision
from app.models.schemas import DecisionPreviewRequest
from app.services.decision_engine import evaluate_trade
from app.services.journal_engine import detect_patterns, explain_decision

router = APIRouter()


def _coverage(db: Session, account_id: str) -> Optional[float]:
    """Journaling coverage feeds the discipline factor; never let it break scoring."""
    try:
        return detect_patterns(db, account_id).get("journaled_coverage_pct")
    except Exception:
        return None


def _serialize(decision: TradeDecision) -> dict:
    payload = {
        "id": decision.id,
        "order_id": decision.order_id,
        "ticker": decision.ticker,
        "risk_score": decision.risk_score,
        "decision_quality_score": decision.decision_quality_score,
        "grade": decision.grade,
        "created_at": decision.created_at,
    }
    try:
        factors = json.loads(decision.factors_json or "{}")
        payload["risk_factors"] = factors.get("risk_factors", [])
        payload["quality_factors"] = factors.get("quality_factors", [])
    except Exception:
        payload["risk_factors"] = []
        payload["quality_factors"] = []
    try:
        payload["context"] = json.loads(decision.context_json or "{}")
    except Exception:
        payload["context"] = {}
    return payload


def persist_decision(db: Session, account_id: str, order_id: Optional[str], scores: dict) -> Optional[TradeDecision]:
    """
    Store a decision snapshot. Shared with the order-creation path.
    Returns None on failure — scoring must never break order entry.
    """
    try:
        decision = TradeDecision(
            id=str(uuid.uuid4()),
            account_id=account_id,
            order_id=order_id,
            ticker=scores["context"]["ticker"],
            risk_score=scores["risk_score"],
            decision_quality_score=scores["decision_quality_score"],
            grade=scores["grade"],
            factors_json=json.dumps({
                "risk_factors": scores["risk_factors"],
                "quality_factors": scores["quality_factors"],
            }),
            context_json=json.dumps(scores["context"], default=str),
        )
        db.add(decision)
        db.commit()
        db.refresh(decision)
        return decision
    except Exception as e:  # pragma: no cover - defensive
        print(f"Failed to persist trade decision: {e}")
        db.rollback()
        return None


@router.post("/preview")
def preview_decision(
    payload: DecisionPreviewRequest,
    explain: bool = Query(False, description="Also generate AI coaching prose"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Score a hypothetical trade without executing anything.

    Deliberately a separate endpoint from POST /api/orders: that route is bound to
    OrderResponse, which would strip any extra fields, and it raises before returning when
    validation rejects.
    """
    scores = evaluate_trade(
        db,
        account_id=current_user["account_id"],
        ticker=payload.ticker,
        side=payload.side,
        qty=payload.qty,
        price=payload.price,
        target_price=payload.target_price,
        stop_loss=payload.stop_loss,
        journaled_coverage_pct=_coverage(db, current_user["account_id"]),
    )

    # AI narration is opt-in so the live-updating ticket panel doesn't call the model on
    # every keystroke.
    if explain:
        scores["explanation"] = explain_decision(scores)

    return scores


@router.get("/history")
def decision_history(
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Past decision scores for this account, newest first."""
    rows = (
        db.query(TradeDecision)
        .filter(TradeDecision.account_id == current_user["account_id"])
        .order_by(TradeDecision.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": d.id,
            "order_id": d.order_id,
            "ticker": d.ticker,
            "risk_score": d.risk_score,
            "decision_quality_score": d.decision_quality_score,
            "grade": d.grade,
            "created_at": d.created_at,
        }
        for d in rows
    ]


@router.get("/order/{order_id}")
def decision_for_order(
    order_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """The stored decision snapshot for one order."""
    decision = (
        db.query(TradeDecision)
        .filter(
            TradeDecision.order_id == order_id,
            TradeDecision.account_id == current_user["account_id"],
        )
        .first()
    )
    if not decision:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No decision snapshot recorded for this order",
        )
    return _serialize(decision)
