"""
Worked examples of the Decision Intelligence Engine, using a trader called "Ram".

Every number below comes from the live database — real prices, real RSI, real ATR, real
news sentiment. Run it to check the feature end to end:

    python demo_ram.py

Each case prints the two scores plus the per-factor arithmetic, so you can verify by hand
that the engine is doing what it claims.
"""
import sys
import io
import uuid

from app.core.db import SessionLocal
from app.core.security import get_password_hash
from app.models.orm import Account, Role, KYCStatus
from app.services.analytics_engine import calculate_atr_percent, get_latest_indicators, get_latest_sentiment
from app.services.decision_engine import evaluate_trade
from app.services.portfolio_engine import get_latest_market_prices

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

RAM = "ram_demo"


def ensure_ram(db) -> Account:
    """A KYC-approved trader with $1,000,000 and no positions — a clean slate."""
    ram = db.query(Account).filter(Account.username == RAM).first()
    if ram:
        return ram
    ram = Account(
        id=str(uuid.uuid4()),
        username=RAM,
        password_hash=get_password_hash("rampass123"),
        role=Role.TRADER,
        kyc_status=KYCStatus.APPROVED,
        starting_capital=1_000_000.0,
        cash_balance=1_000_000.0,
    )
    db.add(ram)
    db.commit()
    db.refresh(ram)
    return ram


def market_table(db):
    prices = get_latest_market_prices(db)
    print("LIVE MARKET DATA (what the engine reads)")
    print(f"{'TICKER':<8}{'PRICE':>9}{'RSI':>7}{'ATR%':>7}{'NEWS':>8}  NOTE")
    print("-" * 62)
    for t in ["AAPL", "GOOG", "IBM", "MSFT", "TSLA", "UL", "WMT"]:
        ind = get_latest_indicators(db, t)
        atr = calculate_atr_percent(db, t) or 0
        sent = get_latest_sentiment(db, t) or {}
        rsi = ind.get("rsi_14") or 0
        notes = []
        if rsi > 70:
            notes.append("overbought")
        elif rsi < 30:
            notes.append("oversold")
        else:
            notes.append("neutral RSI")
        if atr > 4:
            notes.append("high volatility")
        elif atr < 1.5:
            notes.append("calm")
        print(f"{t:<8}{prices.get(t, 0):>9.2f}{rsi:>7.1f}{atr:>7.2f}"
              f"{sent.get('avg_sentiment', 0):>8.2f}  {', '.join(notes)}")
    print()
    return prices


def run(db, ram, title, expectation, **kw):
    res = evaluate_trade(db, account_id=ram.id, **kw)
    plan = (f"target {kw['target_price']}, stop {kw['stop_loss']}"
            if kw.get("target_price") else "NO target, NO stop")
    print("=" * 78)
    print(f"{title}")
    print(f"  Order : {kw['side'].upper()} {kw['qty']} {kw['ticker']} @ ${kw.get('price') or 0:.2f}  ({plan})")
    print(f"  Expect: {expectation}")
    print(f"  ACTUAL: risk {res['risk_score']:.0f}/100   quality "
          f"{res['decision_quality_score']:.0f}/100   grade {res['grade']}")
    print()
    for heading, key in (("RISK — why", "risk_factors"), ("QUALITY — why", "quality_factors")):
        print(f"  {heading}")
        for f in res[key]:
            print(f"    {f['label']:<26} {f['score']:>5.1f} x {f['weight']:.2f}  {f['note']}")
        print()
    return res


def main() -> int:
    db = SessionLocal()
    try:
        prices = market_table(db)
        ram = ensure_ram(db)
        print(f"Trader: {ram.username} | cash ${ram.cash_balance:,.0f} | KYC {ram.kyc_status.value}\n")

        ul, tsla = prices.get("UL", 53.62), prices.get("TSLA", 201.93)

        # UL: neutral RSI, calmest ATR of the seven -> the textbook well-made trade.
        a = run(db, ram,
                "CASE 1  Disciplined trade: small size, calm stock, 2.7:1 plan",
                "HIGH quality (A) and LOW risk. Nothing here is stretched.",
                ticker="UL", side="buy", qty=20, price=ul, target_price=58.0, stop_loss=52.0)

        # TSLA: RSI 96 and 4% ATR -> the most stretched name on the board.
        b = run(db, ram,
                "CASE 2  Reckless trade: 20% of net worth into the most overbought name, no plan",
                "LOW quality (D) and HIGH risk. Every factor should be against it.",
                ticker="TSLA", side="buy", qty=1000, price=tsla)

        # Same reckless size, but now planned -> proves the two scores are independent.
        c = run(db, ram,
                "CASE 3  Same big TSLA trade, but WITH a plan",
                "Quality rises a lot; risk stays high. Risk and quality are different things.",
                ticker="TSLA", side="buy", qty=1000, price=tsla,
                target_price=230.0, stop_loss=190.0)

        # Stop above entry on a buy -> not a plan, a mistake.
        d = run(db, ram,
                "CASE 4  Backwards plan: stop ABOVE entry on a buy",
                "Quality should COLLAPSE — the engine must refuse to credit an unusable plan.",
                ticker="UL", side="buy", qty=20, price=ul, target_price=50.0, stop_loss=56.0)

        print("=" * 78)
        print("CHECKS")
        checks = [
            ("Disciplined trade grades A", a["grade"] == "A"),
            ("Reckless trade grades D", b["grade"] == "D"),
            ("Adding a plan raises quality",
             c["decision_quality_score"] > b["decision_quality_score"]),
            ("Risk stays high despite the plan (independent axes)",
             abs(c["risk_score"] - b["risk_score"]) < 1),
            ("Backwards plan scores worse than a real plan",
             d["decision_quality_score"] < a["decision_quality_score"]),
            ("Big position raises risk over a small one",
             b["risk_score"] > a["risk_score"]),
        ]
        for label, ok in checks:
            print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
        failed = sum(1 for _, ok in checks if not ok)
        print()
        print("All checks passed." if not failed else f"{failed} CHECK(S) FAILED")
        return 1 if failed else 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
