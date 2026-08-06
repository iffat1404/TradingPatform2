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

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.orm import (
    JournalEntry, Order, OrderEvent, Fill, OrderSide, OrderStatus,
    NewsArticle, PriceHistoryDaily, PriceHistoryMinute, LevelAlert,
)
from app.models.schemas import ALLOWED_EMOTIONAL_TAGS, ALLOWED_ENTRY_TYPES
from app.services.analytics_engine import get_recent_daily_bars
from app.services.genai_client import _get_claude_client, GENAI_MODEL, capped_max_tokens, provider_label
from app.services.market_clock import get_market_clock

# Detection thresholds. Deliberately conservative — a flag is a prompt to reflect, not an
# accusation, so we would rather miss a marginal case than cry wolf.
REVENGE_WINDOW_MINUTES = 30
OVERTRADING_ORDERS_PER_DAY = 8
RECENT_ORDER_LIMIT = 200
CONSECUTIVE_LOSS_THRESHOLD = 2   # losing exits in a row before a size increase counts
CHASE_RUNUP_PCT = 8.0            # rally size that makes a subsequent buy a "chase"
CHASE_LOOKBACK_BARS = 5          # sessions the rally is measured over
STOP_TINKER_THRESHOLD = 3        # plan edits on one order before it reads as tinkering
STOP_ACTION_GRACE_MINUTES = 60   # how long after a stop alert an exit still counts as acting on it

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
        "is_auto": bool(getattr(entry, "is_auto", False)),
        # Auto-logged entries start blank; empty and NULL both mean "not yet annotated".
        "needs_annotation": not (entry.rationale or "").strip(),
        "ai_feedback": entry.ai_feedback,
        "ai_flags": _tags_to_list(entry.ai_flags),
        "ai_generated_by": entry.ai_generated_by,
        "ai_generated_at": entry.ai_generated_at,
        "created_at": entry.created_at,
        "updated_at": entry.updated_at,
    }

    # The headline the trader cited, if any — the UI shows it inline on the entry.
    cited = entry.news_article
    payload["news_article"] = None if cited is None else {
        "id": cited.id,
        "ticker": cited.ticker,
        "title": cited.title,
        "date": cited.date.strftime("%Y-%m-%d") if cited.date else None,
        "sentiment_label": cited.sentiment_label,
        "relevance_score": round(cited.relevance_score, 2),
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
        news_article_id=getattr(data, "news_article_id", None) or None,
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
    # Take the most RECENT window, then restore chronological order for sequence analysis.
    # (Ordering ascending before limiting would analyse the oldest orders forever.)
    orders = list(reversed(
        db.query(Order)
        .filter(Order.account_id == account_id, Order.is_backtest == False)  # noqa: E712
        .order_by(Order.created_at.desc())
        .limit(RECENT_ORDER_LIMIT)
        .all()
    ))
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

    # --- Sizing up after consecutive losses ---
    # Classic tilt: after losses stack up, the next bet gets bigger to "win it back".
    sizeup_events: List[Dict[str, Any]] = []
    losing_streak = 0
    last_qty: Optional[int] = None
    for order in orders:
        pnl = _fill_pnl_for_order(db, order)
        if losing_streak >= CONSECUTIVE_LOSS_THRESHOLD and last_qty and order.qty > last_qty:
            sizeup_events.append({
                "ticker": order.ticker,
                "order_id": order.id,
                "qty": order.qty,
                "previous_qty": last_qty,
                "after_losses": losing_streak,
            })
            losing_streak = 0
        if pnl is not None and order.side == OrderSide.SELL:
            losing_streak = losing_streak + 1 if pnl < 0 else 0
        if order.qty:
            last_qty = order.qty

    if sizeup_events:
        findings.append({
            "flag": "size_up_after_losses",
            "label": "Position size grows after losses",
            "count": len(sizeup_events),
            "detail": (
                f"{len(sizeup_events)} time(s) you increased order size straight after "
                f"{CONSECUTIVE_LOSS_THRESHOLD}+ consecutive losing exits. Raising risk to "
                "recover a loss is how a bad day becomes a bad week."
            ),
            "examples": sizeup_events[:3],
        })

    # --- Exiting winners before the stated target ---
    # Only measurable when the trader actually recorded a target on the entry order.
    early_exits: List[Dict[str, Any]] = []
    for order in orders:
        if order.side != OrderSide.SELL or order.status != OrderStatus.FILLED:
            continue
        pnl = _fill_pnl_for_order(db, order)
        if pnl is None or pnl <= 0:
            continue
        entry_order = next(
            (o for o in orders
             if o.ticker == order.ticker
             and o.side == OrderSide.BUY
             and o.target_price
             and o.created_at < order.created_at),
            None,
        )
        if not entry_order:
            continue
        exit_fill = db.query(Fill).filter(Fill.order_id == order.id).first()
        if exit_fill and exit_fill.fill_price < entry_order.target_price:
            shortfall = entry_order.target_price - exit_fill.fill_price
            early_exits.append({
                "ticker": order.ticker,
                "order_id": order.id,
                "exit_price": round(exit_fill.fill_price, 2),
                "target_price": round(entry_order.target_price, 2),
                "left_on_table": round(shortfall * exit_fill.fill_qty, 2),
            })

    if early_exits:
        total_left = sum(e["left_on_table"] for e in early_exits)
        findings.append({
            "flag": "exits_winners_early",
            "label": "Winners closed before target",
            "count": len(early_exits),
            "detail": (
                f"{len(early_exits)} profitable trade(s) were closed short of your own "
                f"target, leaving roughly ${total_left:,.0f} on the table. Cutting winners "
                "early while letting losers run is what turns a positive edge negative."
            ),
            "examples": early_exits[:3],
        })

    # --- Chasing: buying straight after a sharp rally ---
    chase_events: List[Dict[str, Any]] = []
    for order in orders:
        if order.side != OrderSide.BUY:
            continue
        try:
            bars = get_recent_daily_bars(db, order.ticker, limit=CHASE_LOOKBACK_BARS + 1)
        except Exception:
            continue
        if len(bars) < 2 or not bars[0].close:
            continue
        run_up_pct = ((bars[-1].close - bars[0].close) / bars[0].close) * 100.0
        if run_up_pct >= CHASE_RUNUP_PCT:
            chase_events.append({
                "ticker": order.ticker,
                "order_id": order.id,
                "run_up_pct": round(run_up_pct, 1),
                "lookback_days": CHASE_LOOKBACK_BARS,
            })

    if chase_events:
        by_ticker = sorted({e["ticker"] for e in chase_events})
        findings.append({
            "flag": "chasing_rallies",
            "label": "Buying into sharp rallies",
            "count": len(chase_events),
            "detail": (
                f"{len(chase_events)} buy(s) landed after a {CHASE_RUNUP_PCT:.0f}%+ run-up "
                f"over {CHASE_LOOKBACK_BARS} sessions ({', '.join(by_ticker)}). Entering "
                "post-rally leaves you buying other people's profit-taking."
            ),
            "examples": chase_events[:3],
        })

    # --- Adjusting the trade plan repeatedly on one order ---
    # Each change is recorded as a LEVELS_UPDATED order event by the levels endpoint.
    tinker_rows = (
        db.query(OrderEvent.order_id, func.count(OrderEvent.id))
        .join(Order, Order.id == OrderEvent.order_id)
        .filter(
            Order.account_id == account_id,
            OrderEvent.reason.like("LEVELS_UPDATED%"),
        )
        .group_by(OrderEvent.order_id)
        .all()
    )
    tinkered = [{"order_id": oid, "changes": n} for oid, n in tinker_rows if n >= STOP_TINKER_THRESHOLD]
    if tinkered:
        findings.append({
            "flag": "stop_loss_tinkering",
            "label": "Trade plan repeatedly moved",
            "count": len(tinkered),
            "detail": (
                f"{len(tinkered)} order(s) had their target or stop changed "
                f"{STOP_TINKER_THRESHOLD}+ times. Widening a stop mid-trade converts a "
                "planned loss into an open-ended one."
            ),
            "examples": tinkered[:3],
        })

    # --- Stop reached, but the position was not closed ---
    # The sharpest version of "did you follow your own plan": the level you set was hit,
    # you were told, and the holding is still open.
    stop_alerts = (
        db.query(LevelAlert)
        .filter(
            LevelAlert.account_id == account_id,
            LevelAlert.kind == "stop",
        )
        .order_by(LevelAlert.created_at.asc())
        .all()
    )

    ignored_stops = []
    for alert in stop_alerts:
        # Did a closing order follow within the grace window?
        closing_side = OrderSide.SELL if alert.signed_qty > 0 else OrderSide.BUY
        window_end = alert.created_at + timedelta(minutes=STOP_ACTION_GRACE_MINUTES)
        acted = any(
            o.ticker == alert.ticker
            and o.side == closing_side
            and alert.created_at <= o.created_at <= window_end
            for o in orders
        )
        if not acted:
            ignored_stops.append({
                "ticker": alert.ticker,
                "level_price": round(alert.level_price, 2),
                "trigger_price": round(alert.trigger_price, 2),
                "acknowledged": bool(alert.acknowledged),
                "still_open": not alert.resolved,
            })

    if ignored_stops:
        seen_count = sum(1 for s in ignored_stops if s["acknowledged"])
        findings.append({
            "flag": "ignored_own_stop",
            "label": "Stop hit but not acted on",
            "count": len(ignored_stops),
            "detail": (
                f"{len(ignored_stops)} position(s) breached the stop you set and were not "
                f"closed within {STOP_ACTION_GRACE_MINUTES} minutes"
                + (f" ({seen_count} after you had seen the alert)" if seen_count else "")
                + ". A stop you talk yourself out of is not a stop."
            ),
            "examples": ignored_stops[:3],
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
                model=GENAI_MODEL,
                max_tokens=capped_max_tokens(512),
                messages=[{
                    "role": "user",
                    "content": f"""You are a trading performance coach reviewing a paper-trading student's journal.

Journal entries: {stats['entry_count']}
Filled trades: {stats['filled_order_count']}
Journaling coverage: {stats['journaled_coverage_pct']}% of fills have a note
Self-reported emotion tags: {stats['tag_counts'] or 'none'}

Detected behavioural patterns (computed from their real order history):
{findings_text}

Write 3-4 sentences of direct coaching about their PROCESS AND HABITS.

Hard rules:
- NEVER give market or timing advice. Do not say when to buy, sell, hold, exit, or wait
  for a pullback, and never predict what any price will do. You are coaching how they
  decide, not what to trade.
- Every claim must trace to a pattern listed above. Cite its actual number or ticker.
- Prescribe a habit they control before the trade — writing the exit down in advance,
  capping orders per day, sizing rules — not a market action.
- No platitudes, no disclaimers, no restating the stats verbatim.

Example of the register wanted: "You closed a winner short of a target you had already
written down — that is a rule you set and then overrode, so next session decide the exit
before entry and treat it as fixed."
""",
                }],
            )
            narrative = response.content[0].text if response.content else ""
            if narrative:
                return {**stats, "narrative": narrative, "generated_by": provider_label()}
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
                model=GENAI_MODEL,
                max_tokens=capped_max_tokens(384),
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
                generated_by = provider_label()
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


def auto_journal_fill(db: Session, order: Order, fill: Fill) -> Optional[JournalEntry]:
    """
    Create a blank-rationale journal entry the moment a trade fills.

    Called from order_engine.fill_order inside the caller's transaction, so this stays
    strictly deterministic — no AI, no network. The trader is prompted to add their
    reasoning afterwards, and the AI reflection is generated on demand via /analyze.

    Never raises: a journaling problem must not be able to break order execution.
    """
    try:
        # Idempotency — there is no unique constraint on order_id, so guard here.
        existing = (
            db.query(JournalEntry)
            .filter(JournalEntry.order_id == order.id)
            .first()
        )
        if existing:
            return existing

        entry = JournalEntry(
            id=str(uuid.uuid4()),
            account_id=order.account_id,
            order_id=order.id,
            ticker=order.ticker,
            entry_type="trade_note",
            # Empty rather than NULL: pre-existing databases still have NOT NULL on this
            # column (SQLite cannot drop that without a table rebuild). Both are treated
            # as "needs annotation" everywhere downstream.
            rationale="",
            is_auto=True,
        )
        db.add(entry)
        # No commit — fill_order runs inside the caller's transaction and it commits.
        return entry
    except Exception as e:  # pragma: no cover - defensive
        print(f"Auto-journal failed for order {getattr(order, 'id', '?')}: {e}")
        return None


def _deterministic_decision_text(scores: Dict[str, Any]) -> str:
    """Plain-language summary of a decision score, used when no AI is configured."""
    risk = scores.get("risk_score", 0)
    quality = scores.get("decision_quality_score", 0)

    # Lead with whatever is most out of line: the weakest process factor and the biggest risk.
    quality_factors = sorted(scores.get("quality_factors", []), key=lambda f: f["score"])
    risk_factors = sorted(scores.get("risk_factors", []), key=lambda f: -f["score"])

    bits = [f"Risk {risk:.0f}/100, decision quality {quality:.0f}/100 (grade {scores.get('grade', '?')})."]
    if quality_factors:
        bits.append(quality_factors[0]["note"])
    if risk_factors:
        bits.append(risk_factors[0]["note"])
    return " ".join(bits)


def explain_decision(scores: Dict[str, Any]) -> Dict[str, Any]:
    """
    Turn a deterministic score breakdown into short coaching prose.

    The model never decides anything — it is handed the already-computed factors and asked
    to explain them. Falls back to deterministic text whenever AI is unavailable.
    """
    client = _get_claude_client()

    if client:
        try:
            ctx = scores.get("context", {})
            risk_lines = "\n".join(
                f"- {f['label']}: {f['score']:.0f}/100 — {f['note']}"
                for f in scores.get("risk_factors", [])
            )
            quality_lines = "\n".join(
                f"- {f['label']}: {f['score']:.0f}/100 — {f['note']}"
                for f in scores.get("quality_factors", [])
            )
            response = client.messages.create(
                model=GENAI_MODEL,
                max_tokens=capped_max_tokens(384),
                messages=[{
                    "role": "user",
                    "content": f"""You are a trading discipline coach. A trader is about to place this order:

{ctx.get('side', '?').upper()} {ctx.get('qty')} {ctx.get('ticker')} around ${ctx.get('entry_price') or 0:.2f}
Target: {ctx.get('target_price') or 'not set'}   Stop: {ctx.get('stop_loss') or 'not set'}

A deterministic engine scored the DECISION (not the stock):
Risk {scores.get('risk_score')}/100 (higher = more risk taken on)
Decision quality {scores.get('decision_quality_score')}/100 (higher = better process)

Risk factors:
{risk_lines}

Process factors:
{quality_lines}

Write 2-3 sentences of direct coaching about the QUALITY OF THIS DECISION.
Rules:
- Never say whether to buy or sell, and never predict the price.
- Reference the specific weakest factors above.
- Speak to the trader as "you". No preamble, no bullet points.""",
                }],
            )
            text = response.content[0].text if response.content else ""
            if text and text.strip():
                return {"explanation": text.strip(), "generated_by": provider_label()}
        except Exception as e:
            print(f"Decision explanation failed: {e}")
            # Fall through to deterministic text

    try:
        return {
            "explanation": _deterministic_decision_text(scores),
            "generated_by": "deterministic",
        }
    except Exception:
        return {"explanation": None, "error": "Explanation failed", "generated_by": "error"}


# --------------------------------------------------------------------- news thesis review

# How far the price must move before we call it a real move rather than noise.
NEWS_MOVE_FLAT_PCT = 0.5
# Another headline only counts as "missed" if it is materially about the ticker.
MISSED_RELEVANCE_FLOOR = 0.3


def _label_direction(label: Optional[str]) -> int:
    """Bearish/Bullish label -> -1 / 0 / +1."""
    return {
        "Bearish": -1, "Somewhat-Bearish": -1,
        "Neutral": 0,
        "Somewhat-Bullish": 1, "Bullish": 1,
    }.get(label or "", 0)


def _session_close(db: Session, ticker: str, day: datetime) -> Optional[float]:
    """
    Closing price for a ticker on one session.

    Prefers the last minute bar of the day, because the minute dataset spans the whole news
    window (2026-06-30 to 2026-08-29) while the daily dataset stops at 2026-07-10. Falls
    back to the daily bar for dates only the daily set covers.
    """
    day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)

    last_minute = (
        db.query(PriceHistoryMinute)
        .filter(
            PriceHistoryMinute.ticker == ticker,
            PriceHistoryMinute.timestamp >= day_start,
            PriceHistoryMinute.timestamp < day_end,
        )
        .order_by(PriceHistoryMinute.timestamp.desc())
        .first()
    )
    if last_minute:
        return last_minute.close

    daily = (
        db.query(PriceHistoryDaily)
        .filter(PriceHistoryDaily.ticker == ticker, PriceHistoryDaily.date == day_start)
        .first()
    )
    return daily.close if daily else None


def _next_session_close(db: Session, ticker: str, after: datetime, max_lookahead_days: int = 5):
    """
    Close of the next session that actually has data, and its date.

    Walks forward a few days so a weekend or gap in the feed does not read as "no data".
    """
    day_start = after.replace(hour=0, minute=0, second=0, microsecond=0)
    for offset in range(1, max_lookahead_days + 1):
        candidate = day_start + timedelta(days=offset)
        close = _session_close(db, ticker, candidate)
        if close is not None:
            return close, candidate
    return None, None


def review_news_thesis(db: Session, entry: JournalEntry) -> Optional[Dict[str, Any]]:
    """
    Did the headline this entry cites actually move the price - and what else was published
    that day that the trader ignored?

    Fully deterministic. Compares the cited story's sentiment direction against the ticker's
    realised move from the news date to the next session, then looks for same-day stories on
    the same ticker that were *more* relevant or pointed the other way.

    Returns None when the entry cites no headline.
    """
    article = entry.news_article
    if article is None:
        return None

    ticker = article.ticker
    news_date = article.date

    # Realised move: this session's close -> the next session that has data.
    base_close = _session_close(db, ticker, news_date)
    next_close, next_date = _next_session_close(db, ticker, news_date)

    move_pct = None
    if base_close and next_close:
        move_pct = ((next_close - base_close) / base_close) * 100.0

    expected = _label_direction(article.sentiment_label)

    if move_pct is None:
        verdict = "unknown"
        verdict_text = "No next-session price data to judge this against yet."
    elif abs(move_pct) < NEWS_MOVE_FLAT_PCT:
        verdict = "flat"
        verdict_text = (
            f"{ticker} barely moved ({move_pct:+.2f}%) - this story did not drive the price "
            "either way."
        )
    else:
        actual = 1 if move_pct > 0 else -1
        if expected == 0:
            verdict = "no_signal"
            verdict_text = (
                f"The story was scored Neutral, yet {ticker} moved {move_pct:+.2f}%. "
                "Something other than this headline drove the price."
            )
        elif actual == expected:
            verdict = "confirmed"
            verdict_text = (
                f"The {article.sentiment_label} read was borne out - {ticker} moved "
                f"{move_pct:+.2f}% into the next session."
            )
        else:
            verdict = "contradicted"
            verdict_text = (
                f"The story read {article.sentiment_label}, but {ticker} moved "
                f"{move_pct:+.2f}% - the price went the other way."
            )

    # What else was published on that ticker that day, ranked by relevance.
    same_day = (
        db.query(NewsArticle)
        .filter(
            NewsArticle.ticker == ticker,
            NewsArticle.date == news_date,
            NewsArticle.id != article.id,
        )
        .order_by(NewsArticle.relevance_score.desc())
        .all()
    )

    missed = []
    for other in same_day:
        if other.relevance_score < MISSED_RELEVANCE_FLOOR:
            continue
        other_dir = _label_direction(other.sentiment_label)
        # Worth flagging if it contradicted the cited story, or was simply a bigger story.
        contradicts = other_dir != 0 and expected != 0 and other_dir != expected
        more_relevant = other.relevance_score > article.relevance_score
        if contradicts or more_relevant:
            missed.append({
                "title": other.title,
                "sentiment_label": other.sentiment_label,
                "relevance_score": round(other.relevance_score, 2),
                "why": "points the other way" if contradicts else "was a bigger story for this ticker",
            })

    tunnel_vision = any(m["why"] == "points the other way" for m in missed[:3])

    return {
        "article": {
            "id": article.id,
            "ticker": ticker,
            "title": article.title,
            "date": news_date.strftime("%Y-%m-%d") if news_date else None,
            "sentiment_label": article.sentiment_label,
            "relevance_score": round(article.relevance_score, 2),
        },
        "expected_direction": expected,
        "actual_move_pct": round(move_pct, 2) if move_pct is not None else None,
        "measured_to": next_date.strftime("%Y-%m-%d") if next_date else None,
        "verdict": verdict,
        "verdict_text": verdict_text,
        "same_day_article_count": len(same_day),
        "missed": missed[:3],
        "tunnel_vision": tunnel_vision,
        "lesson": (
            "You anchored on one story while the day's coverage disagreed - scan the whole "
            "tape for a ticker before sizing a view."
            if tunnel_vision else
            "Keep pairing each trade with the specific story behind it; that is what makes "
            "this reviewable at all."
        ),
    }


def explain_news_thesis(db: Session, entry: JournalEntry) -> Dict[str, Any]:
    """
    Coach the trader on their news thesis.

    The verdict and the "what you missed" list are computed deterministically by
    review_news_thesis; GenAI only turns them into feedback. Never raises.
    """
    review = review_news_thesis(db, entry)
    if review is None:
        return {"review": None, "coaching": None, "generated_by": "deterministic"}

    client = _get_claude_client()
    if client:
        try:
            missed_lines = [
                "- [{label}, relevance {rel}] {title} ({why})".format(
                    label=m["sentiment_label"], rel=m["relevance_score"],
                    title=m["title"], why=m["why"],
                )
                for m in review["missed"]
            ]
            missed_text = "\n".join(missed_lines) or "- nothing materially contradictory"

            prompt = (
                "You are a trading coach reviewing whether a trader read the news correctly.\n\n"
                "They traded {ticker} citing this story:\n"
                '"{title}"\n'
                "Scored: {label} (relevance {rel})\n\n"
                "WHAT ACTUALLY HAPPENED (computed, not opinion):\n{verdict}\n\n"
                "OTHER {ticker} STORIES THAT SAME DAY THEY DID NOT CITE:\n{missed}\n\n"
                "Write 2-3 sentences of coaching about their NEWS READING PROCESS.\n"
                "Rules:\n"
                "- Never say whether to buy or sell, and never predict future prices.\n"
                "- If the price contradicted their read, say so plainly and without sarcasm.\n"
                "- If they ignored a bigger or opposing story, name it.\n"
                "- End with one concrete habit for tomorrow.\n"
                '- Address them as "you". No preamble.'
            ).format(
                ticker=review["article"]["ticker"],
                title=review["article"]["title"],
                label=review["article"]["sentiment_label"],
                rel=review["article"]["relevance_score"],
                verdict=review["verdict_text"],
                missed=missed_text,
            )

            response = client.messages.create(
                model=GENAI_MODEL,
                max_tokens=capped_max_tokens(384),
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text if response.content else ""
            if text and text.strip():
                return {"review": review, "coaching": text.strip(), "generated_by": provider_label()}
        except Exception as e:
            print("News thesis coaching failed: {}".format(e))

    # Deterministic coaching: the verdict plus the strongest thing they missed.
    bits = [review["verdict_text"]]
    if review["missed"]:
        top = review["missed"][0]
        bits.append(
            'You did not mention "{title}" ({label}), which {why}.'.format(
                title=top["title"][:90], label=top["sentiment_label"], why=top["why"],
            )
        )
    bits.append(review["lesson"])
    return {"review": review, "coaching": " ".join(bits), "generated_by": "deterministic"}
