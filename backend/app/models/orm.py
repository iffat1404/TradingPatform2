from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, ForeignKey, Text, Enum, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.core.db import Base
import enum


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class KYCStatus(str, enum.Enum):
    NOT_STARTED = "NOT_STARTED"
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class OrderStatus(str, enum.Enum):
    NEW = "NEW"
    VALIDATED = "VALIDATED"
    ROUTED = "ROUTED"
    FILLED = "FILLED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class OrderSide(str, enum.Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, enum.Enum):
    MARKET = "market"
    LIMIT = "limit"


class Role(str, enum.Enum):
    TRADER = "trader"
    ADMIN = "admin"


class Account(Base):
    __tablename__ = "accounts"
    
    id = Column(String, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(Enum(Role), default=Role.TRADER, nullable=False)
    kyc_status = Column(Enum(KYCStatus), default=KYCStatus.NOT_STARTED, nullable=False)
    starting_capital = Column(Float, default=1_000_000.0, nullable=False)
    cash_balance = Column(Float, default=1_000_000.0, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    
    # Relationships
    kyc_submissions = relationship("KYCSubmission", back_populates="account", foreign_keys="KYCSubmission.account_id")
    orders = relationship("Order", back_populates="account")
    positions = relationship("Position", back_populates="account")
    cash_ledger_entries = relationship("CashLedger", back_populates="account")
    journal_entries = relationship("JournalEntry", back_populates="account")


class KYCSubmission(Base):
    __tablename__ = "kyc_submissions"
    
    id = Column(String, primary_key=True, index=True)
    account_id = Column(String, ForeignKey("accounts.id"), nullable=False)
    id_type = Column(String, nullable=False)  # passport, drivers_license, national_id
    document_path = Column(String, nullable=False)
    
    # GenAI extracted fields
    extracted_full_name = Column(String, nullable=True)
    extracted_dob = Column(DateTime, nullable=True)
    extracted_id_number = Column(String, nullable=True)
    extracted_expiry_date = Column(DateTime, nullable=True)
    extracted_issuing_country = Column(String, nullable=True)
    extraction_confidence = Column(String, nullable=True)  # high, medium, low
    
    # Auto-check results
    auto_check_passed = Column(Boolean, nullable=True)
    auto_check_notes = Column(Text, nullable=True)
    
    # Status and review
    status = Column(Enum(KYCStatus), default=KYCStatus.PENDING_REVIEW, nullable=False)
    reviewed_by_admin_id = Column(String, ForeignKey("accounts.id"), nullable=True)
    review_notes = Column(Text, nullable=True)
    submitted_at = Column(DateTime, default=utcnow, nullable=False)
    reviewed_at = Column(DateTime, nullable=True)
    
    # Relationships
    account = relationship("Account", back_populates="kyc_submissions", foreign_keys=[account_id])
    reviewer = relationship("Account", foreign_keys=[reviewed_by_admin_id])


class Order(Base):
    __tablename__ = "orders"
    
    id = Column(String, primary_key=True, index=True)
    account_id = Column(String, ForeignKey("accounts.id"), nullable=False)
    ticker = Column(String, nullable=False)
    side = Column(Enum(OrderSide), nullable=False)
    type = Column(Enum(OrderType), nullable=False)
    qty = Column(Integer, nullable=False)
    limit_price = Column(Float, nullable=True)  # Null for market orders

    # Trade plan. Recorded for decision scoring and journaling only — NOT enforced:
    # nothing auto-exits on these levels. Their value is that a trade with a stated
    # target and stop is a planned trade, which is what the quality score measures.
    target_price = Column(Float, nullable=True)
    stop_loss = Column(Float, nullable=True)

    status = Column(Enum(OrderStatus), default=OrderStatus.NEW, nullable=False)
    is_backtest = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    # simulation_timestamp = Column(DateTime, nullable=True)  # UTC from MarketClock - will be added via migration
    
    # Relationships
    account = relationship("Account", back_populates="orders")
    events = relationship("OrderEvent", back_populates="order")
    fills = relationship("Fill", back_populates="order")
    
    # Property alias for compatibility with frontend
    @property
    def quantity(self):
        return self.qty
    
    # Indexes
    __table_args__ = (
        Index('ix_orders_account_id_status', 'account_id', 'status'),
        Index('ix_orders_is_backtest', 'is_backtest'),
    )


class OrderEvent(Base):
    __tablename__ = "order_events"
    
    id = Column(String, primary_key=True, index=True)
    order_id = Column(String, ForeignKey("orders.id"), nullable=False)
    from_state = Column(Enum(OrderStatus), nullable=True)
    to_state = Column(Enum(OrderStatus), nullable=False)
    reason = Column(String, nullable=True)  # Reason code for state transitions
    is_backtest = Column(Boolean, default=False, nullable=False)
    timestamp = Column(DateTime, default=utcnow, nullable=False)
    # simulation_timestamp = Column(DateTime, nullable=True)  # UTC from MarketClock - will be added via migration
    
    # Relationships
    order = relationship("Order", back_populates="events")


class Fill(Base):
    __tablename__ = "fills"
    
    id = Column(String, primary_key=True, index=True)
    order_id = Column(String, ForeignKey("orders.id"), nullable=False)
    fill_price = Column(Float, nullable=False)
    fill_qty = Column(Integer, nullable=False)
    fees = Column(Float, default=1.0, nullable=False)  # Flat fee per trade
    is_backtest = Column(Boolean, default=False, nullable=False)
    timestamp = Column(DateTime, default=utcnow, nullable=False)
    # simulation_timestamp = Column(DateTime, nullable=True)  # UTC from MarketClock - will be added via migration
    
    # Relationships
    order = relationship("Order", back_populates="fills")


class Position(Base):
    __tablename__ = "positions"
    
    id = Column(String, primary_key=True, index=True)
    account_id = Column(String, ForeignKey("accounts.id"), nullable=False)
    ticker = Column(String, nullable=False)
    signed_qty = Column(Integer, nullable=False)  # Positive for long, negative for short
    avg_cost = Column(Float, nullable=False)
    realized_pnl = Column(Float, default=0.0, nullable=False)
    collateral_reserved = Column(Float, default=0.0, nullable=False)  # Collateral for short positions
    is_backtest = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
    
    # Relationships
    account = relationship("Account", back_populates="positions")
    lots = relationship("PositionLot", back_populates="position", cascade="all, delete-orphan")
    
    # Unique constraint to prevent collision between live and backtest positions
    __table_args__ = (
        UniqueConstraint('account_id', 'ticker', 'is_backtest', name='uq_position_account_ticker_backtest'),
    )


class PositionLot(Base):
    """
    FIFO lots for tracking position cost basis.
    Used for accurate realized P&L calculation on partial closes.
    """
    __tablename__ = "position_lots"
    
    id = Column(String, primary_key=True, index=True)
    position_id = Column(String, ForeignKey("positions.id"), nullable=False)
    ticker = Column(String, nullable=False)
    side = Column(Enum(OrderSide), nullable=False)  # BUY or SELL
    qty = Column(Integer, nullable=False)  # Quantity in this lot
    cost = Column(Float, nullable=False)  # Cost basis per share
    opened_at = Column(DateTime, default=utcnow, nullable=False)
    closed_at = Column(DateTime, nullable=True)  # Null if still open
    is_backtest = Column(Boolean, default=False, nullable=False)
    
    # Relationships
    position = relationship("Position", back_populates="lots")
    
    # Index for efficient querying of open lots
    __table_args__ = (
        Index('ix_position_lots_position_closed', 'position_id', 'closed_at'),
    )


class CashLedger(Base):
    __tablename__ = "cash_ledger"
    
    id = Column(String, primary_key=True, index=True)
    account_id = Column(String, ForeignKey("accounts.id"), nullable=False)
    amount = Column(Float, nullable=False)  # Positive for credit, negative for debit
    reason = Column(String, nullable=False)  # TRADE_BUY, TRADE_SELL, COLLATERAL_RESERVE, COLLATERAL_RELEASE, etc.
    is_backtest = Column(Boolean, default=False, nullable=False)
    timestamp = Column(DateTime, default=utcnow, nullable=False)
    
    # Relationships
    account = relationship("Account", back_populates="cash_ledger_entries")


class PriceHistoryDaily(Base):
    __tablename__ = "price_history_daily"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String, nullable=False, index=True)
    date = Column(DateTime, nullable=False)  # Date component only
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    adj_close = Column(Float, nullable=True)
    volume = Column(Integer, nullable=False)
    
    # Unique constraint
    __table_args__ = (
        UniqueConstraint('ticker', 'date', name='uq_price_daily_ticker_date'),
    )


class PriceHistoryMinute(Base):
    __tablename__ = "price_history_minute"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String, nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False)  # Full timestamp with time
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Integer, nullable=False)
    # simulation_timestamp = Column(DateTime, nullable=True)  # UTC from MarketClock - will be added via migration
    
    # Index for efficient querying
    __table_args__ = (
        Index('ix_price_minute_ticker_timestamp', 'ticker', 'timestamp'),
    )


class NewsSentimentDaily(Base):
    __tablename__ = "news_sentiment_daily"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String, nullable=False, index=True)
    date = Column(DateTime, nullable=False)  # Date component only
    avg_sentiment = Column(Float, nullable=False)  # Average sentiment score for the day
    headline_count = Column(Integer, nullable=False)  # Number of headlines

    # Unique constraint
    __table_args__ = (
        UniqueConstraint('ticker', 'date', name='uq_news_sentiment_ticker_date'),
    )


class NewsArticle(Base):
    """
    An individual headline as it relates to one ticker.

    The seed loader previously collapsed the news JSON into NewsSentimentDaily's daily
    average and discarded the headlines, so traders had no way to see *what* the news
    actually said. This table keeps one row per (article, ticker) pair — the grain the
    source data is scored at, since a single story can mention several tickers with
    different relevance and sentiment.
    """
    __tablename__ = "news_articles"

    id = Column(String, primary_key=True, index=True)
    ticker = Column(String, nullable=False, index=True)
    date = Column(DateTime, nullable=False)          # Trading date (no time component)
    published_at = Column(DateTime, nullable=False)  # Full publish timestamp
    title = Column(Text, nullable=False)

    # How much this story is about this ticker, and which way it leans.
    relevance_score = Column(Float, nullable=False)
    sentiment_score = Column(Float, nullable=False)
    sentiment_label = Column(String, nullable=False)  # Bullish .. Bearish
    topics = Column(String, nullable=True)            # Comma-separated topic names

    __table_args__ = (
        Index('ix_news_articles_ticker_date', 'ticker', 'date'),
        Index('ix_news_articles_date', 'date'),
        # The same story can legitimately appear for several tickers, so uniqueness is on
        # the pair rather than the title alone.
        UniqueConstraint('ticker', 'published_at', 'title', name='uq_news_article_ticker_pub_title'),
    )


class BacktestStrategy(Base):
    """
    Declarative strategy schema for paper trading backtests.
    """
    __tablename__ = "backtest_strategies"
    
    id = Column(String, primary_key=True, index=True)
    account_id = Column(String, ForeignKey("accounts.id"), nullable=False)
    name = Column(String, nullable=False)
    ticker = Column(String, nullable=False)
    entry_rule = Column(String, nullable=False)  # JSON string defining entry conditions
    exit_rule = Column(String, nullable=False)  # JSON string defining exit conditions
    position_size = Column(Integer, nullable=False)  # Fixed position size per trade
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    
    # Relationships
    account = relationship("Account")
    runs = relationship("BacktestRun", back_populates="strategy")


class BacktestRun(Base):
    """
    Backtest execution results.
    """
    __tablename__ = "backtest_runs"
    
    id = Column(String, primary_key=True, index=True)
    strategy_id = Column(String, ForeignKey("backtest_strategies.id"), nullable=False)
    account_id = Column(String, ForeignKey("accounts.id"), nullable=False)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    
    # Performance metrics
    starting_capital = Column(Float, nullable=False)
    ending_capital = Column(Float, nullable=False)
    total_return = Column(Float, nullable=False)
    benchmark_return = Column(Float, nullable=False)  # Buy-and-hold return for comparison
    max_drawdown = Column(Float, nullable=False)
    win_rate = Column(Float, nullable=False)
    total_trades = Column(Integer, nullable=False)
    winning_trades = Column(Integer, nullable=False)
    
    status = Column(String, default="completed", nullable=False)  # running, completed, failed
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    
    # Relationships
    strategy = relationship("BacktestStrategy", back_populates="runs")
    account = relationship("Account")


class JournalEntry(Base):
    """
    AI Trading Journal entry.

    A trader's written rationale and emotional state for a trade (or a standalone
    reflection). Behavioural flags are computed deterministically from real order/fill
    history; the AI layer only narrates those findings, per platform principle 1.
    """
    __tablename__ = "journal_entries"

    id = Column(String, primary_key=True, index=True)
    account_id = Column(String, ForeignKey("accounts.id"), nullable=False)
    order_id = Column(String, ForeignKey("orders.id"), nullable=True)  # Null for standalone reflections
    ticker = Column(String, nullable=True)  # Denormalized from the linked order when present
    entry_type = Column(String, nullable=False, default="trade_note")  # trade_note, reflection
    # Nullable because auto-logged entries are created at fill time with no rationale yet —
    # the trader is prompted to annotate them afterwards.
    rationale = Column(Text, nullable=True)
    emotional_tags = Column(String, nullable=True)  # Comma-separated, e.g. "fomo,anxious"
    # True when the system created this entry at fill time rather than the trader writing it.
    is_auto = Column(Boolean, default=False, nullable=False)
    # The headline the trader says drove this trade. Lets the coach later check whether that
    # news actually moved the price, and what else was published that they ignored.
    news_article_id = Column(String, ForeignKey("news_articles.id"), nullable=True)

    # Cached output of the last analysis run (regenerated on demand, never automatically)
    ai_feedback = Column(Text, nullable=True)
    ai_flags = Column(String, nullable=True)  # Comma-separated, e.g. "possible_fomo"
    ai_generated_by = Column(String, nullable=True)  # claude, deterministic, error
    ai_generated_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    # Relationships
    account = relationship("Account", back_populates="journal_entries")
    order = relationship("Order")
    news_article = relationship("NewsArticle")

    # Index for the common "my entries, newest first" query
    __table_args__ = (
        Index('ix_journal_entries_account_created', 'account_id', 'created_at'),
    )


class TradeDecision(Base):
    """
    A snapshot of the Decision Intelligence assessment for one order.

    Scores are computed by deterministic rules in decision_engine; GenAI only narrates
    them. Advisory only — a poor score never blocks an order. The full factor breakdown
    and market context are stored as JSON so the UI can show exactly why a score was
    given, and so historical decisions stay explainable after prices move on.
    """
    __tablename__ = "trade_decisions"

    id = Column(String, primary_key=True, index=True)
    account_id = Column(String, ForeignKey("accounts.id"), nullable=False)
    # Null for a preview that was scored but never submitted.
    order_id = Column(String, ForeignKey("orders.id"), nullable=True, unique=True)
    ticker = Column(String, nullable=False)

    risk_score = Column(Float, nullable=False)              # 0-100, higher = riskier
    decision_quality_score = Column(Float, nullable=False)  # 0-100, higher = better process
    grade = Column(String, nullable=False)                  # A / B / C / D

    factors_json = Column(Text, nullable=False)   # per-factor breakdown, for transparency
    context_json = Column(Text, nullable=False)   # indicators, volatility, sentiment at entry

    created_at = Column(DateTime, default=utcnow, nullable=False)

    # Relationships
    account = relationship("Account")
    order = relationship("Order")

    __table_args__ = (
        Index('ix_trade_decisions_account_created', 'account_id', 'created_at'),
    )


class LevelAlert(Base):
    """
    A target or stop level being reached on an open position.

    Advisory only: the platform never exits for you. The alert exists so the trader is told
    their own plan has triggered, and so the journal can later ask the more useful question
    - when your stop hit, did you actually act on it?

    One unresolved alert per (account, ticker, kind) at a time, so a position sitting below
    its stop does not generate an alert on every poll.
    """
    __tablename__ = "level_alerts"

    id = Column(String, primary_key=True, index=True)
    account_id = Column(String, ForeignKey("accounts.id"), nullable=False)
    ticker = Column(String, nullable=False)
    # The order whose recorded plan produced this level.
    order_id = Column(String, ForeignKey("orders.id"), nullable=True)

    kind = Column(String, nullable=False)          # "target" | "stop"
    level_price = Column(Float, nullable=False)    # the level the trader set
    trigger_price = Column(Float, nullable=False)  # the price that breached it
    signed_qty = Column(Integer, nullable=False)   # position size when it fired

    acknowledged = Column(Boolean, default=False, nullable=False)
    acknowledged_at = Column(DateTime, nullable=True)
    # Set once the position is closed or flipped, so the same level can fire again later.
    resolved = Column(Boolean, default=False, nullable=False)
    resolved_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=utcnow, nullable=False)

    account = relationship("Account")
    order = relationship("Order")

    __table_args__ = (
        Index('ix_level_alerts_account_resolved', 'account_id', 'resolved'),
    )


class MarketSession(Base):
    """
    Market session tracking for Global MarketClock.
    Records session state including simulated time, speed multiplier, and market status.
    """
    __tablename__ = "market_sessions"
    
    id = Column(String, primary_key=True, index=True)
    account_id = Column(String, ForeignKey("accounts.id"), nullable=True)  # Nullable for global sessions
    start_timestamp = Column(DateTime, nullable=False)
    current_timestamp = Column(DateTime, nullable=False)
    speed_multiplier = Column(Float, default=1.0, nullable=False)
    market_status = Column(String, default="open", nullable=False)  # pre-market, open, closed
    created_at = Column(DateTime, default=utcnow, nullable=False)
    
    # Relationships
    account = relationship("Account")