"""
AI Trading Journal engine.

Behavioural patterns (revenge trading, FOMO, overtrading) are detected by deterministic
rules over real order/fill history — GenAI only narrates those findings in coaching
language. This preserves platform principle 1: every trading rule is deterministic code;
GenAI explains and extracts, it never decides.

All Claude calls follow the graceful-degradation contract used across the codebase: never
raise, always return a dict carrying a "generated_by" key of claude | deterministic | error.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, timezone
import uuid

from sqlalchemy.orm import Session

from app.models.orm import JournalEntry, Order, Fill, OrderSide, OrderStatus
from app.models.schemas import ALLOWED_EMOTIONAL_TAGS, ALLOWED_ENTRY_TYPES
from app.services.genai_client import _get_claude_client
from app.services.market_clock import get_market_clock

# Detection thresholds. Deliberately conservative — a flag is a prompt to reflect, not an
# accusation, so we would rather miss a marginal case than cry wolf.
REVENGE_WINDOW_MINUTES = 30
OVERTRADING_ORDERS_PER_DAY = 8
RECENT_ORDER_LIMIT = 200

# Tags a trader self-reports that are worth surfacing back to them in aggregate.
RISK_TAGS = {"fomo", "revenge", "greedy", "fearful", "anxious", "frustrated"}


def _tags_to_list(value: Optional[str]) -> List[str]:
    if not value:
        return []
    return [t for t in (part.strip() for part in value.split(",")) if t]


def _tags_to_str(tags: Optional[List[str]]) -> Optional[str]:
    if not tags:
        return None
    cleaned = []
    for tag in tags:
        normalized = (tag or "").strip().lower()
        if normalized and normalized in ALLOWED_EMOTIONAL_TAGS and normalized not in cleaned:
            cleaned.append(normalized)
    return ",".join(cleaned) if cleaned else None


def serialize_entry(entry: JournalEntry, order: Optional[Order] = None) -> Dict[str, Any]:
    """Shape a JournalEntry for the API, expanding comma-strings back into lists."""
    payload: Dict[str, Any] = {
        "id": entry.id,
        "account_id": entry.account_id,
        "order_id": entry.order_id,
        "ticker": entry.ticker,
        "entry_type": entry.entry_type,
        "rationale": entry.rationale,
        "emotional_tags": _tags_to_list(entry.emotional_tags),
        "ai_feedback": entry.ai_feedback,
        "ai_flags": _tags_to_list(entry.ai_flags),
        "ai_generated_by": entry.ai_generated_by,
        "ai_generated_at": entry.ai_generated_at,
        "created_at": entry.created_at,
        "updated_at": entry.updated_at,
    }

    linked = order if order is not None else entry.order
    if linked is not None:
        payload["order"] = {
            "id": linked.id,
            "ticker": linked.ticker,
            "side": linked.side.value,
            "type": linked.type.value,
            "qty": linked.qty,
            "status": linked.status.value,
            "created_at": linked.created_at,
        }
    else:
        payload["order"] = None

    return payload


def create_entry(db: Session, account_id: str, data) -> JournalEntry:
    """Create a journal entry, resolving ticker from the linked order when present."""
    entry_type = data.entry_type if data.entry_type in ALLOWED_ENTRY_TYPES else "trade_note"

    ticker = (data.ticker or "").strip().upper() or None
    order_id = data.order_id or None

    if order_id:
        # Scope the lookup to this account so a note can never be attached to someone
        # else's order (principle 4: no cross-account data leakage).
        order = (
            db.query(Order)
            .filter(Order.id == order_id, Order.account_id == account_id)
            .first()
        )
        if order is None:
            raise ValueError("Order not found for this account")
        ticker = order.ticker
        entry_type = "trade_note"
    else:
        entry_type = "reflection" if entry_type == "reflection" else entry_type

    entry = JournalEntry(
        id=str(uuid.uuid4()),
        account_id=account_id,
        order_id=order_id,
        ticker=ticker,
        entry_type=entry_type,
        rationale=data.rationale.strip(),
        emotional_tags=_tags_to_str(data.emotional_tags),
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def _fill_pnl_for_order(db: Session, order: Order) -> Optional[float]:
    """
    Rough realized outcome for a single order, used only to spot 'traded right after a
    loss' sequences. Sells credit cash, buys debit it — this is a directional signal for
    pattern detection, not an accounting figure (portfolio_engine owns real P&L).
    """
    fills = db.query(Fill).filter(Fill.order_id == order.id).all()
    if not fills:
        return None
    total = 0.0
    for fill in fills:
        gross = fill.fill_price * fill.fill_qty
        total += (gross - fill.fees) if order.side == OrderSide.SELL else -(gross + fill.fees)
    return total


def detect_patterns(db: Session, account_id: str) -> Dict[str, Any]:
    """
    Deterministic behavioural analysis over this account's real trading history.
    No AI involved — this is the ground truth the coaching layer narrates.
    """
    orders = (
        db.query(Order)
        .filter(Order.account_id == account_id, Order.is_backtest == False)  # noqa: E712
        .order_by(Order.created_at.asc())
        .limit(RECENT_ORDER_LIMIT)
        .all()
    )
    entries = (
        db.query(JournalEntry)
        .filter(JournalEntry.account_id == account_id)
        .order_by(JournalEntry.created_at.asc())
        .all()
    )

    findings: List[Dict[str, Any]] = []

    # --- Revenge trading: a same-ticker order placed soon after a losing exit ---
    revenge_events: List[Dict[str, Any]] = []
    for i, order in enumerate(orders):
        pnl = _fill_pnl_for_order(db, order)
        if pnl is None or pnl >= 0 or order.side != OrderSide.SELL:
            continue
        window_end = order.created_at + timedelta(minutes=REVENGE_WINDOW_MINUTES)
        for follow in orders[i + 1:]:
            if follow.created_at > window_end:
                break
            if follow.ticker == order.ticker and follow.qty >= order.qty:
                revenge_events.append({
                    "ticker": follow.ticker,
                    "after_order_id": order.id,
                    "order_id": follow.id,
                    "minutes_after": round(
                        (follow.created_at - order.created_at).total_seconds() / 60, 1
                    ),
                })
                break

    if revenge_events:
        findings.append({
            "flag": "revenge_trading",
            "label": "Possible revenge trading",
            "count": len(revenge_events),
            "detail": (
                f"{len(revenge_events)} order(s) re-entered the same ticker at equal or larger "
                f"size within {REVENGE_WINDOW_MINUTES} minutes of a losing exit."
            ),
            "examples": revenge_events[:3],
        })

    # --- Overtrading: too many orders inside one simulated session day ---
    per_day: Dict[str, int] = {}
    for order in orders:
        key = order.created_at.strftime("%Y-%m-%d")
        per_day[key] = per_day.get(key, 0) + 1
    heavy_days = {day: n for day, n in per_day.items() if n >= OVERTRADING_ORDERS_PER_DAY}
    if heavy_days:
        findings.append({
            "flag": "overtrading",
            "label": "High order frequency",
            "count": len(heavy_days),
            "detail": (
                f"{len(heavy_days)} day(s) with {OVERTRADING_ORDERS_PER_DAY}+ orders. "
                "High frequency often reflects reacting to noise rather than a plan."
            ),
            "examples": [{"date": d, "orders": n} for d, n in list(heavy_days.items())[:3]],
        })

    # --- Self-reported risk emotions ---
    tag_counts: Dict[str, int] = {}
    for entry in entries:
        for tag in _tags_to_list(entry.emotional_tags):
            tag_counts[tag] = tag_counts.get(tag, 0) + 1

    flagged_tag_counts = {t: c for t, c in tag_counts.items() if t in RISK_TAGS}
    if flagged_tag_counts:
        top_tag = max(flagged_tag_counts.items(), key=lambda kv: kv[1])
        findings.append({
            "flag": f"emotion_{top_tag[0]}",
            "label": f"Recurring '{top_tag[0]}' state",
            "count": top_tag[1],
            "detail": (
                f"You tagged {top_tag[1]} entr{'y' if top_tag[1] == 1 else 'ies'} as "
                f"'{top_tag[0]}'. Naming it is the first step to trading around it."
            ),
            "examples": [{"tag": t, "count": c} for t, c in flagged_tag_counts.items()],
        })

    # --- Journaling discipline: are trades actually being reflected on? ---
    filled_orders = [o for o in orders if o.status == OrderStatus.FILLED]
    journaled_order_ids = {e.order_id for e in entries if e.order_id}
    unjournaled = [o for o in filled_orders if o.id not in journaled_order_ids]
    coverage = (
        round(100.0 * (len(filled_orders) - len(unjournaled)) / len(filled_orders), 1)
        if filled_orders
        else 0.0
    )

    return {
        "entry_count": len(entries),
        "order_count": len(orders),
        "filled_order_count": len(filled_orders),
        "journaled_coverage_pct": coverage,
        "unjournaled_trade_count": len(unjournaled),
        "tag_counts": tag_counts,
        "findings": findings,
        "flags": [f["flag"] for f in findings],
    }


def _deterministic_insight_text(stats: Dict[str, Any]) -> str:
    if stats["entry_count"] == 0:
        return (
            "No journal entries yet. Log the reasoning behind your next trade — even one "
            "line — and this coach starts spotting patterns in your decisions."
        )
    parts = [
        f"You've logged {stats['entry_count']} entr"
        f"{'y' if stats['entry_count'] == 1 else 'ies'} across "
        f"{stats['filled_order_count']} filled trade"
        f"{'' if stats['filled_order_count'] == 1 else 's'} "
        f"({stats['journaled_coverage_pct']}% of your fills are journaled)."
    ]
    if stats["findings"]:
        parts.append("Patterns worth watching: " + "; ".join(f["detail"] for f in stats["findings"]))
    else:
        parts.append("No risk patterns detected in your recent activity — discipline is holding.")
    if stats["unjournaled_trade_count"]:
        parts.append(
            f"{stats['unjournaled_trade_count']} filled trade"
            f"{'' if stats['unjournaled_trade_count'] == 1 else 's'} still "
            "have no note attached."
        )
    return " ".join(parts)


def generate_insights(db: Session, account_id: str) -> Dict[str, Any]:
    """Deterministic stats first; Claude only rewrites them as coaching prose."""
    stats = detect_patterns(db, account_id)
    client = _get_claude_client()

    if client and stats["entry_count"] > 0:
        try:
            findings_text = "\n".join(f"- {f['label']}: {f['detail']}" for f in stats["findings"]) or "- None detected"
            response = client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=512,
                messages=[{
                    "role": "user",
                    "content": f"""You are a trading performance coach reviewing a paper-trading student's journal.

Journal entries: {stats['entry_count']}
Filled trades: {stats['filled_order_count']}
Journaling coverage: {stats['journaled_coverage_pct']}% of fills have a note
Self-reported emotion tags: {stats['tag_counts'] or 'none'}

Detected behavioural patterns (computed from their real order history):
{findings_text}

Write 3-4 sentences of direct, actionable coaching. Reference the specific patterns above.
Be constructive and concrete about what to change next session — no generic platitudes,
no disclaimers, no restating the numbers back verbatim.""",
                }],
            )
            narrative = response.content[0].text if response.content else ""
            if narrative:
                return {**stats, "narrative": narrative, "generated_by": "claude"}
        except Exception as e:
            print(f"Claude journal insights failed: {e}")
            # Fall through to deterministic narrative

    try:
        return {**stats, "narrative": _deterministic_insight_text(stats), "generated_by": "deterministic"}
    except Exception:
        return {
            "entry_count": 0,
            "order_count": 0,
            "filled_order_count": 0,
            "journaled_coverage_pct": 0.0,
            "unjournaled_trade_count": 0,
            "tag_counts": {},
            "findings": [],
            "flags": [],
            "narrative": None,
            "error": "Insight generation failed",
            "generated_by": "error",
        }


def _entry_flags(entry: JournalEntry, trade_pnl: Optional[float]) -> List[str]:
    """Deterministic per-entry flags from the trader's own tags plus the trade outcome."""
    flags: List[str] = []
    tags = _tags_to_list(entry.emotional_tags)
    if "fomo" in tags:
        flags.append("possible_fomo")
    if "revenge" in tags:
        flags.append("possible_revenge_trade")
    if any(t in tags for t in ("anxious", "fearful", "frustrated")):
        flags.append("elevated_stress")
    if "greedy" in tags:
        flags.append("size_discipline_risk")
    if trade_pnl is not None and trade_pnl < 0 and "disciplined" not in tags:
        flags.append("losing_trade_review")
    return flags


def generate_entry_feedback(db: Session, entry: JournalEntry, regenerate: bool = False) -> Dict[str, Any]:
    """
    On-demand coaching for a single entry. Cached on the row so repeat views are free;
    pass regenerate=True to force a fresh call.
    """
    if entry.ai_feedback and not regenerate:
        return {
            "feedback": entry.ai_feedback,
            "flags": _tags_to_list(entry.ai_flags),
            "generated_by": entry.ai_generated_by or "cached",
            "cached": True,
        }

    order = entry.order
    trade_pnl = _fill_pnl_for_order(db, order) if order is not None else None
    flags = _entry_flags(entry, trade_pnl)
    tags = _tags_to_list(entry.emotional_tags)

    trade_context = "No trade linked — this is a standalone reflection."
    if order is not None:
        trade_context = (
            f"Linked trade: {order.side.value.upper()} {order.qty} {order.ticker} "
            f"({order.type.value}), status {order.status.value}."
        )
        if trade_pnl is not None:
            trade_context += f" Approximate cash impact: {trade_pnl:,.2f}."

    client = _get_claude_client()
    feedback: Optional[str] = None
    generated_by = "deterministic"

    if client:
        try:
            response = client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=384,
                messages=[{
                    "role": "user",
                    "content": f"""You are a trading performance coach responding to one journal entry.

{trade_context}
Trader's self-reported emotions: {', '.join(tags) if tags else 'none recorded'}
Trader's written rationale: "{entry.rationale}"
Rule-based flags already computed: {', '.join(flags) if flags else 'none'}

Write 2-3 sentences of specific, actionable feedback on their decision process — not the
outcome. If the flags suggest an emotional bias, name it plainly and give one concrete
habit to counter it next time. Be direct and supportive; no disclaimers.""",
                }],
            )
            text = response.content[0].text if response.content else ""
            if text:
                feedback = text
                generated_by = "claude"
        except Exception as e:
            print(f"Claude journal entry feedback failed: {e}")
            # Fall through to deterministic feedback

    if feedback is None:
        try:
            bits = []
            if "possible_fomo" in flags:
                bits.append(
                    "You flagged FOMO on this one — before the next entry, write the level you "
                    "wanted to buy at *before* looking at the price. If it has already run past it, skip it."
                )
            if "possible_revenge_trade" in flags:
                bits.append(
                    "This entry is tagged as revenge. A hard rule helps here: no new order in the "
                    "same name for 30 minutes after a losing exit."
                )
            if "elevated_stress" in flags:
                bits.append(
                    "You were trading under stress. Size down when that happens — smaller positions "
                    "keep the decision reversible."
                )
            if "size_discipline_risk" in flags:
                bits.append(
                    "Greed was in play. Pre-committing to a fixed position size removes the "
                    "in-the-moment sizing decision entirely."
                )
            if "losing_trade_review" in flags:
                bits.append(
                    "This trade lost money. Separate the decision from the result: was the process "
                    "sound and the outcome unlucky, or was the process itself off?"
                )
            if not bits:
                bits.append(
                    "No risk signals on this entry — the rationale is recorded and the emotional "
                    "read looks steady. Keep logging at this level of detail; consistency is what "
                    "makes the patterns visible."
                )
            feedback = " ".join(bits)
        except Exception:
            return {"feedback": None, "flags": [], "error": "Feedback generation failed", "generated_by": "error"}

    entry.ai_feedback = feedback
    entry.ai_flags = ",".join(flags) if flags else None
    entry.ai_generated_by = generated_by
    entry.ai_generated_at = get_market_clock().now()
    db.commit()
    db.refresh(entry)

    return {"feedback": feedback, "flags": flags, "generated_by": generated_by, "cached": False}
