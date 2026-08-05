# COMPREHENSIVE BACKEND DOCUMENTATION
## Nomura STP Trading Platform - Backend Architecture & Implementation

---

## TABLE OF CONTENTS

A. SYSTEM OVERVIEW
B. FILE STRUCTURE & ORGANIZATION
C. TECHNOLOGY STACK & DEPENDENCIES
D. CONFIGURATION & ENVIRONMENT VARIABLES
E. DATABASE SCHEMA & ORM MODELS
F. API ENDPOINTS - COMPLETE REFERENCE
G. WEBSOCKET ARCHITECTURE
H. SERVICES & BUSINESS LOGIC
I. DATA FLOW & ARCHITECTURE PATTERNS
J. ORDER VALIDATION & RISK MANAGEMENT
K. AUTHENTICATION & SECURITY
L. GLOBAL MARKETCLOCK SYSTEM
M. FEED SIMULATOR & DATA PIPELINE
N. TESTING STRATEGY
O. DEPLOYMENT CONSIDERATIONS

---

## A. SYSTEM OVERVIEW

### A.1 Platform Purpose
The Nomura STP (Straight-Through-Processing) Trading Platform is a comprehensive algorithmic trading simulation system designed for educational and institutional use. It provides:
- Real-time paper trading with simulated market data
- Full order lifecycle management with comprehensive risk controls
- Portfolio tracking and analytics
- Technical analysis and backtesting capabilities
- KYC/AML compliance features
- Global time synchronization for realistic market simulation

### A.2 Architecture Principles
1. **Single Source of Truth**: MarketClock service is the authoritative time source for all operations
2. **STP Automation**: Orders flow through system with minimal manual intervention
3. **Risk-First Design**: Multi-layer validation prevents risky trades
4. **Audit Trail**: Every action is logged for compliance and debugging
5. **Real-Time Updates**: WebSocket-based live data streaming to all clients

### A.3 Key Features
- **7 Tradable Instruments**: AAPL, GOOG, IBM, MSFT, TSLA, UL, WMT
- **Advanced Order Types**: Market, Limit orders with time-in-force
- **Risk Controls**: KYC, market hours, price collars, concentration limits, notional caps
- **Real-Time Data**: Simulated live market data via WebSocket
- **Time Control**: Admin can set simulation time and speed multipliers (1x, 2x, 5x, 12x, 30x)
- **Backtesting**: Strategy backtesting with historical data
- **GenAI Integration**: Claude AI for explanations and analysis
- **Compliance**: Wash-trade detection, audit logs, KYC workflow

---

## B. FILE STRUCTURE & ORGANIZATION

### B.1 Complete Directory Structure

```
backend/
├── app/                                    # Main application package
│   ├── __init__.py
│   ├── main.py                             # FastAPI application entry point
│   │                                          # Initializes MarketClock, routers, CORS
│   ├── api/                                 # API route handlers (11 modules)
│   │   ├── __init__.py
│   │   ├── auth.py                            # Authentication endpoints (3 routes)
│   │   │                                          # register, login, get current user
│   │   ├── kyc.py                             # KYC submission endpoints (2 routes)
│   │   │                                          # submit KYC, get KYC status
│   │   ├── admin.py                           # Admin management (14 routes)
│   │   │                                          # KYC queue, accounts, audit logs, trade logs
│   │   │                                          # compliance flags, session controls
│   │   ├── orders.py                          # Order management (5 routes)
│   │   │                                          # create, list, get, cancel, event trail
│   │   ├── portfolio.py                       # Portfolio endpoints (5 routes)
│   │   │                                          # summary, P&L, exposure, positions, lots
│   │   ├── reports.py                          # Report generation (2 routes)
│   │   │                                          # portfolio report, CSV export
│   │   ├── analytics.py                        # Technical analysis (3 routes)
│   │   │                                          # indicators, alerts, sentiment divergence
│   │   ├── paper_trading.py                    # Backtesting (4 routes)
│   │   │                                          # strategies, backtest runs, run, results
│   │   ├── genai.py                            # GenAI service (5 routes)
│   │   │                                          # portfolio summary, explain rejection
│   │   │                                          # explain ticker, extract ID, parse order
│   │   ├── prices.py                           # Price data endpoints (3 routes)
│   │   │                                          # latest price, intraday, daily, market/current
│   │   └── websockets.py                       # WebSocket endpoints (4 routes)
│   │                                              # market data, session, account, admin notifications
│   ├── core/                                # Core utilities (4 modules)
│   │   ├── __init__.py
│   │   ├── config.py                           # Configuration settings
│   │   │                                          # Database URL, JWT secrets, trading parameters
│   │   ├── db.py                               # Database connection and session
│   │   │                                          # SQLAlchemy engine, session factory
│   │   └── security.py                         # JWT and password security
│   │                                              # password hashing, JWT encoding/decoding
│   ├── models/                              # ORM models and schemas (2 modules)
│   │   ├── __init__.py
│   │   ├── orm.py                              # SQLAlchemy ORM models (12 tables)
│   │   │                                          # Account, Order, OrderEvent, Fill, Position
│   │   │                                          # CashLedger, PositionLot, KYCSubmission
│   │   │                                          # PriceHistoryDaily, PriceHistoryMinute
│   │   │                                          # BacktestRun, BacktestStrategy, MarketSession
│   │   └── schemas.py                          # Pydantic schemas (8 schemas)
│   │                                              # Request/response models for API validation
│   ├── services/                             # Business logic services (8 modules)
│   │   ├── __init__.py
│   │   ├── order_engine.py                      # Order processing engine
│   │   │                                          # validation, execution, fill logic
│   │   ├── portfolio_engine.py                   # Portfolio calculations
│   │   │                                          # metrics, P&L, exposure, lots (FIFO)
│   │   ├── analytics_engine.py                   # Technical indicators
│   │   │                                          # SMA, EMA, RSI, MACD, Bollinger Bands
│   │   ├── backtest_engine.py                    # Backtesting engine
│   │   │                                          # strategy execution, result calculation
│   │   ├── feed_simulator.py                     # Market data simulation
│   │   │                                          # get current tick for ticker, reset
│   │   ├── kyc_engine.py                         # KYC validation
│   │   │                                          # document validation, expiration checks
│   ├── genai_client.py                         # Anthropic Claude client
│   │                                          # API client for AI explanations
│   │   └── market_clock.py                       # Global time management
│   │                                              # simulated time, speed multipliers
│   └── data/                                 # Data loaders and files
│       ├── __init__.py
│       ├── loaders.py                          # CSV/JSON data loaders
│       │                                           # load_all_data, load_historical_data
│       ├── simulation_historical_data/           # Historical daily price data
│       │   ├── GOOG_2026_historical.csv           # 130 daily bars (2026-06-23 to 2026-12-15)
│       │   ├── IBM_2026_historical.csv            # 130 daily bars
│       │   ├── MSFT_2026_historical.csv           # 130 daily bars
│       │   ├── TSLA_2026_historical.csv           # 130 daily bars
│       │   ├── UL_2026_historical.csv              # 130 daily bars
│       │   ├── WMT_2026_historical.csv              # 130 daily bars
│       │   └── simulated_AAPL_2026_historical.csv # 130 daily bars
│       ├── simulation_price_data_July_1-Aug_30/ # Intraday minute data
│       │   ├── simulated_AAPL_live.csv         # Minute-level data (July-Aug 2026)
│       │   ├── simulated_GOOG_live.csv
│       │   ├── simulated_IBM_live.csv
│       │   ├── simulated_MSFT_live.csv
│       │   ├── simulated_TSLA_live.csv
│       │   ├── simulated_UL_live.csv
│       │   └── simulated_WMT_live.csv
│       └── simulation_news_data_July_1-Aug_30/    # News sentiment data
│           ├── simulated_July_news_2026.json
│           └── simulated_August_news_2026.json
├── tests/                                  # Test suite (11 test files)
│   ├── test_admin.py
│   ├── test_analytics.py
│   ├── test_auth.py
│   ├── test_genai.py
│   ├── test_kyc.py
│   ├── test_kyc_integration.py
│   ├── test_live_data.py
│   ├── test_orders.py
│   ├── test_paper_trading.py
│   ├── test_portfolio.py
│   └── test_reports.py
├── requirements.txt                         # Python dependencies
├── seed_admin.py                           # Admin account seeding script
├── migrate_add_simulation_timestamps.py  # Database migration script
├── test_market_clock.py                    # Market clock testing
└── test_session_endpoints.py             # Session endpoint testing
```

### B.2 Module Responsibilities

| Module | Responsibility | Key Functions |
|--------|---------------|---------------|
| `main.py` | Application initialization | MarketClock startup, router registration, CORS |
| `auth.py` | Authentication | User registration, JWT token generation |
| `kyc.py` | KYC workflow | Document submission, status checking |
| `admin.py` | Admin operations | KYC review, account management, session control |
| `orders.py` | Order lifecycle | Create, list, cancel, event tracking |
| `portfolio.py` | Portfolio data | Metrics, P&L, exposure, positions, lots |
| `reports.py` | Report generation | Portfolio reports, CSV export |
| `analytics.py` | Technical analysis | Indicators, alerts, sentiment divergence |
| `paper_trading.py` | Backtesting | Strategy management, backtest execution |
| `genai.py` | AI integration | Claude API client, explanations |
| `prices.py` | Price data | Latest price, intraday/daily data |
| `websockets.py` | Real-time data | Market data, session sync, notifications |
| `config.py` | Configuration | App settings, trading parameters |
| `db.py` | Database | SQLAlchemy engine, session management |
| `security.py` | Security | Password hashing, JWT validation |
| `orm.py` | Database models | Table definitions, relationships |
| `schemas.py` | API schemas | Request/response validation |
| `order_engine.py` | Order processing | Validation, execution, fills |
| `portfolio_engine.py` | Portfolio logic | Calculations, FIFO lots, exposure |
| `analytics_engine.py` | Technical indicators | SMA, EMA, RSI, MACD, Bollinger Bands |
| `backtest_engine.py` | Backtesting | Strategy execution, P&L calculation |
| `feed_simulator.py` | Market simulation | Current tick retrieval, time sync |
| `kyc_engine.py` | KYC validation | Document parsing, expiration checks |
| `genai_client.py` | AI client | Claude API integration |
| `market_clock.py` | Time management | Simulated time, speed multipliers |

---

## C. TECHNOLOGY STACK & DEPENDENCIES

### C.1 Core Frameworks
- **FastAPI** (0.100+): Modern async Python web framework
- **SQLAlchemy** (2.0+): Python SQL toolkit and ORM
- **Pydantic** (2.0+): Data validation using Python type hints
- **Uvicorn** (0.20+): ASGI server for FastAPI

### C.2 Database
- **SQLite**: Embedded database for development
- **SQLAlchemy ORM**: Database abstraction layer
- **Alembic**: Database migration tool (not currently used)

### C.3 Security
- **python-jose** (3.3+): JWT token generation and validation
- **passlib** (1.7.4+): Password hashing with bcrypt
- **python-multipart**: File upload handling

### C.4 Data Processing
- **pandas** (2.0+): Data manipulation and analysis
- **numpy**: Numerical computing
- **Pillow**: Image processing for KYC documents

### C.5 API & HTTP
- **httpx**: Async HTTP client for external API calls
- **python-multipart**: Multipart form data handling

### C.6 AI Integration
- **anthropic**: Anthropic Claude API client for GenAI features

### C.7 Development Tools
- **pytest**: Testing framework
- **pytest-asyncio**: Async test support
- **python-dotenv**: Environment variable management

### C.8 Complete requirements.txt

```
fastapi==0.100.0
uvicorn[standard]==0.20.0
sqlalchemy==2.0.0
pydantic==2.0.0
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-multipart
pandas==2.0.0
numpy
pillow
httpx
python-dotenv
anthropic
pytest
pytest-asyncio
```

---

## D. CONFIGURATION & ENVIRONMENT VARIABLES

### D.1 Configuration File (`app/core/config.py`)

```python
# Database
DATABASE_URL = "sqlite:///./trading_platform.db"

# JWT
SECRET_KEY = "your-secret-key-here"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

# Trading
ALLOWED_TICKERS = ["AAPL", "GOOG", "IBM", "MSFT", "TSLA", "UL", "WMT"]
MARKET_START_HOUR = 9
MARKET_END_HOUR = 16
MARKET_TIMEZONE = "UTC"

# Risk Controls
PRICE_COLLAR_PERCENT = 10
MAX_NOTIONAL_PER_ORDER = 250000
MAX_CONCENTRATION_PERCENT = 25
MAX_ORDERS_PER_MINUTE = 10

# Commissions
COMMISSION_FLAT_FEE = 1.0

# File Upload
MAX_FILE_SIZE_MB = 10
ALLOWED_FILE_TYPES = ["image/jpeg", "image/png", "application/pdf"]

# KYC
KYC_APPROVAL_HOURS = 24
KYC_EXPIRY_DAYS = 365

# MarketClock
DEFAULT_START_TIME = "2026-06-30T09:30:00+00:00"
DEFAULT_SPEED_MULTIPLIER = 1.0
ALLOWED_SPEED_MULTIPLIERS = [1.0, 2.0, 5.0, 12.0, 30.0]

# GenAI
ANTHROPIC_API_KEY = ""
```

### D.2 Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `DATABASE_URL` | Database connection string | sqlite:///./trading_platform.db | No |
| `SECRET_KEY` | JWT signing key | Random dev key | Yes (production) |
| `ANTHROPIC_API_KEY` | Anthropic Claude API key | "" | No (optional) |
| `LOG_LEVEL` | Logging level | INFO | No |

---

## E. DATABASE SCHEMA & ORM MODELS

### E.1 Core Tables

#### E.1.1 Account Table
```python
class Account(Base):
    __tablename__ = "accounts"
    
    id = Column(String, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(Enum(Role), default=Role.TRADER, nullable=False)
    kyc_status = Column(Enum(KYCStatus), default=KYCStatus.PENDING_SUBMISSION, nullable=False)
    starting_capital = Column(Float, default=1000000.000, nullable=False)
    cash_balance = Column(Float, default=1000000.000, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    
    # Relationships
    orders = relationship("Order", back_populates="account")
    positions = relationship("Position", back_populates="account")
    kyc_submissions = relationship("KYCSubmission", back_populates="account")
    cash_ledger = relationship("CashLedger", back_populates="account")
    market_sessions = relationship("MarketSession", back_populates="account")
```

**Indexes:**
- Primary: `id`
- Unique: `username`
- Index: `kyc_status`

#### E.1.2 Order Table
```python
class Order(Base):
    __tablename__ = "orders"
    
    id = Column(String, primary_key=True, index=True)
    account_id = Column(String, ForeignKey("accounts.id"), nullable=False)
    ticker = Column(String, nullable=False)
    side = Column(Enum(OrderSide), nullable=False)
    type = Column(Enum(OrderType), nullable=False)
    qty = Column(Integer, nullable=False)
    limit_price = Column(Float, nullable=True)
    status = Column(Enum(OrderStatus), default=OrderStatus.NEW, nullable=False)
    is_backtest = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    
    # Relationships
    account = relationship("Account", back_populates="orders")
    events = relationship("OrderEvent", back_populates="order")
    fills = relationship("Fill", back_populates="order")
```

**Enums:**
- `OrderSide`: BUY, SELL
- `OrderType`: MARKET, LIMIT
- `OrderStatus`: NEW, PENDING, PARTIAL_FILLED, FILLED, CANCELLED, REJECTED
- `Role`: TRADER, ADMIN

**Indexes:**
- Primary: `id`
- Index: `account_id`, `status`
- Index: `is_backtest`

#### E.1.3 OrderEvent Table
```python
class OrderEvent(Base):
    __tablename__ = "order_events"
    
    id = Column(String, primary_key=True, index=True)
    order_id = Column(String, ForeignKey("orders.id"), nullable=False)
    from_state = Column(Enum(OrderStatus), nullable=True)
    to_state = Column(Enum(OrderStatus), nullable=False)
    reason = Column(String, nullable=True)
    is_backtest = Column(Boolean, default=False, nullable=False)
    timestamp = Column(DateTime, default=utcnow, nullable=False)
    
    # Relationships
    order = relationship("Order", back_populates="events")
```

**Purpose:** Audit trail for order state transitions per Principle 6

#### E.1.4 Fill Table
```python
class Fill(Base):
    __tablename__ = "fills"
    
    id = Column(String, primary_key=True, index=True)
    order_id = Column(String, ForeignKey("orders.id"), nullable=False)
    fill_price = Column(Float, nullable=False)
    fill_qty = Column(Integer, nullable=False)
    fees = Column(Float, default=1.0, nullable=False)
    is_backtest = Column(Boolean, default=False, nullable=False)
    timestamp = Column(DateTime, default=utcnow, nullable=False)
    
    # Relationships
    order = relationship("Order", back_populates="fills")
```

**Purpose:** Record successful order executions

#### E.1.5 Position Table
```python
class Position(Base):
    __tablename__ = "positions"
    
    id = Column(String, primary_key=True, index=True)
    account_id = Column(String, ForeignKey("accounts.id"), nullable=False)
    ticker = Column(String, nullable=False)
    signed_qty = Column(Integer, nullable=False)
    avg_cost = Column(Float, nullable=False)
    current_price = Column(Float, nullable=False)
    market_value = Column(Float, nullable=False)
    unrealized_pnl = Column(Float, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    
    # Relationships
    account = relationship("Account", back_populates="positions")
    lots = relationship("PositionLot", back_populates="position")
```

**Purpose:** Track current holdings per ticker

#### E.1.6 PositionLot Table
```python
class PositionLot(Base):
    __tablename__="position_lots"
    
    id = Column(String, primary_key=True, index=True)
    position_id = Column(String, ForeignKey("positions.id"), nullable=False)
    qty = Column(Integer, nullable=False)
    cost = Column(Float, nullable=False)
    is_backtest = Column(Boolean, default=False, nullable=False)
    entry_time = Column(DateTime, default=utcnow, nullable=False)
    
    # Relationships
    position = relationship("Position", back_populates="lots")
```

**Purpose:** FIFO lot tracking for cost basis calculation

#### E.1.7 CashLedger Table
```python
class CashLedger(Base):
    __tablename__ = "cash_ledger"
    
    id = Column(String, primary_key=True, index=True)
    account_id = Column(String, ForeignKey("accounts.id"), nullable=False)
    amount = Column(Float, nullable=False)
    balance_after = Column(Float, nullable=False)
    transaction_type = Column(String, nullable=False)
    related_order_id = Column(String, ForeignKey("orders.id"), nullable=True)
    is_backtest = Column(Boolean, default=False, nullable=False)
    timestamp = Column(DateTime, default=utcnow, nullable=False)
    
    # Relationships
    account = relationship("Account", back_populates="cash_ledger")
```

**Purpose:** Track all cash movements

#### E.1.8 KYCSubmission Table
```python
class KYCSubmission(Base):
    __tablename__ = "kyc_submissions"
    
    id = Column(String, primary_key=True, index=True)
    account_id = Column(String, ForeignKey("accounts.id"), nullable=False)
    id_type = Column(String, nullable=False)
    document_path = Column(String, nullable=False)
    status = Column(Enum(KYCStatus), default=KYCStatus.PENDING_REVIEW, nullable=False)
    submitted_at = Column(DateTime, default=utcnow, nullable=False)
    reviewed_at = Column(DateTime, nullable=True)
    reviewer_id = Column(String, nullable=True)
    rejection_reason = Column(String, nullable=True)
    is_backtest = Column(Boolean, default=False, nullable=False)
    
    # Relationships
    account = relationship("Account", back_populates="kyc_submissions")
```

**Enums:**
- `KYCStatus`: PENDING_SUBMISSION, PENDING_REVIEW, APPROVED, REJECTED

#### E.1.9 PriceHistoryDaily Table
```python
class PriceHistoryDaily(Base):
    __tablename__ = "price_history_daily"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String, nullable=False, index=True)
    date = Column(Date, nullable=False)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Integer, nullable=False)
```

**Purpose:** Historical daily OHLCV data (130 bars per ticker)

**Indexes:**
- Primary: `id`
- Index: `ticker`, `date`

#### E.1.10 PriceHistoryMinute Table
```python
class PriceHistoryMinute(Base):
    __tablename__ = "price_history_minute"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String, nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Integer, nullable=False)
```

**Purpose:** Intraday minute-level data (July-August 2026)

**Indexes:**
- Primary: `id`
- Index: `ticker`, `timestamp`

#### E.1.11 BacktestRun Table
```python
class BacktestRun(Base):
    __tablename__ = "backtest_runs"
    
    id = Column(String, primary_key=True, index=True)
    strategy_id = Column(String, ForeignKey("backtest_strategies.id"), nullable=False)
    account_id = Column(String, ForeignKey("accounts.id"), nullable=False)
    start_timestamp = Column(DateTime, nullable=False)
    end_timestamp = Column(DateTime, nullable=False)
    initial_capital = Column(Float, nullable=False)
    final_capital = Column(PickleType, nullable=False)
    total_return = Column(Float, nullable=False)
    sharpe_ratio = Column(Float, nullable=False)
    max_drawdown = Column(Float, nullable=False)
    total_trades = Column(Integer, nullable=False)
    status = Column(String, default="completed", nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    
    # Relationships
    strategy = relationship("BacktestStrategy", back_populates="runs")
    account = relationship("Account")
```

#### E.1.12 BacktestStrategy Table
```python
class BacktestStrategy(Base):
    __tablename__ = "backtest_strategies"
    
    id = Column(String, primary_key=True, index=True)
    account_id = Column(String, ForeignKey("accounts.id"), nullable=False)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    parameters = Column(PickleType, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    
    # Relationships
    account = relationship("Account")
    runs = relationship("BacktestRun", back_populates="strategy")
```

#### E.1.13 MarketSession Table
```python
class MarketSession(Base):
    __tablename__ = "market_sessions"
    
    id = Column(String, primary_key=True, index=True)
    account_id = Column(String, ForeignKey("accounts.id"), nullable=True)
    start_timestamp = Column(DateTime, nullable=False)
    current_timestamp = Column(DateTime, nullable=False)
    speed_multiplier = Column(Float, default=1.0, nullable=False)
    market_status = Column(String, default="open", nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    
    # Relationships
    account = relationship("Account")
```

**Purpose:** Track Global MarketClock sessions for admin control

---

## F. API ENDPOINTS - COMPLETE REFERENCE

### F.1 Authentication Endpoints (`/api/auth`)

#### F.1.1 POST `/api/auth/register`
**Description:** Register new trader account
**Auth Required:** No
**Request Body:**
```json
{
  "username": "string (3-20 chars)",
  "password": "string (min 8 chars)",
  "starting_capital": 1000000.0 (optional, default 1M)"
}
```
**Response:**
```json
{
  "id": "account_uuid",
  "username": "string",
  "role": "trader",
  "kyc_status": "PENDING_SUBMISSION",
  "cash_balance": 1000000.0,
  "created_at": "2026-06-30T09:30:00Z"
}
```

#### F.1.2 POST `/api/auth/login`
**Description:** Login and receive JWT token
**Auth Required:** No
**Request Body:**
```json
{
  "username": "string",
  "password": "string"
}
```
**Response:**
```json
{
  "access_token": "jwt_token_string",
  "token_type": "bearer",
  "role": "trader" | "admin"
}
```

#### F.1.3 GET `/api/auth/me`
**Description:** Get current authenticated user info
**Auth Required:** Yes (JWT)
**Response:**
```json
{
  "id": "account_uuid",
  "username": "string",
  "role": "trader" | "admin",
  "kyc_status": "APPROVED" | "PENDING_SUBMISSION" | "PENDING_REVIEW" | "REJECTED",
  "cash_balance": 1000000.0,
  "created_at": "2026-06-30T09:30:00Z"
}
```

---

### F.2 KYC Endpoints (`/api/kyc`)

#### F.2.1 POST `/api/kyc/submit`
**Description:** Submit KYC document for verification
**Auth Required:** Yes (JWT)
**Request:** multipart/form-data
- `id_type`: "passport" | "drivers_license" | "national_id"
- `id_document`: File (JPEG, PNG, PDF, max 10MB)
**Response:**
```json
{
  "id": "kyc_uuid",
  "account_id": "account_uuid",
  "id_type": "passport",
  "status": "PENDING_REVIEW",
  "submitted_at": "2026-06-30T09:30:00Z"
}
```

#### F.2.2 GET `/api/kyc/status`
**Description:** Get current KYC status
**Auth Required:** Yes (JWT)
**Response:**
```json
{
  "status": "APPROVED" | "PENDING_SUBMISSION" | "PENDING_REVIEW" | "REJECTED",
  "submission_id": "kyc_uuid" (if submitted),
  "rejection_reason": "string" (if rejected)
}
```

---

### F.3 Admin Endpoints (`/api/admin`)

#### F.3.1 GET `/api/admin/kyc`
**Description:** Get KYC submission queue
**Auth Required:** Yes (Admin role)
**Query Parameters:**
- `status_filter`: "PENDING_REVIEW" (default), "APPROVED", "REJECTED"
**Response:**
```json
[
  {
    "id": "kyc_uuid",
    "account_id": "account_uuid",
    "username": "trader1",
    "id_type": "passport",
    "status": "PENDING_REVIEW",
    "submitted_at": "2026-06-30T09:30:00Z"
  }
]
```

#### F.3.2 GET `/api/admin/kyc/{submission_id}`
**Description:** Get specific KYC submission details
**Auth Required:** Yes (Admin role)
**Response:**
```json
{
  "id": "kyc_uuid",
  "account_id": "account_uuid",
  "username": "trader1",
  "id_type": "passport",
  "document_path": "/path/to/document.pdf",
  "status": "PENDING_REVIEW",
  "submitted_at": "2026-06-30T09:30:00Z",
  "reviewed_at": null,
  "reviewer_id": null,
  "rejection_reason": null
}
```

#### F.3.3 POST `/api/admin/kyc/{submission_id}/approve`
**Description:** Approve KYC submission
**Auth Required:** Yes (Admin role)
**Request Body:**
```json
{
  "reviewer_id": "admin_uuid" (optional)
}
```
**Response:**
```json
{
  "id": "kyc_uuid",
  "status": "APPROVED",
  "reviewed_at": "2026-06-30T10:00:00Z",
  "reviewer_id": "admin_uuid"
}
```

#### F.3.4 POST `/api/admin/kyc/{submission_id}/reject`
**Description:** Reject KYC submission
**Auth Required:** Yes (Admin role)
**Request Body:**
```json
{
  "rejection_reason": "Document unclear/incomplete",
  "reviewer_id": "admin_uuid" (optional)
}
```
**Response:**
```json
{
  "id": "kyc_uuid",
  "status": "REJECTED",
  "reviewed_at": "2026-06-30T10:00:00Z",
  "reviewer_id": "admin_uuid",
  "rejection_reason": "Document unclear/incomplete"
}
```

#### F.3.5 GET `/api/admin/accounts`
**Description:** Get all accounts overview
**Auth Required:** Yes (Admin role)
**Response:**
```json
[
  {
    "id": "account_uuid",
    "username": "trader1",
    "role": "trader",
    "kyc_status": "APPROVED",
    "cash_balance": 1000000.0,
    "created_at": "2026-06-30T09:30:00Z"
  }
]
```

#### F.3.6 GET `/api/admin/audit-logs`
**Description:** Get audit logs with filtering
**Auth Required:** Yes (Admin role)
**Query Parameters:**
- `account_id`: Optional account filter
- `ticker`: Optional ticker filter
- `from_`: Optional datetime (YYYY-MM-DD HH:MM:SS)
- `to_`: Optional datetime (YYYY-MM-DD HH:MM:SS)
- `reason_code`: Optional reason code filter
- `include_backtest`: Boolean (default: false)
**Response:**
```json
[
  {
    "id": "event_uuid",
    "account_id": "account_uuid",
    "username": "trader1",
    "ticker": "AAPL",
    "action": "ORDER_CREATED",
    "details": "BUY 100 AAPL @ $150.00",
    "reason_code": "ORDER_CREATED",
    "timestamp": "2026-06-30T09:30:00Z",
    "is_backtest": false
  }
]
```

#### F.3.7 GET `/api/admin/trade-logs`
**Description:** Get trade execution logs
**Auth Required:** Yes (Admin role)
**Query Parameters:**
- `account_id`: Optional account filter
- `ticker`: Optional ticker filter
- `from_`: Optional datetime filter
- `to_`: Optional datetime filter
**Response:**
```json
[
  {
    "id": "order_uuid",
    "account_id": "account_uuid",
    "username": "trader1",
    "ticker": "AAPL",
    "side": "BUY",
    "qty": 100,
    "limit_price": 150.0,
    "status": "FILLED",
    "fill_price": 150.25,
    "timestamp": "2026-06-30T09:30:00Z"
  }
]
```

#### F.3.8 GET `/api/admin/flags`
**Description:** Get compliance flags
**Auth Required:** Yes (Admin role)
**Response:**
```json
[
  {
    "id": "flag_uuid",
    "account_id": "account_uuid",
    "username": "trader1",
    "flag_type": "WASH_TRADE_FLAGGED",
    "description": "Detected wash-trade pattern",
    "order_id": "order_uuid",
    "timestamp": "2026-06-30T09:30:00Z"
  }
]
```

#### F.3.9 POST `/api/admin/feed/reset`
**Description:** Reset feed simulator to start of dataset
**Auth Required:** Yes (Admin role)
**Response:**
```json
{
  "message": "Feed simulator reset to start of dataset",
  "cache_info": {...},
  "system_time": "2026-06-30T09:30:00Z"
}
```

#### F.3.10 GET `/api/admin/feed/status`
**Description:** Get feed simulator status (MarketClock-based)
**Auth Required:** Yes (Admin role)
**Response:**
```json
{
  "market_clock": {
    "session_id": "session_uuid",
    "simulated_time": "2026-06-30T09:30:00Z",
    "speed_multiplier": 1.0,
    "market_status": "open",
    "is_running": true
  },
  "system_time": "2026-06-30T09:30:00Z",
  "running": true
}
```

#### F.3.11 POST `/api/admin/session/time`
**Description:** Set simulated session time
**Auth Required:** Yes (Admin role)
**Request Body:**
```json
{
  "date": "2026-07-15",
  "time": "09:15:00"
}
```
**Response:**
```json
{
  "session_id": "session_uuid",
  "simulated_time": "2026-07-15T09:15:00Z",
  "speed_multiplier": 1.0,
  "market_status": "open"
}
```

#### F3.12 POST `/api/admin/session/reset`
**Description:** Reset session to start of dataset
**Auth Required:** Yes (Admin role)
**Response:**
```json
{
  "session_id": "new_session_uuid",
  "simulated_time": "2026-06-30T09:30:00Z",
  "speed_multiplier": 1.0,
  "market_status": "open"
}
```

#### F.3.13 POST `/api/admin/session/speed`
**Description:** Set speed multiplier
**Auth Required:** Yes (Admin role)
**Request Body:**
```json
{
  "multiplier": 1 | 2 | 5 | 12 | 30
}
```
**Response:**
```json
{
  "session_id": "session_uuid",
  "simulated_time": "2026-06-30T09:30:00Z",
  "speed_multiplier": 2.0,
  "market_status": "open"
}
```

#### F3.14 GET `/api/admin/session/status`
**Description:** Get current session status
**Auth Required:** Yes (Admin role)
**Response:**
```json
{
  "session_id": "session_uuid",
  "simulated_time": "2026-06-30T09:30:00Z",
  "speed_multiplier": 1.0,
  "market_status": "open",
  "is_running": true
}
```

---

### F.4 Order Endpoints (`/api/orders`)

#### F.4.1 POST `/api/orders/`
**Description:** Create new order
**Auth Required:** Yes (JWT, KYC approved)
**Request Body:**
```json
{
  "ticker": "AAPL",
  "side": "buy" | "sell",
  "type": "market" | "limit",
  "quantity": 100,
  "limit_price": 150.0 (required for limit orders),
  "time_in_force": "DAY"
}
```
**Response:**
```json
{
  "id": "order_uuid",
  "account_id": "account_uuid",
  "ticker": "AAPL",
  "side": "BUY",
  "type": "MARKET",
  "qty": 100,
  "limit_price": null,
  "status": "NEW",
  "created_at": "2026-06-30T09:30:00Z"
}
```

**Order Validation Chain (ordered):**
1. KYC status must be APPROVED
2. Ticker must be in ALLOWED_TICKERS
3. Must be within market hours (9:30 AM - 4:00 PM UTC)
4. Price collar check (±10% of current price)
5. Notional cap check (max $250,000 per order)
6. Concentration limit check (max 25% of net worth)
7. Cash/collateral availability check
8. Rate limit check (max 10 orders/minute)
9. Wash-trade pattern detection

#### F4.2 GET `/api/orders/`
**Description:** Get all user orders
**Auth Required:** Yes (JWT)
**Query Parameters:**
- `status`: Optional status filter
- `ticker`: Optional ticker filter
- `is_backtest`: Boolean filter
**Response:**
```json
[
  {
    "id": "order_uuid",
    "ticker": "AAPL",
    "side": "BUY",
    "type": "MARKET",
    "qty": 100,
    "limit_price": null,
    "status": "FILLED",
    "fill_price": 150.25,
    "is_backtest": false,
    "created_at": "2026-06-30T09:30:00Z"
  }
]
```

#### F4.3 GET `/api/orders/{order_id}`
**Description:** Get specific order details
**Auth Required:** Yes (JWT)
**Response:**
```json
{
  "id": "order_uuid",
  "account_id": "account_uuid",
  "ticker": "AAPL",
  "side": "BUY",
  "type": "MARKET",
  "qty": 100,
  "limit_price": null,
  "status": "FILLED",
  "fill_price": 150.25,
  "is_backtest": false,
  "created_at": "2026-06-30T09:30:00Z"
}
```

#### F4.4 DELETE `/api/orders/{order_id}`
**Description:** Cancel pending order
**Auth Required:** Yes (JWT)
**Response:**
```json
{
  "id": "order_uuid",
  "status": "CANCELLED",
  "cancelled_at": "2026-06-30T09:31:00Z"
}
```

#### F4.5 GET `/api/orders/{order_id}/events`
**Description:** Get order event trail
**Auth Required:** Yes (JWT)
**Response:**
```json
[
  {
    "id": "event_uuid",
    "order_id": "order_uuid",
    "from_state": "NEW",
    "to_state": "PENDING",
    "reason": "ORDER_CREATED",
    "timestamp": "2026-06-30T09:30:00Z"
  },
  {
    "id": "event_uuid",
    "order_id": "order_uuid",
    "from_state": "PENDING",
    "to_state": "FILLED",
    "reason": "ORDER_FILLED",
    "timestamp": "2026-06-30T09:30:00Z"
  }
]
```

---

### F.5 Portfolio Endpoints (`/api/portfolio`)

#### F5.1 GET `/api/portfolio/`
**Description:** Get portfolio summary metrics
**Auth Required:** Yes (JWT)
**Response:**
```json
{
  "net_worth": 1000000.0,
  "cash_balance": 500000.0,
  "market_value": 500000.0,
  "unrealized_pnl": 25000.0,
  "realized_pnl": -1000.0,
  "positions": [
    {
      "ticker": "AAPL",
      "signed_qty": 100,
      "avg_cost": 140.0,
      "current_price": 150.0,
      "market_value": 15000.0,
      "unrealized_pnl": 1000.0
    }
  ]
}
```

#### F5.2 GET `/api/portfolio/pnl`
**Description:** Get P&L breakdown
**Auth Required:** Yes (JWT)
**Response:**
```json
{
  "daily_pnl": 5000.0,
  "daily_pnl_pct": 0.5,
  "total_pnl": 5000.0,
  "total_pnl_pct": 0.5,
  "realized_pnl": -1000.0,
  "unrealized_pnl": 6000.0
}
```

#### F5.3 GET `/api/portfolio/exposure`
**Description:** Get exposure by ticker/sector
**Auth Required:** Yes (JWT)
**Response:**
```json
{
  "ticker_exposure": {
    "AAPL": {
      "ticker": "AAPL",
      "quantity": 100,
      "avg_cost": 140.0,
      "current_price": 150.0,
      "market_value": 15000.0,
      "unrealized_pnl": 1000.0,
      "percentage": 1.5
    }
  },
  "sector_exposure": {
    "Technology": {
      "percentage": 50.0,
      "tickers": ["AAPL", "GOOG", "MSFT"]
    }
  }
}
```

#### F5.4 GET `/api/portfolio/positions`
**Description:** Get all open positions
**Auth Required:** Yes (JWT)
**Response:**
```json
[
  {
    "id": "position_uuid",
    "ticker": "AAPL",
    "signed_qty": 100,
    "avg_cost": 140.0,
    "current_price": 150.0,
    "market_value": 15000.0,
    "unrealized_pnl": 1000.0
  }
]
```

#### F5.5 GET `/api/portfolio/{ticker}/lots`
**Description:** Get FIFO lots for ticker
**Auth Required:** Yes (JWT)
**Response:**
```json
[
  {
    "id": "lot_uuid",
    "qty": 50,
    "cost": 135.0,
    "entry_time": "2026-06-30T09:30:00Z"
  },
  {
    "id": "lot_uuid",
    "qty": 50,
    "cost": 145.0,
    "entry_time": "2026-06-30T10:00:00Z"
  }
]
```

---

### F.6 Reports Endpoints (`/api/reports`)

#### F6.1 GET `/api/reports/portfolio`
**Description:** Generate portfolio report
**Auth Required:** Yes (JWT)
**Response:**
```json
{
  "report_id": "report_uuid",
  "generated_at": "2026-06-30T09:30:00Z",
  "period": "last_30_days",
  "metrics": {...},
  "positions": [...],
  "performance": {...}
```

#### F6.2 GET `/api/reports/portfolio/export`
**Description:** Export portfolio as CSV
**Auth Required:** Yes (JWT)
**Query Parameters:**
- `format`: "csv" (only format supported)
**Response:** CSV file download

---

### F.7 Analytics Endpoints (`/api/analytics`)

#### F7.1 GET `/api/analytics/{ticker}/indicators`
**Description:** Get technical indicators for ticker
**Auth Required:** Yes (JWT)
**Response:**
```json
{
  "ticker": "AAPL",
  "indicators": {
    "sma_20": 148.5,
    "sma_50": 145.2,
    "ema_12": 149.2,
    "ema_26": 147.8,
    "rsi_14": 65.0,
    "macd": {
      "macd": 0.5,
      "signal": 0.3,
      "histogram": [...]
    },
    "bollinger_bands": {
      "upper": 152.0,
      "middle": 148.5,
      "lower": 145.0
    }
  }
}
```

#### F7.2 GET `/api/analytics/{ticker}/alerts`
**Description:** Get technical analysis alerts
**Auth Required:** Yes (JWT)
**Response:**
```json
{
  "ticker": "AAPL",
  "alerts": [
    {
      "type": "RSI_OVERBOUGHT",
      "message": "RSI above 70 - overbought condition",
      "timestamp": "2026-06-30T09:30:00Z"
    },
    {
      "type": "PRICE_BREAKOUT",
      "message": "Price above upper Bollinger Band",
      "timestamp": "2026-06-30T09:30:00Z"
    }
  ]
}
```

#### F7.3 GET `/api/analytics/{ticker}/sentiment-divergence`
**Description:** Check sentiment divergence
**Auth Required:** Yes (JWT)
**Query Parameters:**
- `date`: YYYY-MM-DD format
**Response:**
```json
{
  "ticker": "AAPL",
  "date": "2026-07-15",
  "sentiment_score": 0.7,
  "price_change": 0.05,
  "divergence_detected": false
}
```

---

### F.8 Paper Trading Endpoints (`/api/paper-trading`)

#### F8.1 POST `/api/paper-trading/strategies`
**Description:** Create backtest strategy
**Auth Required:** Yes (JWT)
**Request Body:**
```json
{
  "name": "MA Crossover Strategy",
  "description": "Buy when SMA_20 crosses above SMA_50",
  "parameters": {
    "short_term_period": 20,
    "long_term_period": 50
  }
}
```
**Response:**
```json
{
  "id": "strategy_uuid",
  "name": "MA Crossover Strategy",
  "parameters": {...},
  "created_at": "2026-06-30T09:30:00Z"
}
```

#### F8.2 GET `/api/paper-trading/strategies`
**Description:** List all strategies
**Auth Required:** Yes (JWT)
**Response:**
```json
[
  {
    "id": "strategy_uuid",
    "name": "MA Crossover Strategy",
    "description": "Buy when SMA_20 crosses above SMA_50",
    "created_at": "2026-06-30T09:30:00Z"
  }
]
```

#### F8.3 GET `/api/paper-trading/backtest`
**Description:** List backtest runs
**Auth Required:** Yes (JWT)
**Response:**
```json
[
  {
    "id": "run_uuid",
    "strategy_id": "strategy_uuid",
    "account_id": "account_uuid",
    "start_timestamp": "2026-06-30T09:30:00Z",
    "end_timestamp": "2026-07-30T16:00:00Z",
    "status": "completed",
    "total_return": 0.15,
    "sharpe_ratio": 1.2,
    "created_at": "2026-06-30T09:30:00Z"
  }
]
```

#### F8.4 POST `/api/paper-trading/backtest/{strategy_id}/run`
**Description:** Run backtest for strategy
**Auth Required:** Yes (JWT)
**Request Body:**
```json
{
  "start_date": "2026-07-01",
  "end_date": "2026-07-30"
}
```
**Response:**
```json
{
  "id": "run_uuid",
  "strategy_id": "strategy_uuid",
  "start_timestamp": "2026-07-01T09:30:00Z",
  "end_timestamp": "2026-07-30T16:00:00Z",
  "status": "in_progress"
}
```

#### F8.5 GET `/api/paper-trading/backtest/{run_id}/results`
**Description:** Get backtest results
**Auth Required:** Yes (JWT)
**Response:**
```json
{
  "id": "run_uuid",
  "strategy_id": "strategy_uuid",
  "initial_capital": 1000000.0,
  "final_capital": 1150000.0,
  "total_return": 0.15,
  "sharpe_ratio": 1.2,
  "max_drawdown: -0.05,
  "total_trades": 45,
  "win_rate": 0.67,
  "trade_log": [...]
}
```

---

### F.9 GenAI Endpoints (`/api/genai`)

#### F9.1 POST `/api/genai/portfolio-summary`
**Description:** Get AI portfolio summary
**Auth Required:** Yes (JWT)
**Response:**
```json
{
  "summary": "Portfolio shows bullish bias with concentration in Technology sector. Current allocation is 45% Technology, 30% Healthcare, 25% Consumer Discretionary. Risk level: Moderate. Consider diversification for reduced volatility.",
  "generated_at": "2026-06-30T09:30:00Z"
}
```

#### F9.2 POST `/api/genai/explain/{ticker}`
**Description: Get AI explanation for ticker performance
**Auth Required:** Yes (JWT)
**Response:```json
{
  "ticker": "AAPL",
  "explanation": "AAPL shows strong upward momentum with higher highs and higher lows. RSI indicates overbought conditions. Recent news sentiment is positive. Current trend: Bullish.",
  "generated_at": "2026-06-30T09:30:00Z"
}
```

#### F9.3 POST `/api/genai/extract-id`
**Description: Extract security identifier from text
**Auth Required:** Yes (JWT)
**Request Body:**
```json
{
  "text": "Portfolio analysis shows XYZ performance..."
}
```
**Response:**
```json
{
  "account_id": "ACC123",
  "ticker": "XYZ",
  "confidence": 0.95
}
```

#### F9.4 POST `/api/genai/parse-order`
**Description: Parse natural language order request
**Auth Required:** Yes (JWT)
**Request Body:**
```json
{
  "text": "Buy 100 shares of AAPL at market"
}
```
**Response:```json
{
  "ticker": "AAPL",
  "side": "buy",
  "type": "market",
  "quantity": 100,
  "confidence": 0.98
}
```

#### F9.5 POST `/api/genai/explain-rejection`
**Description: Get AI explanation for order rejection
**Auth Required:** Yes (JWT)
**Request Body:```json
{
  "order_id": "order_uuid",
  "rejection_reason": "KYC_NOT_APPROVED"
}
```
**Response:**
```json
{
  "explanation": "Order rejected because KYC status is not approved. Users must complete KYC verification before trading. Submit identification documents for approval.",
  "recommendation": "Submit KYC documents via /api/kyc/submit"
}
```

---

### F.10 Price Data Endpoints (`/api/prices`)

#### F10.1 GET `/api/prices/{ticker}/latest`
**Description:** Get current minute-level price snapshot
**Auth Required:** No
**Response:**
```json
{
  "ticker": "AAPL",
  "timestamp": "2026-07-01 09:31:00",
  "open": 224.1013,
  "high": 224.2407,
  "low": 223.952,
  "close": 224.0714,
  "volume": 106824,
  "system_time": "2026-06-30T09:30:00Z"
}
```

#### F10.2 GET `/api/prices/{ticker}/intraday`
**Description:** Get intraday OHLCV data with resampling
**Auth Required:** No
**Query Parameters:**
- `interval`: "1m" | "5m" | "15m" | "60m" (default: "5m")
**Response:**
```json
[
  {
    "timestamp": "2026-07-01 09:31:00",
    "open": 224.1013,
    "high": 224.2407,
    "low": 223.952,
    "close": 224.0714,
    "volume": 106824
  }
]
```

#### F10.3 GET `/api/prices/{ticker}/daily`
**Description:** Get daily OHLCV data
**Auth Required:** No
**Response:**
```json
[
  {
    "date": "2026-06-23",
    "open": 211.0,
    "high": 215.0,
    "low": 209.0,
    "close": 214.0,
    "volume": 50000000
  }
]
```

#### F10.4 GET `/api/prices/market/current`
**Description:** Get current prices for all tickers
**Auth Required:** No
**Response:**
```json
{
  "AAPL": {
    "timestamp": "2026-07-01 09:31:00",
    "open": 224.1013,
    "high": 224.2407,
    "low": 223.962,
    "close": 224.0714,
    "volume": 106824
  },
  "GOOG": {...},
  "IBM": {...},
  "MSFT": {...},
  "TSLA": {...},
  "UL": {...},
  "WMT": {...},
  "system_time": "2026-06-30T09:30:00Z"
}
```

---

## G. WEBSOCKET ARCHITECTURE

### G.1 WebSocket Endpoints

#### G.1.1 WS `/ws/market/{ticker}` (PUBLIC)
**Purpose:** Stream real-time market data for specific ticker
**Update Frequency:** Every 1 minute (60 seconds)
**Message Format:**
```json
{
  "type": "tick",
  "timestamp": "2026-07-01 09:31:00Z",
  "ticker": "AAPL",
  "price": 224.0714,
  "open": 224.1013,
  "high": 224.2407,
  "low": 223.952,
  "volume": 106824,
  "change": 0.5,
  "change_percent": 0.22
}
```

**Flow:**
1. Client connects to WebSocket
2. Server accepts connection
3. Server queries feed simulator for current tick at MarketClock time
4. Server sends tick every 60 seconds
5. Client updates charts/tables with new data

#### G1.2 WS `/ws/session` (PUBLIC)
**Purpose:** Global session synchronization for all clients
**Update Frequency:** Every 1 second
**Message Format:**
```json
{
  "type": "market/session/update",
  "simulated_time": "2026-07-15T09:30:00Z",
  "speed_multiplier": 2.0,
  "market_status": "open",
  "session_id": "session_abc123"
}
```

**Flow:**
1. Client connects to WebSocket
2. Server sends initial session status
3. Server broadcasts MarketClock status every second
4. All clients receive synchronized time
5. Frontend displays time indicator with live updates

#### G1.3 WS `/ws/account/{account_id}` (AUTHENTICATED)
**Purpose:** Account-specific updates and notifications
**Message Formats:**
```json
// Order execution
{
  "type": "order_execution",
  "order_id": "order_uuid",
  "status": "FILLED",
  "fill_price": 150.25,
  "timestamp": "2026-06-30T09:30:00Z"
}

// Position update
{
  "type": "position_update",
  "ticker": "AAPL",
  "signed_qty": 100,
  "market_value": 15000.0,
  "unrealized_pnl": 1000.0,
  "timestamp": "2026-06-30T09:30:00Z"
}
```

#### G1.4 WS `/ws/admin/notifications` (ADMIN ONLY)
**Purpose:** Admin console system status and notifications
**Update Frequency:** Every 30 seconds
**Message Formats:**
```json
// System status
{
  "type": "admin_notification",
  "timestamp": "2026-06-30T09:30:00Z",
  "message": "System operational",
  "severity": "info",
  "market_clock": {
    "session_id": "session_abc123",
    "simulated_time": "2026-06-30T09:30:00Z",
    "speed_multiplier": 1.0,
    "market_status": "open"
  }
}

// New KYC submission
{
  "type": "new_kyc_submission",
  "submission_id": "kyc_552",
  "account_id": "acc_777",
  "timestamp": "2026-06-30T09:05:00Z"
}

// Compliance flag
{
  "type": "compliance_flag",
  "flag_type": "WASH_TRADE_FLAGGED",
  "account_id": "acc_123",
  "order_id": "ord_9a1b",
  "timestamp": "2026-06-30T10:20:00Z"
}
```

### G.2 WebSocket Connection Management

#### G.2.1 Client-Side Connection Pattern
```typescript
// MarketDataManager (useMarketData.ts)
- Single connection per ticker
- Automatic reconnection after 5 seconds
- Proper cleanup on component unmount
- Prevents duplicate connections
- Ticker-specific connection management
```

#### G.2.2 Server-Side Connection Handling
```python
# Each WebSocket endpoint has:
- Connection acceptance
- Message parsing and error handling
- Connection closure handling
- Periodic data broadcasting
- State management
```

---

## H. SERVICES & BUSINESS LOGIC

### H.1 Order Engine (`order_engine.py`)

#### H.1.1 Core Functions

**`validate_order(order: Order, db: Session) -> None`**
- Performs all 9 validation checks in order
- Raises HTTPException with specific error codes
- Logs rejection reasons to audit log

**`create_order(order: Order, db: Session) -> Order`**
- Creates order in database
- Creates initial ORDER_CREATED event
- Trigger order processing

**`process_order(order: Order, db: Session) -> None`**
- Checks market hours (9:30 AM - 4:00 PM UTC)
- Fetches current price from feed simulator
- Checks if already have matching order to flip position
- Executes order via `fill_order()`

**`fill_order(order: Order, synthetic_prices: Dict, db: Session) -> Fill`**
- Calculates fill cost with commission
- Updates account cash balance
- Creates fill record
- Updates position using FIFO lots
- Records ORDER_FILLED event

**`flip_position(existing_order: Order, new_order: Order, db: Session) -> None`**
- Calculates P&L from position flip
- Updates position with new qty
- Records lot for unrealized P&L
- Records POSITION_FLIP event

**`calculate_position_with_lots(position: Position, new_qty: int, fill_price: float, db: Session) -> Position`**
- Handles FIFO lot logic
- Calculates weighted average cost
- Updates position market value
- Calculates unrealized P&L

**`create_order_event(order_id: str, from_status: OrderStatus, to_status: OrderStatus, event_type: str, notes: Optional[str] = None) -> OrderEvent`**
- Creates order event for audit trail
- Records reason code for state transitions
- Timestamps from MarketClock

**Functions Using MarketClock:**
- `create_order_event()` - Uses `market_clock.now()` for timestamps
- `fill_order()` - Uses `market_clock.now()` for timestamps

---

### H.2 Portfolio Engine (`portfolio_engine.py`)

#### H.2.1 Core Functions

**`get_latest_market_price(db: Session, ticker: Optional[str]) -> Optional[float]`**
- Fetches current price from feed simulator
- Returns null if ticker not found

**`get_latest_market_prices(db: Session) -> Dict[str, float]`
- Gets current prices for all 7 tickers
- Returns dictionary mapping ticker -> close price

**`calculate_portfolio_metrics(db: Session, account_id: str) -> PortfolioMetrics`
- Calculates net worth, cash balance, market value
- Calculates unrealized and realized P&L
- Returns all open positions with metrics

**`calculate_portfolio_pnl(db: Session, account_id: str) -> PortfolioPnL`
- Calculates daily and total P&L
- Calculates daily and total P&L percentages
- Returns realized and unrealized components

**`calculate_portfolio_exposure(db: Session, account_id: str) -> PortfolioExposure`
- Calculates exposure by ticker
- Calculates exposure by sector
- Returns exposure percentages

**`update_position_with_lots(position: Position, new_qty: int, fill_price: float, db: Session) -> Position`**
- Uses FIFO lot logic for cost basis
- Updates position with new quantity
- Recalculates unrealized P&L
- Records new lot or releases old lots

**`update_cash_ledger(account_id: str, amount: float, transaction_type: str, related_order_id: Optional[str], db: Session) -> None`**
- Records cash movements
- Updates account cash balance
- Links to order execution when applicable

**Functions Using MarketClock:**
- All functions can be adapted to use MarketClock time for simulation timestamps

---

### H.3 Analytics Engine (`analytics_engine.py`)

#### H.3.1 Technical Indicators

**`calculate_sma(prices: List[float], period: int) -> float`**
- Simple Moving Average calculation
- Uses last N prices

**`calculate_ema(prices: List[float], period: int) -> float`**
- Exponential Moving Average calculation
- Uses smoothing factor α = 2/(period+1)

**`calculate_rsi(prices: List[float], period: int = 14) -> float`**
- Relative Strength Index calculation
- Uses Wilder's smoothing

**`calculate_macd(prices: List[float], fast_period: int = 12, slow_period: int = 26, signal_period: int = 9) -> Dict`
- MACD line calculation
- Signal line calculation
- Histogram calculation
- Returns dict with macd, signal, histogram

**`calculate_bollinger_bands(prices: List[float], period: int = 20, std_dev: float = 2.0) -> Dict`
- Middle band (SMA)
- Upper band (SMA + 2 std dev)
- Lower band (SMA - 2 std dev)
- Returns dict with upper, middle, lower bands

**`calculate_atr(prices: List[float], period: int = 14) -> float`
- Average True Range calculation
- Measures volatility

**`calculate_vwap(prices: List[float], volumes: List[int]) -> float`**
- Volume Weighted Average Price
- Returns VWAP value

**`calculate_ichimoku(cloud: List[float]...) -> Dict`**
- Ichimoku Cloud calculation
- Returns tenkan-sen span and cloud lines

---

### H.4 Backtest Engine (`backtest_engine.py`)

#### H.4.1 Core Functions

**`run_backtest(strategy: BacktestStrategy, start_date: str, end_date: str, db: Session) -> BacktestRun`
- Loads historical data for strategy period
- Executes strategy logic
- Simulates order execution
- Calculates performance metrics
- Returns BacktestRun with results

**`calculate_backtest_metrics(trades: List[Dict], initial_capital: float) -> Dict`
- Calculates total return
- Calculates Sharpe ratio
- Calculates maximum drawdown
- Calculates win rate
- Returns performance metrics dict

**Functions Using MarketClock:**
- All backtest functions can be adapted to use MarketClock time for simulation timestamps

---

### H.5 Feed Simulator (`feed_simulator.py`)

#### H5.1 Core Functions

**`get_current_tick_for_ticker(ticker: str, db: Session) -> Optional[Dict]`**
- Gets current tick for ticker based on MarketClock time
- Queries database directly (no caching)
- 5-minute window query for efficiency
- Returns OHLCV data point or None

**`get_all_current_ticks(db: Session) -> Dict[str, Dict]`
- Gets current ticks for all 7 tickers
- Returns dictionary mapping ticker -> OHLCV data

**`get_tick_for_ticker_at_time(ticker: str, target_time: datetime, db: Session) -> Optional[Dict]`
- Gets specific tick at target timestamp
- Used for historical queries and backtesting
- Returns closest tick within 5-minute window

**`reset_feed_simulator() -> None`**
- Resets to start of dataset
- Also resets MarketClock to start time
- Records reset in audit log

**Functions Using MarketClock:**
- `get_current_tick_for_ticker()` - Uses `market_clock.now()` for simulated time
- All feed simulator functions now use MarketClock time source

---

### H.6 KYC Engine (`kyc_engine.py`)

#### H.6.1 Core Functions

**`validate_kyc_document(file_data: bytes, file_type: str) -> Dict`
- Validates document type and size
- Checks file size limit (10MB)
- Returns validation result

**`extract_document_metadata(file_data: bytes, file_type: str) -> Dict`
- Extracts metadata from document
- Returns ID number, name, expiry, etc.

**`check_document_expiry(expiry_date: str) -> bool`
- Checks if document is expired
- Returns True if expired, False if valid

**`is_expiring_soon(expiry_date: str, days_threshold: int = 30) -> bool`
- Checks if document expires within threshold
- Returns True if expiring soon

---

### H.7 GenAI Client (`genai_client.py`)

#### H7.1 Core Functions

**`generate_portfolio_summary(db: Session, account_id: str) -> str`
- Fetches portfolio data
- Constructs prompt for Claude
- Calls Anthropic Claude API
- Returns AI-generated summary

**`explain_ticker_performance(ticker: str, db: Session) -> str`
- Fetches historical price data
- Fetches news sentiment data
- Constructs prompt for Claude
- Returns AI explanation

**`extract_account_id(text: str) -> Dict`
- Parses text for account IDs
- Returns account_id with confidence score

**`parse_natural_language_order(text: str) -> Dict`
- Parses natural language order request
- Returns parsed order parameters

**explain_order_rejection(order_id: str, rejection_reason: str, db: Session) -> str`
- Fetches order context
- Constructs prompt for Claude
- Returns AI explanation

**`generate_text_with_claude(prompt: str) -> str`
- Calls Anthropic Claude API
- Returns generated text response

---

### H.8 Market Clock (`market_clock.py`)

#### H.8.1 Core Functions

**`get_market_clock() -> MarketClock`**
- Returns singleton MarketClock instance
- Thread-safe singleton pattern
- Auto-initializes on first call

**`__init__(MarketClock.__init__(self)`**
- Initializes with default start time (2026-06-30 09:30:00 UTC)
- Sets default speed multiplier (1.0)
- Sets default market status (open)
- Creates unique session ID

**`now() -> datetime`**
- Returns current simulated time based on:
  - Start time + (elapsed seconds * speed multiplier)
- Thread-safe with lock
- UTC timezone

**`set_time(target_time: datetime) -> None`**
- Sets simulated time to target
- Resets elapsed seconds counter
- Updates market status based on time of day

**`set_speed_multiplier(multiplier: float) -> None`**
- Validates multiplier (1.0, 2.0, 5.0, 12.0, 30.0)
- Updates speed multiplier
- Broadcasts update via WebSocket

**`reset() -> None`**
- Resets to default start time
- Resets speed multiplier to 1.0
- Resets market status to "open"
- Broadcasts reset via WebSocket

**`get_status() -> Dict`**
- Returns current session state
- Includes: session_id, simulated_time, speed_multiplier, market_status, is_running

**`start() -> None`**
- Starts background time advancement thread
- Updates simulated time every second
- Advances time by speed multiplier

**`stop() -> None`**
- Stops background thread
- Pauses time advancement

**`_time_advancement_loop()`
- Background thread function
- Advances time every second
- Updates market status based on time of day
- Checks for pre-market (9:00-9:30), open (9:30-16:00), closed (16:00+)

---

## I. DATA FLOW & ARCHITECTURE PATTERNS

### I.1 Order Processing Flow

```
Client Request → API Order Endpoint
    ↓
validate_order() (9 validation checks)
    ↓
Create Order in Database
    ↓
process_order()
    ↓
check_market_hours()
    ↓
get_current_tick_for_ticker() (MarketClock time)
    ↓
check_existing_position_flip()
    ↓
fill_order()
    ↓
update_position_with_lots()
↓
update_cash_ledger()
↓
create_order_event() (MarketClock timestamp)
↓
return Order to client
```

### I.2 WebSocket Data Flow

```
MarketClock (every second)
    ↓
Session WebSocket (/ws/session)
    ↓
All Clients
    ↓
MarketTimeIndicator displays time
```

```
MarketClock (every minute)
    ↓
get_current_tick_for_ticker() (MarketClock time)
    ↓
Market WebSocket (/ws/market/{ticker})
    ↓
All Charts/Portfolios
    ↓
Live price updates
```

### I.3 Portfolio Update Flow

```
WebSocket receives price update
    ↓
useMarketData Hook
    ↓
setRealtimePrices state
    ↓
Debounce 500ms
    ↓
refetchMetrics()
refetchPnL()
refetchExposure()
    ↓
Positions table updates live
```

### I.4 Admin Control Flow

```
Admin sets time/speed via API
    ↓
Admin API Endpoint
    ↓
MarketClock Service
    ↓
WebSocket Session Broadcast
    ↓
All Clients Receive Update
    ↓
MarketTimeIndicator updates
```

---

## J. ORDER VALIDATION & RISK MANAGEMENT

### J.1 Validation Chain (Ordered)

1. **KYC Check**
   - User must have KYC status APPROVED
   - Reject with error: "Your account must be KYC approved before trading"

2. **Ticker Validation**
   - Ticker must be in ALLOWED_TICKERS: ["AAPL", "GOOG", "IBM", "MarketClock now()`, feed simulator determines which tick to show
- Maps time-of-day to historical tick position
- 5-minute window query for efficiency
- Returns OHLCV data point

#### J.7.5 Feed Simulator Flow
```
MarketClock.now() (simulated time)
    ↓
Query database for ticker in [time-5min, time+5min]
    ↓
Find closest timestamp
    ↓
Return OHLCV data point
```

#### J.7.6 MarketClock Broadcast Flow
```
set_time() / set_speed_multiplier()
    ↓
MarketClock._current_timestamp updated
    ↓
WebSocket broadcast via signal or polling
    ↓
All clients receive update
    ↓
Frontend updates display
```

---

## K. AUTHENTICATION & SECURITY

### K.1 JWT Authentication Flow

```
Client Login Request
    ↓
/security/hash_password()
    ↓
/security/create_access_token()
    ↓
JWT Token generated
    ↓
Token returned to client
    ↓
Client includes token in Authorization header
    ↓
/security/verify_token()
    ↓
Token validated
    ↓
User authenticated
```

### K.2 Password Security

- **Hashing:** bcrypt with salt
- **Salt Rounds:** 12 rounds
- **Algorithm:** bcrypt (via passlib)
- **Storage:** Password hash stored in database

### K.3 JWT Token Management

- **Algorithm:** HS256
- **Expiry:** 60 minutes
- **Token Type:** Bearer
- **Payload:** username, role, exp

### K.4 Authorization Middleware

```python
def require_admin():
    if not user or user.role != Role.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
```

### K.5 Security Best Practices

- **Password Requirements:** Minimum 8 characters
- **Token Validation:** Every API endpoint requires valid JWT
- **Role-Based Access Control:** Admin-only endpoints protected
- **CORS:** Configured for development ( "*" origins)
- **SQL Injection Protection:** SQLAlchemy ORM prevents SQL injection
- **File Upload Validation:** Type and size checks

---

## L. GLOBAL MARKETCLOCK SYSTEM

### L.1 Architecture

**MarketClock is the single source of truth for all time-based operations**

### L.2 Core Components

**MarketClock Class:**
- Singleton pattern with thread-safe singleton
- Simulated time based on start time + elapsed time * speed multiplier
- Market status based on time of day (pre-market, open, closed)
- Speed multipliers: 1x, 2x, 5x, 12x, 30x
- Background thread for time advancement (every second)
- WebSocket broadcasting capability

### L.3 Time Calculation

```
simulated_time = start_time + (elapsed_seconds * speed_multiplier)
```

### L.4 Market Status Logic

- **Pre-Market:** 9:00-9:30 UTC
- **Open:** 9:30-16:00 UTC
- **Closed:** 16:00 UTC onwards

### L.5 Admin Control

**API Endpoints:**
- `POST /api/admin/session/time` - Set specific date/time
- `POST /api/admin/session/reset` - Reset to start
- `POST /api /admin/session/speed` - Set speed multiplier
- `GET /api/admin/session/status` - Get current state

**WebSocket Broadcast:**
- Session updates broadcast to all clients
- Instant synchronization across all connected users

### L.6 Integration Points

**Components Using MarketClock:**
- Feed simulator: Uses `market_clock.now()` for tick selection
- Order engine: Uses `market_clock.now()` for timestamps
- WebSocket: Broadcasts MarketClock status to clients
- Feed simulator: Direct database queries at MarketClock time

---

## M. FEED SIMULATOR & DATA PIPELINE

### M.1 Data Sources

**Historical Daily Data:**
- 130 daily bars per ticker (June 23 - December 15, 2026)
- Tickers: AAPL, GOOG, IBM, MSFT, TSLA, UL, WMT
- Location: `backend/app/data/simulation_historical_data/`

**Intraday Minute Data:**
- Minute-level data for July 1 - August 30, 2026
- 7 tickers with OHLCV data
- Location: `backend/app/data/simulation_price_data_July_1-Aug_30/`

**News Sentiment Data:**
- JSON files with sentiment scores
- Location: `backend/app/data/simulation_news_data_July_1-Aug_30/`

### M.2 Data Loading Process

**Application Startup (`main.py`):**
1. Check if database is empty
2. If empty, load all data:
   - Historical daily data via `load_all_data()`
   - Creates price_history_daily table
3. Data sources are CSV files in `data/` directory

### M.3 Feed Simulator Operation

**No Caching Approach:**
- Direct database queries
- 5-minute window queries for tick retrieval
- Map MarketClock time to historical tick
- No in-memory cache (removed for simplicity)

**Tick Selection Logic:**
1. Get MarketClock current time
2. Extract time-of-day (HH:MM:SS)
3. Query database for ticker in ±5 minute window
4. Find closest timestamp to target time
5. Return OHLCV data point

### M.4 Data Flow

```
MarketClock.now() (simulated time)
    ↓
get_current_tick_for_ticker(ticker, db)
    ↓
Database Query (5-minute window)
    ↓
Closest Timestamp Match
    ↓
Return OHLCV Data Point
    ↓
WebSocket Broadcast (every minute)
    ↓
All Charts/Portfolios Update
```

---

## N. TESTING STRATEGY

### N.1 Test Suite Structure

**Test Files:**
- `test_admin.py` - Admin functionality
- `test_analytics.py` - Technical indicators
- `test_auth.py` - Authentication flow
- `test_genai.py` - GenAI integration
- `test_kyc.py` - KYC workflow
- `test_kyc_integration.py` - KYC integration tests
- `test_live_data.py` - Live data streaming
- `test_orders.py` - Order lifecycle
- `test_paper_trading.py` - Backtesting engine
- `test_portfolio.py` - Portfolio calculations
- `test_reports.py` - Report generation

### N.2 Test Categories

1. **Unit Tests:** Individual function testing
2. **Integration Tests:** API endpoint testing
3. **End-to-End Tests:** Complete workflow testing
4. **MarketClock Tests:** Time management verification
5. **WebSocket Tests:** Real-time data streaming
6. **Risk Control Tests:** Validation logic verification

### N.3 Test Execution

```bash
# Run all tests
pytest

# Run specific test
pytest tests/test_orders.py

# Run with coverage
pytest --cov=app --cov-report=html
```

---

## O. DEPLOYMENT CONSIDERATIONS

### O.1 Production Deployment

**Environment Setup:**
- Set `SECRET_KEY` environment variable
- Configure `DATABASE_URL` for production database (PostgreSQL recommended)
- Set `ANTHROPIC_API_KEY` for GenAI features

**Database Migration:**
- Use Alembic for production database migrations
- Ensure proper indexing on (ticker, timestamp) columns
- Run migration script for simulation_timestamp columns if needed

**Performance:**
- Consider Redis for WebSocket connection management
- Use PostgreSQL for production database
- Configure connection pooling
- Enable query caching where appropriate

**Security:**
- Enable HTTPS
- Configure CORS for production domain
- Set up rate limiting
- Enable API keys for service-to-service communication

### O.2 Scalability Considerations

**WebSocket Scaling:**
- Single WebSocket per ticker may not scale
- Consider WebSocket load balancer for production
- Implement connection pooling

**Database Scaling:**
- SQLite suitable for development
- PostgreSQL for production
- Implement read replicas for read-heavy operations

**Background Tasks:**
- MarketClock thread needs proper signal handling
- Feed simulator may need queuing for multiple concurrent requests

### O.3 Monitoring

**Key Metrics:**
- WebSocket connection count
- Order processing latency
- Database query performance
- MarketClock thread health
- API error rates

**Logging:**
- Structured logging with log levels
- Audit log retention policy
- Error alerting and notifications

---

## APPENDICES

### Appendix A: Enum Definitions

**OrderSide:** BUY, SELL
**OrderType:** MARKET, LIMIT
**OrderStatus:** NEW, PENDING, PARTIAL_FILLED, FILLED, CANCELLED, REJECTED
**Role:** TRADER, ADMIN
**KYCStatus:** PENDING_SUBMISSION, PENDING_REVIEW, APPROVED, REJECTED
**MarketStatus:** pre-market, open, closed

### Appendix B: Error Codes

**400 Bad Request:** Invalid request parameters
**401 Unauthorized:** Invalid or missing JWT token
**403 Forbidden:** Insufficient permissions (e.g., non-admin accessing admin endpoint)
**404 Not Found:** Resource not found
**500 Internal Server Error:** Unexpected server error
**503 Service Unavailable:** Server temporarily unavailable

### Appendix C: Default Configuration

**Default MarketClock Settings:**
- Start Time: 2026-06-30T09:30:00 UTC
- Speed Multiplier: 1.0
- Market Status: open

**Default Risk Control Settings:**
- Price Collar: ±10%
- Max Notional: $250,000 per order
- Concentration Limit: 25% of net worth
- Max Orders: 10 per minute
- Commission: $1.00 flat fee

**Default Commission:** $1.00 flat fee per trade

---

**END OF COMPREHENSIVE BACKEND DOCUMENTATION**
