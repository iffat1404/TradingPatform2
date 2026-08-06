"""
Trade-plan level alerts.

Tells a trader when their own target or stop has been reached. Nothing here ever trades on
their behalf — see level_monitor for why that is deliberate.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user
from app.models.orm import LevelAlert
from app.services.level_monitor import check_levels, serialize_alert
from app.services.market_clock import get_market_clock

router = APIRouter()


@router.get("/alerts")
def get_level_alerts(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Live target/stop breaches on this account's open positions.

    Evaluation happens on request rather than on a background thread, so this both
    re-checks and returns.
    """
    alerts = check_levels(db, current_user["account_id"])
    return {
        "count": len(alerts),
        "unacknowledged": sum(1 for a in alerts if not a.acknowledged),
        "alerts": [serialize_alert(a) for a in alerts],
    }


@router.post("/alerts/{alert_id}/acknowledge")
def acknowledge_alert(
    alert_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Dismiss an alert.

    Acknowledging records that the trader saw it — it does not close the position, and the
    alert stays unresolved until the position actually goes flat. That distinction is what
    lets the journal ask whether a seen stop was acted on.
    """
    alert = (
        db.query(LevelAlert)
        .filter(LevelAlert.id == alert_id, LevelAlert.account_id == current_user["account_id"])
        .first()
    )
    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")

    alert.acknowledged = True
    alert.acknowledged_at = get_market_clock().now()
    db.commit()
    db.refresh(alert)
    return serialize_alert(alert)
