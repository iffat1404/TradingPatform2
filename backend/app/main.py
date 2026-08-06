from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, kyc, admin, orders, portfolio, reports, analytics, paper_trading, genai, journal, decision, news, levels, websockets, prices, news
from app.core.db import engine, Base, SessionLocal
from app.data.loaders import load_all_data
from app.models.orm import PriceHistoryDaily, PriceHistoryMinute
from app.services.market_clock import get_market_clock

# Create database tables
Base.metadata.create_all(bind=engine)

# Seed the database with historical and live market data if it is empty.
def ensure_seed_data() -> None:
    db = SessionLocal()
    try:
        has_daily = db.query(PriceHistoryDaily).first() is not None
        has_minute = db.query(PriceHistoryMinute).first() is not None
        if has_daily or has_minute:
            return
    finally:
        db.close()

    db = SessionLocal()
    try:
        data_dir = Path(__file__).resolve().parent / "data"
        load_all_data(db, data_dir=str(data_dir))
    finally:
        db.close()


ensure_seed_data()

# Initialize and start MarketClock
def initialize_market_clock() -> None:
    market_clock = get_market_clock()
    market_clock.start()
    print("MarketClock started")


initialize_market_clock()

app = FastAPI(
    title="Nomura STP Trading Platform Group 11",
    description="Straight-Through-Processing trading simulation platform",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(kyc.router, prefix="/api/kyc", tags=["kyc"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(orders.router, prefix="/api/orders", tags=["orders"])
app.include_router(portfolio.router, prefix="/api/portfolio", tags=["portfolio"])
app.include_router(reports.router, prefix="/api/reports", tags=["reports"])
app.include_router(prices.router, prefix="/api/prices", tags=["prices"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["analytics"])
app.include_router(paper_trading.router, prefix="/api/paper-trading", tags=["paper-trading"])
app.include_router(genai.router, prefix="/api/genai", tags=["genai"])
app.include_router(decision.router, prefix="/api/decision", tags=["decision"])
app.include_router(news.router, prefix="/api/news", tags=["news"])
app.include_router(levels.router, prefix="/api/levels", tags=["levels"])
app.include_router(journal.router, prefix="/api/journal", tags=["journal"])
app.include_router(news.router, prefix="/api/news", tags=["news"])
app.include_router(websockets.router, prefix="/ws", tags=["websockets"])


@app.get("/health")
def health_check():
    return {"status": "healthy"}