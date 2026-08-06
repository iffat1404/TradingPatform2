"""
Decision Intelligence Engine.

Scores the *quality of a trading decision* before it is executed — never which stock to
buy. Two numbers come out of it:

    risk_score              0-100, higher = more risk being taken on
    decision_quality_score  0-100, higher = better process (plan, sizing, discipline)

Both are computed by transparent deterministic rules over real portfolio, price and
sentiment data, and every factor reports its own inputs and sub-score so the UI can show
exactly *why* a score is what it is. GenAI never computes these — it only narrates them
afterwards, per platform principle 1.

These scores are advisory. Nothing here can reject an order; the deterministic risk chain
in order_engine.validate_order remains the only thing that does.
"""
from typing import Dict, Any, List, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.orm import OrderSide
from app.services.analytics_engine import (
    calculate_atr_percent,
    get_latest_indicators,
    get_latest_sentiment,
)
from app.services.portfolio_engine import (
    calculate_portfolio_metrics,
    get_latest_market_prices,
)

# Sizing bands, expressed as a share of net worth.
COMFORTABLE_POSITION_PCT = 10.0   # at or below this, sizing is not a concern
SIZING_FULL_MARKS_PCT = 10.0

# Volatility bands on ATR%.
VOL_CALM_PCT = 1.5
VOL_HIGH_PCT = 4.0

# A 2:1 reward-to-risk plan earns full marks.
TARGET_REWARD_RISK = 2.0

# Weights must sum to 1.0 within each score.
RISK_WEIGHTS = {
    "concentration": 0.30,
    "diversification": 0.20,
    "technical_stretch": 0.20,
    "volatility": 0.20,
    "sentiment": 0.10,
}
QUALITY_WEIGHTS = {
    "plan_completeness": 0.35,
    "reward_risk": 0.25,
    "size_discipline": 0.20,
    "signal_alignment": 0.10,
    "journaling_discipline": 0.10,
}


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _factor(key: str, label: str, weight: float, score: float, value, note: str) -> Dict[str, Any]:
    """One transparent line of the breakdown."""
    return {
        "key": key,
        "label": label,
        "weight": round(weight, 2),
        "score": round(_clamp(score), 1),
        "value": value,
        "note": note,
    }


def _weighted(factors: List[Dict[str, Any]]) -> float:
    total_weight = sum(f["weight"] for f in factors) or 1.0
    return round(sum(f["score"] * f["weight"] for f in factors) / total_weight, 1)


def build_trade_context(
    db: Session,
    account_id: str,
    ticker: str,
    side,
    qty: int,
    price: Optional[float] = None,
    target_price: Optional[float] = None,
    stop_loss: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Gather everything the scoring rules need: portfolio state, indicators, volatility and
    news sentiment for one prospective trade.
    """
    ticker = (ticker or "").upper()
    side_value = side.value if hasattr(side, "value") else str(side or "").lower()

    prices = get_latest_market_prices(db)
    entry_price = price if price else prices.get(ticker)

    metrics = calculate_portfolio_metrics(db, account_id, prices) or {}
    indicators = get_latest_indicators(db, ticker)
    atr_pct = calculate_atr_percent(db, ticker)
    sentiment = get_latest_sentiment(db, ticker)

    notional = (entry_price or 0.0) * (qty or 0)
    net_worth = metrics.get("net_worth") or 0.0
    ticker_exposure = dict(metrics.get("ticker_exposure") or {})

    # Exposure as it would look *after* this trade — that is what the trader is choosing.
    projected_exposure = dict(ticker_exposure)
    projected_exposure[ticker] = projected_exposure.get(ticker, 0.0) + notional

    return {
        "ticker": ticker,
        "side": side_value,
        "qty": qty,
        "entry_price": entry_price,
        "notional": notional,
        "target_price": target_price,
        "stop_loss": stop_loss,
        "net_worth": net_worth,
        "cash_balance": metrics.get("cash_balance"),
        "ticker_exposure": ticker_exposure,
        "projected_exposure": projected_exposure,
        "position_count": len(ticker_exposure),
        "indicators": indicators,
        "atr_percent": atr_pct,
        "sentiment": sentiment,
    }


# --------------------------------------------------------------------------- risk factors


def _risk_concentration(ctx) -> Dict[str, Any]:
    net_worth, notional = ctx["net_worth"], ctx["notional"]
    if not net_worth:
        return _factor("concentration", "Position concentration", RISK_WEIGHTS["concentration"],
                       50.0, None, "Net worth unavailable — assuming moderate risk.")

    pct = (ctx["projected_exposure"].get(ctx["ticker"], 0.0) / net_worth) * 100.0
    limit = settings.MAX_CONCENTRATION_PCT or 25.0
    # Full risk once the position reaches the platform's hard concentration limit.
    score = (pct / limit) * 100.0
    return _factor(
        "concentration", "Position concentration", RISK_WEIGHTS["concentration"], score,
        round(pct, 2),
        f"{pct:.1f}% of net worth in {ctx['ticker']} after this trade (limit {limit:.0f}%).",
    )


def _risk_diversification(ctx) -> Dict[str, Any]:
    exposure = {k: v for k, v in ctx["projected_exposure"].items() if v}
    total = sum(exposure.values())
    if not total:
        return _factor("diversification", "Portfolio diversification", RISK_WEIGHTS["diversification"],
                       50.0, 0, "No exposure yet — first position carries concentration risk by definition.")

    # Herfindahl index: 1.0 = everything in one name, ->0 = evenly spread.
    hhi = sum((v / total) ** 2 for v in exposure.values())
    score = hhi * 100.0
    return _factor(
        "diversification", "Portfolio diversification", RISK_WEIGHTS["diversification"], score,
        round(hhi, 3),
        f"{len(exposure)} name(s) held; concentration index {hhi:.2f} (1.00 = single name).",
    )


def _risk_technical(ctx) -> Dict[str, Any]:
    ind, side = ctx["indicators"], ctx["side"]
    rsi, close = ind.get("rsi_14"), ind.get("close")
    upper, lower = ind.get("bb_upper"), ind.get("bb_lower")

    if rsi is None:
        return _factor("technical_stretch", "Technical stretch", RISK_WEIGHTS["technical_stretch"],
                       50.0, None, "No indicator history for this ticker.")

    overbought = settings.RSI_OVERBOUGHT or 70.0
    oversold = settings.RSI_OVERSOLD or 30.0

    # Buying into strength or selling into weakness is the stretched direction.
    if side == "buy":
        score = _clamp((rsi - 50.0) / (overbought - 50.0) * 100.0)
        stretched = rsi > overbought
        detail = f"RSI {rsi:.0f}" + (" — overbought while buying." if stretched else " on a buy.")
    else:
        score = _clamp((50.0 - rsi) / (50.0 - oversold) * 100.0)
        stretched = rsi < oversold
        detail = f"RSI {rsi:.0f}" + (" — oversold while selling." if stretched else " on a sell.")

    # Trading outside the Bollinger envelope in the stretched direction adds risk.
    if close and upper and lower:
        if (side == "buy" and close > upper) or (side != "buy" and close < lower):
            score = _clamp(score + 20.0)
            detail += " Price is outside the Bollinger band."

    return _factor("technical_stretch", "Technical stretch", RISK_WEIGHTS["technical_stretch"],
                   score, round(rsi, 1), detail)


def _risk_volatility(ctx) -> Dict[str, Any]:
    atr_pct = ctx["atr_percent"]
    if atr_pct is None:
        return _factor("volatility", "Market volatility", RISK_WEIGHTS["volatility"],
                       50.0, None, "Not enough price history to measure volatility.")

    # Scale calm->high onto 0->100, saturating beyond the high band.
    score = _clamp((atr_pct - VOL_CALM_PCT) / (VOL_HIGH_PCT - VOL_CALM_PCT) * 100.0)
    if atr_pct < VOL_CALM_PCT:
        band = "calm"
    elif atr_pct < VOL_HIGH_PCT:
        band = "normal"
    else:
        band = "elevated"
    return _factor("volatility", "Market volatility", RISK_WEIGHTS["volatility"], score,
                   round(atr_pct, 2), f"14-day ATR is {atr_pct:.1f}% of price ({band}).")


def _risk_sentiment(ctx) -> Dict[str, Any]:
    sentiment = ctx["sentiment"]
    if not sentiment or sentiment.get("avg_sentiment") is None:
        return _factor("sentiment", "News sentiment", RISK_WEIGHTS["sentiment"],
                       50.0, None, "No recent news sentiment for this ticker.")

    value = sentiment["avg_sentiment"]
    # Risk rises when the trade leans against the prevailing news tone.
    against = -value if ctx["side"] == "buy" else value
    score = _clamp(50.0 + against * 50.0)
    direction = "positive" if value >= 0 else "negative"
    return _factor("sentiment", "News sentiment", RISK_WEIGHTS["sentiment"], score,
                   round(value, 3),
                   f"Recent coverage is {direction} ({value:+.2f}) across "
                   f"{sentiment.get('headline_count', 0)} headline(s).")


# ------------------------------------------------------------------------ quality factors


def _levels_are_coherent(ctx) -> bool:
    """
    A target above and stop below the entry (inverted for a sell). Levels on the wrong
    side of the entry are not a plan — they are a mistake, and shouldn't earn credit.
    """
    entry, target, stop = ctx["entry_price"], ctx["target_price"], ctx["stop_loss"]
    if not entry or target is None or stop is None:
        return True  # nothing to contradict yet; missing levels are scored separately
    if ctx["side"] == "buy":
        return target > entry > stop
    return target < entry < stop


def _quality_plan(ctx) -> Dict[str, Any]:
    has_target = ctx["target_price"] is not None
    has_stop = ctx["stop_loss"] is not None
    coherent = _levels_are_coherent(ctx)
    score = (50.0 if has_target else 0.0) + (50.0 if has_stop else 0.0)

    if has_target and has_stop and not coherent:
        # Both fields filled but pointing the wrong way — credit the intent, not the plan.
        score = 25.0
        note = ("Target and stop are on the wrong side of your entry, so this plan cannot "
                "be acted on as written.")
    elif has_target and has_stop:
        note = "Both a target and a stop are defined — this is a planned trade."
    elif has_stop:
        note = "Stop set, no target. You know your downside but not when to take profit."
    elif has_target:
        note = "Target set, no stop. Your downside is currently unbounded."
    else:
        note = "No target and no stop — there is no written plan for this trade."

    return _factor("plan_completeness", "Trade plan", QUALITY_WEIGHTS["plan_completeness"],
                   score, {"target": has_target, "stop": has_stop, "coherent": coherent}, note)


def _quality_reward_risk(ctx) -> Dict[str, Any]:
    entry, target, stop = ctx["entry_price"], ctx["target_price"], ctx["stop_loss"]
    weight = QUALITY_WEIGHTS["reward_risk"]

    if not entry or target is None or stop is None:
        return _factor("reward_risk", "Reward vs risk", weight, 0.0, None,
                       "Cannot be measured without both a target and a stop.")

    if ctx["side"] == "buy":
        reward, risk = target - entry, entry - stop
    else:
        reward, risk = entry - target, stop - entry

    if risk <= 0 or reward <= 0:
        return _factor("reward_risk", "Reward vs risk", weight, 0.0, None,
                       "Target and stop are on the wrong side of the entry price.")

    ratio = reward / risk
    score = _clamp((ratio / TARGET_REWARD_RISK) * 100.0)
    return _factor("reward_risk", "Reward vs risk", weight, score, round(ratio, 2),
                   f"Risking {risk:.2f} to make {reward:.2f} — a {ratio:.1f}:1 ratio "
                   f"(>={TARGET_REWARD_RISK:.0f}:1 scores full marks).")


def _quality_sizing(ctx) -> Dict[str, Any]:
    net_worth, notional = ctx["net_worth"], ctx["notional"]
    weight = QUALITY_WEIGHTS["size_discipline"]
    if not net_worth:
        return _factor("size_discipline", "Position sizing", weight, 50.0, None,
                       "Net worth unavailable.")

    pct = (notional / net_worth) * 100.0
    if pct <= SIZING_FULL_MARKS_PCT:
        score = 100.0
    else:
        # Decays to zero as the position approaches the hard concentration limit.
        limit = settings.MAX_CONCENTRATION_PCT or 25.0
        span = max(limit - SIZING_FULL_MARKS_PCT, 1.0)
        score = _clamp(100.0 - ((pct - SIZING_FULL_MARKS_PCT) / span) * 100.0)

    return _factor("size_discipline", "Position sizing", weight, score, round(pct, 2),
                   f"This order is {pct:.1f}% of net worth "
                   f"(<={SIZING_FULL_MARKS_PCT:.0f}% scores full marks).")


def _quality_signal(ctx) -> Dict[str, Any]:
    rsi = ctx["indicators"].get("rsi_14")
    weight = QUALITY_WEIGHTS["signal_alignment"]
    if rsi is None:
        return _factor("signal_alignment", "Signal alignment", weight, 50.0, None,
                       "No indicator history for this ticker.")

    overbought = settings.RSI_OVERBOUGHT or 70.0
    oversold = settings.RSI_OVERSOLD or 30.0

    if ctx["side"] == "buy" and rsi > overbought:
        score, note = 20.0, f"Buying at RSI {rsi:.0f}, already overbought."
    elif ctx["side"] != "buy" and rsi < oversold:
        score, note = 20.0, f"Selling at RSI {rsi:.0f}, already oversold."
    else:
        score, note = 100.0, f"RSI {rsi:.0f} does not contradict this direction."

    return _factor("signal_alignment", "Signal alignment", weight, score, round(rsi, 1), note)


def _quality_journaling(ctx) -> Dict[str, Any]:
    coverage = ctx.get("journaled_coverage_pct")
    weight = QUALITY_WEIGHTS["journaling_discipline"]
    if coverage is None:
        return _factor("journaling_discipline", "Journaling discipline", weight, 50.0, None,
                       "No trading history yet.")
    return _factor("journaling_discipline", "Journaling discipline", weight, coverage,
                   round(coverage, 1),
                   f"You have journaled {coverage:.0f}% of your filled trades.")


def _grade(quality: float) -> str:
    if quality >= 80:
        return "A"
    if quality >= 65:
        return "B"
    if quality >= 45:
        return "C"
    return "D"


def score_trade(context: Dict[str, Any]) -> Dict[str, Any]:
    """Turn a trade context into the two scores plus a full factor breakdown."""
    risk_factors = [
        _risk_concentration(context),
        _risk_diversification(context),
        _risk_technical(context),
        _risk_volatility(context),
        _risk_sentiment(context),
    ]
    quality_factors = [
        _quality_plan(context),
        _quality_reward_risk(context),
        _quality_sizing(context),
        _quality_signal(context),
        _quality_journaling(context),
    ]

    risk_score = _weighted(risk_factors)
    quality_score = _weighted(quality_factors)

    return {
        "risk_score": risk_score,
        "decision_quality_score": quality_score,
        "grade": _grade(quality_score),
        "risk_factors": risk_factors,
        "quality_factors": quality_factors,
        "context": {
            "ticker": context["ticker"],
            "side": context["side"],
            "qty": context["qty"],
            "entry_price": context["entry_price"],
            "notional": context["notional"],
            "target_price": context["target_price"],
            "stop_loss": context["stop_loss"],
            "indicators": context["indicators"],
            "atr_percent": context["atr_percent"],
            "sentiment": context["sentiment"],
            "net_worth": context["net_worth"],
        },
    }


def evaluate_trade(
    db: Session,
    account_id: str,
    ticker: str,
    side,
    qty: int,
    price: Optional[float] = None,
    target_price: Optional[float] = None,
    stop_loss: Optional[float] = None,
    journaled_coverage_pct: Optional[float] = None,
) -> Dict[str, Any]:
    """Build the context and score it — the single entry point callers should use."""
    context = build_trade_context(
        db, account_id, ticker, side, qty, price, target_price, stop_loss
    )
    context["journaled_coverage_pct"] = journaled_coverage_pct
    return score_trade(context)
