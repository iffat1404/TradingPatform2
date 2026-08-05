# Nomura STP Trading Platform — Master Build Prompt
**Version 5 — closes six gaps identified in build-readiness review: Paper Trading isolation from live state, SQLite concurrent-write safety, feed simulator restart determinism, GenAI failure fallback, KYC upload limits, and timestamp timezone. Supersedes v4. Nothing from v4 has been removed — only reorganized and extended.**

This document is written to be used as a standing prompt/context file for a coding agent. Start at Section 0, absorb the constraints once, then work top-to-bottom — every open design question has already been resolved below.

---

## 0. Mission and non-negotiable principles

**Mission:** build a 3-week MVP of a Straight-Through-Processing (STP) trading simulation platform for the Nomura Tech Graduate Program. Multiple traders, each onboarded through a KYC identity-verification flow, submit simulated market/limit orders (long or short) against a synthesized live price feed; the platform tracks positions and P&L in real time over WebSockets, charts historical and intraday prices with technical indicators, runs rule-based paper-trading backtests, layers Claude-powered GenAI features throughout, and gives an Admin role full oversight — KYC review, audit logs, and trade logs across every account.

**Non-negotiable principles — do not violate these anywhere in the codebase or the UI:**

1. **Every trading rule is deterministic code. GenAI explains and extracts; it never decides.** No LLM call ever decides whether an order is valid, whether a limit is breached, or what price a trade fills at.
2. **No order the GenAI layer drafts is ever submitted automatically.** Natural-language order parsing always returns a draft for explicit human confirmation before it reaches `POST /api/orders`.
3. **No partial fills — anywhere, including the UI.** Every order is fill-or-rest-in-full against the current tick. Do not surface a "PARTIALLY FILLED" status in code, API responses, or any UI component — the only terminal/interim states are `NEW`, `VALIDATED`, `ROUTED`, `FILLED`, `REJECTED`, `CANCELLED`.
4. **No cross-account data leakage.** Every authenticated query is scoped to the requesting account's `account_id` at the database query level — except Admin endpoints, which are deliberately cross-account and scoped by **role** instead, verified server-side on every request.
5. **FIFO cost basis, always**, for any partial position close.
6. **The audit trail (`order_events`) is mandatory, not optional.** It's also the data source the Admin console reads for trade/audit logs, so it must be complete.
7. **Short selling requires the collateral check.** Never ship short-order flow without the 150%-collateral guardrail in the same change.
8. **KYC approval is always a human (Admin) decision.** GenAI extracts fields from an uploaded ID document and reports structural checks as *suggestions*; `kyc_status` only becomes `APPROVED` when an Admin explicitly approves it.
9. **A trader cannot place an order until `kyc_status == APPROVED`.** Enforced in the order validation chain (check 0), not just in the frontend.
10. **The frontend is a basic, functional dashboard, not a polished product.** Section 18 defines a full design-token system and Section 19 tiers every screen element as MVP or Stretch — build MVP-tier items with the tokens applied (cheap, just CSS variables) and treat Stretch-tier visual richness (donut charts, sparklines, document zoom/rotate, tax-lot modals) as optional polish only if time remains after every module's Definition of Done passes.
11. **Paper Trading never touches live portfolio state.** Every order/fill/event a backtest generates is flagged `is_backtest = true` and is excluded from the trader's live portfolio totals and from the Admin's audit/trade logs by default. Same tables, same `order_engine.py`, one boolean flag — see Section 14.2 and Section 23.
12. **All timestamps are UTC, everywhere — storage, API responses, WebSocket payloads, logs.** The frontend converts to local time only at the point of display. Never store or compare a naive/local timestamp anywhere in the backend.
13. **The feed simulator is deterministic by default, resettable on demand.** It always replays from the start of the dataset (Jun 30) on a fresh container start; an Admin-only endpoint can force a reset back to the start at any time without restarting the container (Section 9.6).
14. **Every GenAI-powered feature degrades gracefully on failure.** If a Claude API call fails or times out, the surrounding feature shows a clear fallback state and the rest of the platform keeps working — a GenAI outage must never block trading, KYC submission, or any deterministic-code path (Section 15.3).

**Important scope boundary — state this explicitly in the README and the final presentation:** KYC in this platform is a **simulated, document-based flow** — an uploaded ID document is parsed and structurally validated (expiry, name match, age), it is **not** connected to any real government ID database, sanctions list, or licensed identity-verification provider (e.g., Jumio, Onfido, Persona). Use only sample/dummy ID images for testing and demos, and `.gitignore` the upload directory.

---

## 1. Business context (condensed from the original brief)

Nomura wants a modern trading platform with STP capabilities covering five core modules — Order Execution, Portfolio Management, Reporting & Charting, Technical Analytics, Paper Trading — built with GenAI, cloud/DevOps, and Python. Three deliverables: (1) the working platform, (2) operational workflow documentation (settlement, risk, system access), (3) a final presentation. Judged on functional completeness, business/tech alignment, and genuine GenAI use.

**Design implications from the stakeholder quotes:**
- Rohan (Head of Product): "single click to trade," fast execution, KPIs, reports, charting → Modules A and C
- Tom/Patricia (Client): Excel-based tracking is a pain point, wants a dashboard "tracking what I am interested in" → the Portfolio dashboard specifically
- Nora (Tech Developer): warns a full real-time sentiment system is "far-fetched" → news-sentiment feature is scoped as "aggregate and explain existing sentiment scores," not "build a sentiment model from scratch"
- Roy (CTO): wants DevSecOps, "robust and resilient," security/ops/SRE built in → drives the audit trail (principle 6), the KYC/onboarding control (principles 8–9), and the Admin oversight console (Module I) directly

---

## 2. Data assets (confirmed sufficient by direct computation — do not re-validate, proceed to build)

| Asset | Location pattern | Grain | Coverage | Notes |
|---|---|---|---|---|
| Historical prices | `simulation_historical_data/*.csv` | Daily OHLCV | 7 tickers, 130 rows each, Jan 2 – Jul 10 2026, zero nulls | Backtesting seed data, daily charts |
| Live feed | `simulation_price_data_July_1-Aug_30/*_live.csv` | 1-minute OHLCV | 7 tickers, ~17,000 rows each, Jun 30 – Aug 29 2026, zero nulls | Streamed to simulate real-time ticks |
| News | `simulation_news_data_.../*.json` | Daily article buckets, per-ticker sentiment | Market-wide (thousands of tickers), July + August | **Filter to the 7 tradable tickers before use** |

Tickers: **AAPL, GOOG, IBM, MSFT, TSLA, UL, WMT**

Confirmed by computation: SMA50 first valid at day 50/130; RSI14/MACD/Bollinger all clean from day ~15–20; sample AAPL row — close 232.98, SMA20 216.23, SMA50 198.71, RSI14 78.7, MACD 8.70 above signal 7.55. Intraday ~17k rows/ticker, far more than any indicator period needs.

**Known data quirk:** historical (through Jul 10) and live (from Jun 30) overlap ~10 trading days — dedupe by date if concatenated.

---

## 3. System architecture

```
+------------------+  +------------------+  +------------------+
| Historical CSVs  |  |  Live feed CSVs  |  |    News JSON     |
+--------+---------+  +--------+---------+  +--------+---------+
         +---------------------+---------------------+
                               v
                +-------------------------------+
                |   Data and ingestion layer     |
                +---------------+-----------------+
                                v
   +-------------+--------------+--------------+-------------+
   |Order         |Portfolio     |Technical      |Paper        |
   |Execution (A) |Mgmt (B)      |Analytics (D)  |Trading (E)  |
   +------+-------+------+-------+------+--------+------+------+
          +--------------+--------------+---------------+
                                v
                +-------------------------------+
                |        GenAI layer (F)         |
                | parsing, summaries, explains,  |
                | ID document extraction         |
                +---------------+-----------------+
                                v
        +----------------------+----------------------+
        v                                              v
+----------------+                          +--------------------+
| Trader frontend|                          |  Admin console (I)  |
| orders, chart, |                          | KYC review, audit   |
| portfolio, AI  |                          | logs, trade logs    |
+----------------+                          +--------------------+

  KYC/Onboarding (H) gates entry: Register -> Submit ID -> GenAI
  extraction -> Admin approve/reject -> kyc_status=APPROVED unlocks
  the trader frontend and Module A.

  All services run inside Docker containers, orchestrated with
  docker-compose, built and tested via GitLab CI/CD.
```

Key architectural decisions:
- **A and E share one engine**, pluggable price source (live vs. historical replay) — build this from the start.
- **GenAI sits underneath both the trader frontend and the Admin console.** `genai_client.py` is a shared service; it also handles ID document field extraction for KYC (H), consumed by the Admin review screen.
- **Admin console is a separate frontend surface, not a mode toggle inside the trader dashboard** — different role, different data scope, own route tree (`/admin/*`), own auth guard.
- **Reporting & Charting (C) remains a read layer** over B and the data layer, not a new business-rule surface.

---

## 4. Finalized tech stack

| Layer | Choice | Rationale |
|---|---|---|
| Backend framework | FastAPI (Python 3.11+) | async-native, needed for WebSocket tick streaming |
| Database | SQLite | zero infra overhead for a 3-week MVP |
| ORM | SQLAlchemy + Pydantic schemas | Pydantic doubles as FastAPI request/response validation |
| Auth | JWT (`python-jose` + `passlib`), role claim (`trader`/`admin`) | multi-account, two roles |
| File storage (KYC docs) | Local filesystem under a gitignored `uploads/` volume for MVP | swap for S3/blob storage if this graduates past a demo |
| Real-time | FastAPI native WebSockets | public market-tick channel, authenticated per-account channel, admin notifications channel |
| Frontend | React + Vite | basic functional dashboard for traders; a second lightweight route tree for Admin |
| Frontend data layer | TanStack Query + native WebSocket hook | |
| Charting | `lightweight-charts` (TradingView) or Recharts | candlestick + volume, indicator overlays, RSI/MACD sub-panel |
| Styling | Tailwind CSS, configured with the design tokens in Section 18 | fastest path to a clean-enough basic dashboard that still looks intentional |
| GenAI | Anthropic Python SDK (Claude API), multimodal calls for ID documents | one internal service, five capabilities (Section 15) |
| Containerization | Docker (multi-stage builds), docker-compose | |
| CI/CD | GitLab CI | lint -> test -> build, path-scoped jobs |
| IaC | Terraform | out of scope unless core build finishes early |

---

## 5. Repo and file structure

```
nomura-stp-platform/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── api/
│   │   │   ├── auth.py
│   │   │   ├── kyc.py                 # Module H
│   │   │   ├── admin.py               # Module I
│   │   │   ├── orders.py              # Module A
│   │   │   ├── portfolio.py           # Module B
│   │   │   ├── reports.py             # Module C
│   │   │   ├── analytics.py           # Module D
│   │   │   ├── paper_trading.py       # Module E
│   │   │   ├── genai.py               # Module F
│   │   │   └── websockets.py
│   │   ├── core/
│   │   │   ├── config.py              # ALL tunable constants (Section 6)
│   │   │   ├── db.py
│   │   │   └── security.py            # JWT issuing/verification + role guard dependency
│   │   ├── models/
│   │   │   ├── orm.py
│   │   │   └── schemas.py
│   │   ├── services/
│   │   │   ├── order_engine.py        # validation chain (incl. KYC check), state machine, pluggable price source
│   │   │   ├── portfolio_engine.py
│   │   │   ├── indicators.py
│   │   │   ├── feed_simulator.py
│   │   │   ├── backtest_engine.py     # now incl. benchmark calc, Section 14
│   │   │   ├── kyc_engine.py          # deterministic auto-checks (expiry, age, name match)
│   │   │   └── genai_client.py        # order parsing, explainer, summary, rejection explain, ID extraction
│   │   └── data/
│   │       ├── loaders.py
│   │       ├── news_preprocessor.py
│   │       └── seed_demo.py           # Section 21
│   ├── uploads/                       # gitignored — KYC document storage
│   ├── tests/
│   │   ├── test_order_validation.py   # top priority
│   │   ├── test_indicators.py         # top priority
│   │   ├── test_portfolio.py
│   │   └── test_kyc.py
│   ├── Dockerfile
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── trader/{components,pages,api,charts}/     # trader-facing app
│   │   ├── admin/{components,pages,api}/             # admin console
│   │   ├── shared/{auth,ui}/
│   │   └── styles/tokens.css                         # Section 18 design tokens as CSS variables
│   ├── tailwind.config.js                             # extended with Section 18 tokens
│   ├── Dockerfile
│   └── package.json
├── data/                              # raw simulation CSVs/JSON
├── docs/                              # this file + companion specs + design kit reference
├── infra/terraform/                   # empty unless Section 4's IaC stretch goal is reached
├── .gitlab-ci.yml
├── docker-compose.yml
├── .gitignore                         # must include backend/uploads/, *.db, .env
└── README.md
```

---

## 6. Configurable constants (single source of truth — `core/config.py`, never hardcode inline)

| Constant | Default | Used by |
|---|---|---|
| `STARTING_CAPITAL` | $1,000,000 | Account creation |
| `SPREAD_BPS` | 8 | A.3 synthetic bid/ask |
| `PRICE_COLLAR_PCT` | 10% | A.4 check |
| `MAX_NOTIONAL_PER_ORDER` | $250,000 | A.4 check |
| `MAX_CONCENTRATION_PCT` | 25% | A.4 check, also the sector-exposure warning marker in the UI (B.2) |
| `SHORT_COLLATERAL_MULTIPLIER` | 1.5 (150%) | A.4 check, also the collateral callout in the UI (A.1) |
| `ORDER_RATE_LIMIT_PER_MINUTE` | 10 | A.4 check |
| `WASH_TRADE_WINDOW_SECONDS` | 60 | A.4 check |
| `COMMISSION_FLAT_FEE` | $1.00 | B fee model |
| `MARKET_OPEN` / `MARKET_CLOSE` | 09:30 / 16:00 | derived from live feed timestamps |
| `FEED_REPLAY_SPEED_MULTIPLIER` | configurable; UI exposes 1x/5x/10x/60x presets (E.1) | G.2 |
| `SMA_PERIODS` | [20, 50] | D.1 |
| `EMA_PERIODS` | [12, 26] | D.1 |
| `RSI_PERIOD` | 14 | D.1 |
| `MACD_PARAMS` | (12, 26, 9) | D.1 |
| `BOLLINGER_PARAMS` | (20, 2) | D.1 |
| `RSI_OVERBOUGHT` / `RSI_OVERSOLD` | 70 / 30 | D.2 |
| `SENTIMENT_DIVERGENCE_THRESHOLD` | 0.35 | D.3 |
| `KYC_MIN_AGE_YEARS` | 18 | H.2 auto-check |
| `KYC_NAME_MATCH_THRESHOLD` | 0.85 (fuzzy match score) | H.2 auto-check |
| `ADMIN_BOOTSTRAP_USERNAME` / `ADMIN_BOOTSTRAP_PASSWORD` | set via `.env`, never committed | seed script (Section 21) |
| `KYC_MAX_UPLOAD_SIZE_MB` | 10 | H.1 upload validation |
| `KYC_ALLOWED_MIME_TYPES` | `["image/jpeg", "image/png", "application/pdf"]` | H.1 upload validation |
| `APP_TIMEZONE` | `UTC` (fixed, not meant to be changed) | every timestamp field, system-wide (principle 12) |
| `FEED_SIMULATOR_START_TIMESTAMP` | first timestamp in `price_history_minute` (Jun 30 2026, 09:30 UTC) | feed simulator reset behavior (principle 13, Section 16.5) |

---

## 7. Account model, roles, and auth

Two roles: **`trader`** (default, multi-account, own portfolio) and **`admin`** (oversight only — no trading portfolio of their own). Every request is scoped to `account_id` + `role` from the JWT.

- [ ] `POST /api/auth/register` — `{username, password, starting_capital?}` → creates a `trader` account, `kyc_status = NOT_STARTED`
- [ ] `POST /api/auth/login` — `{username, password}` → `{access_token, token_type, role}`
- [ ] `GET /api/auth/me` — returns account id/username/role/kyc_status/cash_balance
- [ ] Admin accounts are **never created via public registration** — only via the seed/bootstrap script (Section 21)
- [ ] `require_role("admin")` FastAPI dependency guarding every `/api/admin/*` route — returns 403 for any non-admin token

**Definition of Done:**
- [ ] Registering two trader accounts and logging into each returns distinct JWTs; account A's token against account B's portfolio endpoint returns only A's data
- [ ] A trader token against any `/api/admin/*` endpoint returns 403
- [ ] Password is never stored or returned in plaintext anywhere, including logs
- [ ] No public endpoint can create an `admin`-role account

---

## 8. Module H — KYC and Onboarding

**Flow:** Register → account exists with `kyc_status = NOT_STARTED`, trading blocked → trader submits ID document → GenAI extracts fields (informational) → deterministic auto-checks run and are recorded (informational) → `kyc_status = PENDING_REVIEW` → Admin reviews (Module I) and explicitly approves or rejects → only on Admin approval does `kyc_status = APPROVED` and trading unlock.

### H.1 Submission
- [ ] `POST /api/kyc/submit` — multipart upload: `id_type` (passport/drivers_license/national_id), `id_document` (image/PDF file)
- [ ] Validate the upload against `KYC_MAX_UPLOAD_SIZE_MB` (10MB) and `KYC_ALLOWED_MIME_TYPES` (`image/jpeg`, `image/png`, `application/pdf`) — reject anything else with a clear `400` error before it touches storage or the GenAI extraction call, so a bad upload fails fast and cheaply rather than burning an API call on a file that was never going to work
- [ ] Store under `backend/uploads/kyc/{account_id}/{submission_id}.{ext}` — never inline in the database, never committed to git
- [ ] Trigger extraction (H.2) and auto-checks (H.3) on submission; return `{status: "PROCESSING"}` if async, or synchronously if fast enough

### H.2 GenAI field extraction (informational only — principle 8)
```json
{"extracted_full_name": "Jordan A. Rivera", "extracted_dob": "1998-04-12",
 "extracted_id_number": "X1234567", "extracted_expiry_date": "2029-11-30",
 "extracted_issuing_country": "US", "extraction_confidence": "high"}
```
Prompt instructions must explicitly forbid inferring a value not legibly present in the image — return `null` + low confidence instead of guessing.

### H.3 Deterministic auto-checks (plain code, not GenAI)
| Check | Rule | Outcome if failed |
|---|---|---|
| Not expired | `extracted_expiry_date > today` | Flags "ID expired," still routes to Admin |
| Minimum age | `today - extracted_dob >= KYC_MIN_AGE_YEARS` | Flags "under minimum age" |
| Name match | Fuzzy match ≥ `KYC_NAME_MATCH_THRESHOLD` | Flags "name mismatch" |
| Extraction confidence | If not `"high"` | Flags "low-confidence extraction, verify manually" |

These populate `auto_check_passed`/`auto_check_notes` only — **the Admin approve/reject action is the only thing that changes `kyc_status`.**

### H.4 Status and gating
- [ ] `kyc_status` enum: `NOT_STARTED → PENDING_REVIEW → APPROVED` or `REJECTED` (rejected trader can resubmit, looping to `PENDING_REVIEW`)
- [ ] `GET /api/kyc/status` — trader-facing, returns current status and, if rejected, the Admin's `review_notes`
- [ ] Module A's validation chain gains **check 0**: `account.kyc_status == "APPROVED"`, reason code `KYC_NOT_APPROVED`

### Definition of Done
- [ ] Submitting a document creates a `kyc_submissions` row, extracts fields, runs all four auto-checks, lands in `PENDING_REVIEW` — `kyc_status` doesn't change without an explicit Admin action
- [ ] An order submitted while `kyc_status != APPROVED` is rejected with `KYC_NOT_APPROVED`, before any other check
- [ ] Uploaded documents are retrievable only by the owning trader and by Admin
- [ ] The upload directory is confirmed absent from any git commit

---

## 9. Module I — Admin Console

Full oversight for the Admin role: KYC review queue, cross-account audit logs, cross-account trade logs, and compliance flags. No trading capability for Admin accounts — separate surface, not an extra tab on the trader dashboard.

### I.1 KYC review
- [ ] `GET /api/admin/kyc?status=PENDING_REVIEW`
- [ ] `GET /api/admin/kyc/{submission_id}` — document image/PDF (admin-only authenticated route), extracted fields, `auto_check_passed`/`auto_check_notes`, account's registered info for comparison
- [ ] `POST /api/admin/kyc/{submission_id}/approve` → `account.kyc_status = APPROVED`, records `reviewed_by_admin_id`/`reviewed_at`
- [ ] `POST /api/admin/kyc/{submission_id}/reject` — `{reason}` → `account.kyc_status = REJECTED`, `review_notes = reason`

### I.2 Accounts overview
- [ ] `GET /api/admin/accounts` — username, `kyc_status`, net worth, created_at, order count

### I.3 Audit logs (built directly on `order_events`, principle 6)
- [ ] `GET /api/admin/audit-logs?account_id=&ticker=&from=&to=&reason_code=`
```json
{"account_id": "acc_123", "order_id": "ord_8f3a1c", "from_state": "VALIDATED",
 "to_state": "REJECTED", "reason": "CONCENTRATION_LIMIT_EXCEEDED",
 "timestamp": "2026-07-31T10:15:00Z"}
```

### I.4 Trade logs
- [ ] `GET /api/admin/trade-logs?account_id=&ticker=&from=&to=` — every fill across every account

### I.5 Compliance flags
- [ ] `GET /api/admin/flags` — wash-trade flags + KYC submissions with `auto_check_passed = false`, one combined review list

### I.6 Feed control (new — resolves feed simulator restart ambiguity, principle 13)
- [ ] `POST /api/admin/feed/reset` — admin-only, forces the feed simulator back to `FEED_SIMULATOR_START_TIMESTAMP` (Jun 30) without requiring a container restart. This is the operator's control for a live demo: run it right before presenting so the market state is always in a known, rehearsed position regardless of how long the container has been running or what happened in earlier sessions
- [ ] `GET /api/admin/feed/status` — current simulated timestamp, replay speed, running/paused state — lets the Admin console show "the market is currently at [timestamp]" rather than that being invisible

### I.7 Audit/trade log backtest filtering (ties to principle 11)
- [ ] `GET /api/admin/audit-logs` and `GET /api/admin/trade-logs` both default to `is_backtest = false` (live activity only) — add an explicit `include_backtest=true` query param for the rare case an Admin wants to inspect backtest activity, so the default view is never cluttered with simulated trades

### Definition of Done
- [ ] Approving a KYC submission immediately unblocks that account's ability to place orders
- [ ] Rejecting with a reason makes it visible to the trader via `GET /api/kyc/status`
- [ ] Audit/trade log endpoints return cross-account data in one call, and exclude backtest activity by default
- [ ] A trader-role JWT cannot reach any `/api/admin/*` endpoint
- [ ] `POST /api/admin/feed/reset` returns the simulator to the exact starting timestamp and tick order resumes correctly from there

---

## 10. Module A — Order Execution

### A.1 Order types — exact mechanics
| Type | Included | Behavior |
|---|---|---|
| Market | Yes | No price field; fills against the synthetic bid/ask on the **next tick after submission** (avoids look-ahead), always fully, immediately |
| Limit | Yes | Requires a limit price. **Marketable on arrival**: fills instantly at the limit price if immediately crossable. Otherwise rests in `VALIDATED`, re-checked every tick. **Day time-in-force only**. Fills at limit price or better, never worse |
| Stop-loss | Tier 2 stretch | Converts to a market order once trigger price is touched |
| Stop-limit | Excluded entirely | Can trigger and still not fill — too confusing to demo |

### A.2 Sides and short selling (in scope for MVP)
Side is Buy/Sell; direction comes from the resulting sign of `positions.signed_qty`.

### A.3 Spread — platform-synthesized, never trader-set
```
spread = last_price × SPREAD_BPS / 10000
synthetic_ask = last_price + spread / 2   (market buy fills here)
synthetic_bid = last_price − spread / 2   (market sell fills here)
```

### A.4 Pre-trade validation chain — ordered, first failure short-circuits
| # | Check | Rule | Reason code |
|---|---|---|---|
| 0 | **KYC approved** | `account.kyc_status == "APPROVED"` | `KYC_NOT_APPROVED` |
| 1 | Valid ticker | One of the 7 supported tickers | `INVALID_TICKER` |
| 2 | Market hours | Within `MARKET_OPEN`–`MARKET_CLOSE` | `MARKET_CLOSED` |
| 3 | Price collar | Limit price within ±`PRICE_COLLAR_PCT` of last price | `PRICE_COLLAR_BREACH` |
| 4 | Notional cap | `qty × price ≤ MAX_NOTIONAL_PER_ORDER` | `NOTIONAL_LIMIT_EXCEEDED` |
| 5 | Concentration limit | Resulting position value ≤ `MAX_CONCENTRATION_PCT` of net worth | `CONCENTRATION_LIMIT_EXCEEDED` |
| 6 | Cash/collateral | Buy: cash ≥ notional + fees. Short: reserve `SHORT_COLLATERAL_MULTIPLIER × notional` | `INSUFFICIENT_BUYING_POWER` |
| 7 | Rate limit | ≤ `ORDER_RATE_LIMIT_PER_MINUTE`/account/minute | `ORDER_RATE_LIMIT_EXCEEDED` |
| 8 | Wash-trade pattern (Tier 2) | Opposite-side same-ticker order within `WASH_TRADE_WINDOW_SECONDS` → flag, don't reject | `WASH_TRADE_FLAGGED` |

### A.5 Order lifecycle and audit trail
`NEW → VALIDATED → ROUTED → FILLED` / `NEW → REJECTED` / `VALIDATED → CANCELLED`. **These six states are the complete, closed set — no `PARTIALLY_FILLED` state exists anywhere in the system, per principle 3.** Every transition writes to `order_events`.

### A.6 Fill logic
Market: next tick, synthetic bid/ask, always fully. Limit: limit-or-better, immediate if marketable on arrival, else on the crossing tick. No partial fills.

### API — sample payloads
- [ ] `POST /api/orders`
```json
// Request
{"ticker": "AAPL", "side": "buy", "type": "limit", "qty": 100, "limit_price": 230.50}
// Response 201
{"id": "ord_8f3a1c", "account_id": "acc_123", "ticker": "AAPL", "side": "buy",
 "type": "limit", "qty": 100, "limit_price": 230.50, "status": "VALIDATED",
 "created_at": "2026-07-31T10:15:00Z"}
// Response 422 (KYC gate)
{"detail": {"error_code": "KYC_NOT_APPROVED",
 "message": "Your identity verification is still pending review. You can't place orders until it's approved."}}
```
- [ ] `GET /api/orders`, `GET /api/orders/{id}`, `DELETE /api/orders/{id}`, `GET /api/orders/{id}/events`

### Definition of Done
- [ ] Order submitted before KYC approval is rejected with `KYC_NOT_APPROVED`, before any other check
- [ ] Market buy for AAPL with sufficient cash (post-approval) fills within one tick at `synthetic_ask`; position/cash update; full event trail logged
- [ ] Market sell fills at `synthetic_bid`
- [ ] Limit buy priced above current ask fills immediately at the **limit price**
- [ ] Limit buy priced below current bid rests, fills only once crossed, at the limit price
- [ ] Order breaching `MAX_NOTIONAL_PER_ORDER` is `REJECTED`, no position/cash change
- [ ] Order breaching `MAX_CONCENTRATION_PCT` is rejected, existing position unchanged
- [ ] Short sell reserves `SHORT_COLLATERAL_MULTIPLIER × notional`; blocked if insufficient
- [ ] Cancelling a resting limit order moves it to `CANCELLED`, never fills afterward
- [ ] The 11th order within 60 seconds from one account is rejected
- [ ] Every scenario produces a complete `order_events` trail visible via `GET /api/orders/{id}/events` and `GET /api/admin/audit-logs`
- [ ] No API response, database row, or UI component anywhere ever contains a "PARTIALLY_FILLED" status

---

## 11. Module B — Portfolio Management

### B.1 Cost basis — FIFO, always
On a partial close, realized P&L is computed against the oldest open lots first; remaining quantity retains the cost basis of the not-yet-closed lots. Expose per-lot detail (purchase timestamp, quantity, cost) via a lots endpoint so the UI's tax-lot detail view (Section 19, B.1) has real data to show:
- [ ] `GET /api/portfolio/{ticker}/lots` — list of open FIFO lots for that ticker

### B.2 Cash and capital
Starting capital = `STARTING_CAPITAL`. Every fill writes a `cash_ledger` row: buy = debit (notional + fee), sell = credit (notional − fee), short sell = credit + collateral reservation entry.

- [ ] **Stretch (not MVP):** a "top up" capability — `POST /api/portfolio/topup {amount}` adding simulated cash mid-session. The frontend button for this exists in the design (Section 19, B) but stays disabled/placeholder until this endpoint is actually built — don't wire it to a fake success state, an honestly-disabled button is better than a button that lies about what it does.

### B.3 Position and valuation
`unrealized_pnl = signed_qty × (last_price − avg_cost)`, `market_value = signed_qty × last_price`. Rollups: `net_worth`, `gross_exposure`, `net_exposure`, and now also `collateral_reserved` (sum of active short-sale collateral reservations) so the UI's capital breakdown cards (Section 19, B.1) have a real figure to display, not a placeholder.

### B.4 Sector mapping (hardcoded)
```
AAPL, MSFT, IBM → Technology | GOOG → Communication Services
TSLA → Consumer Discretionary | WMT, UL → Consumer Staples
```

### API
- [ ] `GET /api/portfolio` (now includes `collateral_reserved`), `GET /api/portfolio/pnl`, `GET /api/portfolio/exposure`, `GET /api/portfolio/{ticker}/lots`

### Definition of Done
- [ ] After a fill, `signed_qty`/`avg_cost` (FIFO) correct
- [ ] Partial close realized P&L against oldest lot(s) only, and `GET /api/portfolio/{ticker}/lots` reflects the correct remaining lots
- [ ] `net_worth` matches a hand-calculated value for a scripted 3+ trade sequence
- [ ] `collateral_reserved` matches the sum of active short positions' reserved collateral
- [ ] Exposure by ticker/sector sums correctly to gross/net totals

---

## 12. Module C — Reporting and Charting

- [ ] Daily OHLCV endpoint from historical CSVs
- [ ] Intraday OHLCV endpoint, `interval` param (1m/5m/15m/60m), pandas `resample()`
- [ ] On-demand portfolio report; EOD snapshot at last tick before `MARKET_CLOSE`
- [ ] CSV export (first); PDF export only after content is stable
- [ ] `GET /api/prices/{ticker}/daily`, `GET /api/prices/{ticker}/intraday?interval=`, `GET /api/reports/portfolio`, `GET /api/reports/portfolio/export?format=`

### Definition of Done
- [ ] Daily endpoint returns exactly 130 bars/ticker matching source exactly
- [ ] 5-min resampled bar matches manual aggregation of underlying 1-min bars
- [ ] EOD snapshot: exactly one net-worth point per session
- [ ] CSV export matches on-screen numbers exactly

---

## 13. Module D — Technical Analytics

### D.1 Indicators
| Indicator | Params | Formula |
|---|---|---|
| SMA | 20, 50 | Rolling mean of close |
| EMA | 12, 26 | Standard exponential smoothing |
| RSI | 14 | Wilder's method |
| MACD | 12, 26, 9 | EMA(12) − EMA(26); signal = EMA(9) of that |
| Bollinger Bands | 20, 2σ | SMA(20) ± 2×rolling std |

### D.2 Alerts
RSI > 70 overbought (red badge in UI), RSI < 30 oversold (green badge in UI), MACD/signal crossover, price crosses outer Bollinger band.

### D.3 Sentiment-divergence
Daily avg sentiment vs. daily price-return sign; flag if `|avg_sentiment| > SENTIMENT_DIVERGENCE_THRESHOLD` and signs disagree. Deterministic — GenAI only narrates.

### API
- [ ] `GET /api/analytics/{ticker}/indicators`, `GET /api/analytics/{ticker}/alerts`, `GET /api/analytics/{ticker}/sentiment-divergence?date=`

### Definition of Done
- [ ] SMA50 first valid at exactly day 50
- [ ] RSI14 matches manual computation within rounding tolerance
- [ ] MACD crossover fires on the exact crossing day
- [ ] Sentiment-divergence fires only when both conditions met, verified on one hand-picked case

---

## 14. Module E — Paper Trading

Declarative strategy schema (ticker, entry_rule, exit_rule referencing Module D, position_size). Backtest runner steps through historical CSVs, evaluates rules, submits orders through the **same** `order_engine.py`/`validate_order()` as live trading — pluggable price source is essential, built into Module A from the start. Metrics: total return, max drawdown, win rate.

### E.1 Isolation from live state (new — resolves the paper-trading/live-portfolio gap)
Backtests use the same tables and the same engine as live trading — not separate schemas — but every row a backtest produces is flagged so it can never be mistaken for or mixed into real account state:
- [ ] Every order/fill/event a backtest run generates carries `is_backtest = true` (added to `orders`, `fills`, `order_events`, `cash_ledger`, `positions` — Section 23)
- [ ] `order_engine.py`'s validation and fill logic behave identically either way — the flag changes nothing about *how* an order is processed, only how it's tagged and later filtered
- [ ] `GET /api/portfolio`, `GET /api/portfolio/pnl`, `GET /api/portfolio/exposure` (Module B) all filter to `is_backtest = false` by default — a backtest run must never change the numbers a trader sees on their live dashboard
- [ ] Backtest positions/cash are tracked using the account's real `starting_capital` as a hypothetical baseline for the run, but never write back to the account's actual `cash_balance` — the backtest's ending cash/positions exist only within its own flagged rows, read by `GET /api/paper-trading/backtest/{run_id}/results`, never merged into `GET /api/portfolio`
- [ ] Admin's audit/trade logs (I.3, I.4, I.7) exclude `is_backtest = true` rows by default, with an explicit opt-in filter to view them

### E.2 Benchmark comparison (added to match the UI's Benchmark Comparison Chart)
- [ ] For every backtest run, also compute a **buy-and-hold benchmark** on the same ticker over the same date range: buy at the first bar's open, hold to the last bar's close, compute the resulting return with no trading logic applied
- [ ] Store `benchmark_return` alongside `total_return` on `backtest_runs` so the strategy's performance can be shown against the naive baseline — this is a deliberately simple benchmark (not a market index, since the dataset doesn't include one), and should be labeled "vs. buy-and-hold AAPL" (or whichever ticker) in the UI, not "vs. market," to avoid overstating what it's comparing against

### API
- [ ] `POST /api/paper-trading/strategies`, `GET /api/paper-trading/strategies`, `POST /api/paper-trading/backtest/{strategy_id}/run`, `GET /api/paper-trading/backtest/{run_id}/results` (now includes `benchmark_return`)

### Definition of Done
- [ ] RSI<30/RSI>70 strategy on AAPL historical data submits orders through the same validation chain (KYC-approved backtest account required, same as live)
- [ ] Backtest metrics match manual recomputation for a fixed date range
- [ ] `benchmark_return` matches a manual buy-and-hold calculation for the same ticker/date range
- [ ] Running a backtest leaves the account's `GET /api/portfolio` response byte-for-byte unchanged before and after the run
- [ ] Backtest-generated rows are visible in `GET /api/paper-trading/backtest/{run_id}/results` but absent from `GET /api/admin/audit-logs`/`trade-logs` unless `include_backtest=true` is passed

---

## 15. Module F — GenAI Layer

One internal service, five capabilities, routed through it, never duplicated per-caller.

| Capability | Consumed by | Human-in-the-loop |
|---|---|---|
| Order command parsing | A | **Always** — draft only, requires explicit confirm |
| News/sentiment explainer | C, D | No — informational |
| Portfolio/report summary | C | No — numbers passed in, never recalculated by the model |
| Compliance/rejection explanation | A | No — explains a code already produced by A.4 |
| ID document field extraction | H (KYC) | **Always** — extraction is a suggestion for the Admin, never auto-applied to `kyc_status` |

### Sample payloads
```json
// POST /api/genai/parse-order
{"text": "buy 100 apple shares at market"}
// -> {"draft_order": {"ticker": "AAPL", "side": "buy", "type": "market", "qty": 100},
//     "confidence": "high", "requires_confirmation": true}

// GET /api/genai/explain/AAPL?date=2026-07-15
// -> {"ticker": "AAPL", "date": "2026-07-15",
//     "summary": "AAPL saw positive coverage today driven by strong iPhone demand reports...",
//     "headline_count": 12, "avg_sentiment": 0.42}

// POST /api/genai/explain-rejection
{"order_id": "ord_8f3a1c"}
// -> {"explanation": "This order was rejected because it would push your AAPL position
//     to 31% of total capital, above the 25% concentration policy limit..."}
```

### Guardrails and caching
- [ ] Cache news summaries per (ticker, date)
- [ ] Pre-filter news JSON to the 7 tradable tickers before any prompt
- [ ] Prompts explicitly forbid inventing numbers/facts not in the input — for ID extraction, forbid guessing any field not legibly present (return `null` + low confidence instead)

### 15.3 Graceful degradation on failure (new — resolves the missing GenAI-outage behavior, principle 14)
Every capability has a defined fallback so a Claude API failure or timeout never blocks a deterministic-code path:
| Capability | On failure |
|---|---|
| Order command parsing | Return a clear error to the frontend ("Couldn't parse that command"); the manual order ticket remains fully usable — a trader can always fall back to filling in ticker/side/qty by hand |
| News/sentiment explainer | Panel shows "AI summary unavailable right now" instead of blocking the chart/analytics page; the underlying deterministic sentiment-divergence flag (D.3) still renders regardless, since that's computed independently of this call |
| Portfolio/report summary | Card shows "AI summary unavailable"; the numeric report data (which doesn't depend on GenAI) still renders in full |
| Compliance/rejection explanation | Order rejection still shows the raw reason code and message (Section 10.4's table) even if the GenAI plain-English version fails to generate — the reason code is never gated behind GenAI availability |
| ID document extraction | KYC submission still reaches the Admin queue with `extraction_confidence = null` and a note "automatic extraction failed, review document manually" — the submission is never blocked or lost, Admin can review the raw document directly |
- [ ] Backend wraps every `genai_client.py` call in a try/except with a bounded timeout (e.g., 15s); on exception or timeout, return the fallback payload defined above rather than propagating a 500
- [ ] No retry/backoff logic required for this scope — one attempt, then degrade (keeps the failure path simple and fast to hit in a live demo if needed)

### Definition of Done
- [ ] Order-parsing output never reaches `POST /api/orders` without explicit separate confirmation
- [ ] News explainer only references facts in the filtered input
- [ ] Portfolio summary numbers match exactly what was passed in
- [ ] Repeated (ticker, date) explainer request is served from cache
- [ ] ID extraction output is never written to `account.kyc_status` directly by any code path
- [ ] Simulating a Claude API failure (e.g., an invalid API key in a test run) for each of the five capabilities produces the documented fallback behavior, not a crash or a blocked page

---

## 16. Module G — Data and Infrastructure

- [ ] One-time loader: historical CSVs → `price_history_daily`, live CSVs → `price_history_minute`
- [ ] News preprocessor: daily JSON → `news_sentiment_daily`, filtered to 7 tickers, pre-aggregated
- [ ] Feed simulator: replays `price_history_minute` at `FEED_REPLAY_SPEED_MULTIPLIER`, pushes ticks over `/ws/market/{ticker}`, triggers resting-order checks and revaluation
- [ ] Market hours derived from the live feed's own timestamps

### G.1 SQLite concurrency (new — resolves the write-contention gap, given the feed simulator and order API both write concurrently)
- [ ] Enable WAL mode on database init: `PRAGMA journal_mode=WAL` — this is a one-line fix that lets reads proceed while a write is in progress, which is exactly the pattern here (feed simulator writing ticks/fills in the background while the API handles order submissions)
- [ ] No further concurrency infrastructure (write queues, connection pooling beyond SQLAlchemy defaults) is needed at this scale — WAL mode is sufficient for a single-instance MVP with 7 tickers ticking once a minute

### G.2 Feed simulator determinism and reset (new — resolves the restart-behavior gap, principle 13)
- [ ] On backend container start, the feed simulator always begins replay from `FEED_SIMULATOR_START_TIMESTAMP` (the first minute-bar timestamp in the dataset, Jun 30 2026 09:30 UTC) — never resumes from a persisted "last position." This keeps every fresh start deterministic and rehearsable
- [ ] `POST /api/admin/feed/reset` (Section 9.6) lets an Admin force the same reset-to-start behavior on a running container, without needing to restart it — this is the operator control for resetting market state right before a live demo
- [ ] `GET /api/admin/feed/status` exposes the current simulated timestamp and running state so this is never a black box

### Definition of Done
- [ ] Loader produces exactly 7×130 daily rows and correct minute-row counts, zero nulls
- [ ] Feed simulator at 1x emits one tick per sim-minute per ticker, correct order
- [ ] `news_sentiment_daily` contains only the 7 tickers, one row per (ticker, date)
- [ ] WAL mode is confirmed active (`PRAGMA journal_mode` returns `wal`) and a concurrent order-submission-during-tick-write test does not raise a "database is locked" error
- [ ] Restarting the backend container resets the feed to `FEED_SIMULATOR_START_TIMESTAMP`, and `POST /api/admin/feed/reset` produces the identical reset without a restart

---

## 17. WebSocket catalogue

- [ ] `WS /ws/market/{ticker}` — public, no auth:
```json
{"type": "tick", "ticker": "AAPL", "timestamp": "2026-07-01T09:31:00Z",
 "open": 211.47, "high": 212.11, "low": 211.36, "close": 211.99, "volume": 585361,
 "synthetic_bid": 211.88, "synthetic_ask": 212.10}
```
- [ ] `WS /ws/account/{account_id}` — authenticated (JWT on connect, trader-scoped):
```json
{"type": "order_update", "order_id": "ord_8f3a1c", "status": "FILLED",
 "fill_price": 230.50, "timestamp": "2026-07-31T10:15:01Z"}
{"type": "portfolio_update", "net_worth": 1002345.12, "cash": 850000.00,
 "positions": [{"ticker": "AAPL", "qty": 100, "unrealized_pnl": 150.00}],
 "timestamp": "2026-07-31T10:16:00Z"}
{"type": "kyc_status_update", "kyc_status": "APPROVED", "timestamp": "2026-07-31T09:00:00Z"}
```
- [ ] `WS /ws/admin/notifications` — authenticated, **admin role only**:
```json
{"type": "new_kyc_submission", "submission_id": "kyc_552", "account_id": "acc_777", "timestamp": "2026-07-31T09:05:00Z"}
{"type": "compliance_flag", "flag_type": "WASH_TRADE_FLAGGED", "account_id": "acc_123", "order_id": "ord_9a1b", "timestamp": "2026-07-31T10:20:00Z"}
```

**Note on update frequency:** fine as-is at 7 tickers/1-minute ticks; throttle `portfolio_update` to at most once/second if replay speed or ticker count increases later.

---

## 18. UI/UX Design System

Derived from the "Global Investment & Trading Platform" design kit, verified against the actual kit assets (color swatches and type specimens match exactly) and cross-checked against every reason code, status enum, and threshold defined earlier in this document. Implement as CSS variables / Tailwind theme extension, referenced by class name in Section 19 — never hardcode a hex value or pixel size directly in a component.

### 18.1 Color tokens
**Brand and action:**
| Token | Hex | Usage |
|---|---|---|
| `color-primary` | `#0082FF` | Primary CTAs (Start Trade, Buy, active nav) |
| `color-info` | `#2BBCFF` | Informational badges, `NEW` order status, secondary links |
| `color-base` | `#FFFFFF` | Cards, modals, popovers |
| `color-background` | `#F4F9FF` | Page canvas |

**Financial/semantic status:**
| Token | Hex | Usage |
|---|---|---|
| `color-positive` | `#00B29C` | Profit, upward ticks, `FILLED` status, KYC `APPROVED` |
| `color-positive-100` | `#E8FBF4` | Positive metric backgrounds |
| `color-negative` | `#FF6363` | Loss, downward ticks, `REJECTED` status, KYC `REJECTED` |
| `color-negative-100` | `#FFF3F4` | Negative/reject backgrounds |
| `color-warning` | `#FF9F43` | KYC `PENDING_REVIEW`, wash-trade alerts — **not** used for a partial-fill state, since that state doesn't exist (principle 3) |
| `color-warning-100` | `#FFF8E7` | Pending/warning backgrounds |

**Neutrals:** `color-neutral-500 #121D28` (primary text) / `400 #626E7A` (secondary text) / `300 #99A2A9` (icons, disabled) / `200 #C4CAD1` (borders) / `100 #E3E6ED` (card borders, hover).

**Specialized:** `color-kit #F8FAFD` (inner widget headers), `color-presentation #DCE3ED` (disabled surfaces), `color-component #9747FF` (GenAI feature accents — every AI-generated element in the UI, the parse-order modal, the news explainer, the portfolio narrative, should carry this accent so GenAI content is visually distinguishable from deterministic platform data, reinforcing principle 1 at the UI level).

### 18.2 Typography
Circular (Bold/Black) for headings, SF Pro (Regular/Medium/Semibold) for data density and body copy.

| Style | Font | Weight | Size/Line-height | Usage |
|---|---|---|---|---|
| Headline/XL | Circular | Bold | 48/56 | Page titles ("Overview," "KYC Verification") |
| Headline/L | Circular | Bold | 36/44 | Module headers, modal titles |
| Headline/M | Circular | Bold | 30/38 | Widget titles |
| Headline/S | Circular | Bold | 20/28 | Sub-card headers |
| Subheadline/Medium | SF Pro | Medium | 17/24 | Prominent table rows, tab headers |
| Subheadline/Regular | SF Pro | Regular | 17/24 | Form field titles |
| Body/Semibold | SF Pro | Semibold | 14/20 | Primary table data, active button text |
| Body/Regular | SF Pro | Regular | 14/20 | Standard body copy |
| Body/Uppercase | SF Pro | Semibold | 14/20 | Ticker symbols, column headers |
| Caption/Semibold | SF Pro | Semibold | 12/16 | Micro-badges, timestamps |
| Caption/Regular | SF Pro | Regular | 12/16 | Secondary table metrics |

### 18.3 Layout, grid, and spacing
- Viewport base width 1440px (desktop standard); 12-column responsive grid, 86px columns, 11px gutter; 64px canvas margin
- Sidebar: 192px expanded / 72px collapsed
- Card radius 16px (standard) / 24px (main app wrapper); button radius 24px (pill) / 12px (secondary); input radius 12px
- Card outer gap 24px; card inner padding 24px

### 18.4 Note on the "basic dashboard" scope decision
This design system is comprehensive, but the earlier project decision was explicit: **basic, functional dashboard, not a polished product.** Resolve the tension this way — apply the color tokens, typography, and spacing system everywhere (they cost nothing extra once defined as Tailwind theme values), but treat the richer components described in Section 19 (donut charts, sparklines, document zoom/rotate, tax-lot modals, benchmark comparison charts) as explicitly tiered MVP vs. Stretch. Every item in Section 19 carries that tag — build MVP-tagged items first and completely; only reach for Stretch-tagged polish once every module's Definition of Done (Sections 7–16) passes.

---

## 19. Frontend Implementation — Module Screens

All items below use the Section 18 tokens. Each item is tagged **[MVP]** or **[Stretch]**. Build all MVP items before any Stretch item, regardless of module.

### Shell components
- [MVP] Login/Register: centered white card on `color-background` canvas, standard fields (username, password, optional starting capital)
- [MVP] KYC status banner (floating, top of trader app): `NOT_STARTED`/`PENDING_REVIEW` → `color-warning` accent, "Identity verification pending. Trading execution is locked." / `REJECTED` → `color-negative` accent, "KYC Verification Failed. Reason: [Admin's review_notes]. Please re-submit." / `APPROVED` → `color-positive` badge, "Account Verified"
- [MVP] Trader sidebar: logo, `[+ Start Trade]` CTA (disabled/greyed if `kyc_status != APPROVED`), nav (Overview, Trade Execution, Portfolio, Charts, Analytics, Paper Trading, KYC Verification, Settings)
- [Stretch] `[↑ Top Up]` CTA — per the earlier resolution, render it but keep it disabled/placeholder until `POST /api/portfolio/topup` (Section 11) actually exists; do not fake a success response
- [MVP] Admin sidebar (`/admin/*`): distinct brand badge with `color-component` accent, nav (KYC Queue, Accounts Overview, Audit Logs, Trade Logs, Compliance Flags)
- [MVP] Top header summary bar (trader view): Unrealized P&L, Realized P&L, Net Worth, Cash Balance, KYC badge, user greeting — all sourced from `/ws/account/{id}` `portfolio_update` messages, not polled
- [Stretch] Collateral/margin reserved as a fifth header stat, sourced from `collateral_reserved` (Section 11.3)

### Module A — Order Execution
- [MVP] Order ticket: ticker, side toggle, quantity; limit orders add limit price + Day time-in-force label
- [MVP] KYC gating overlay on the order ticket if `kyc_status != APPROVED`: semi-transparent panel, CTA "Complete Identity Verification to Unlock Trading" linking to the KYC page
- [MVP] Short-sell toggle with a collateral callout computed client-side from `SHORT_COLLATERAL_MULTIPLIER × notional` (e.g., "Collateral Required: $22,500 (150%)") — matches Section 6/A.4 exactly, don't let the UI display a different multiplier than the backend enforces
- [MVP] Real-time estimated execution price callout ("Estimated execution at Ask $153.33"), computed client-side from the `synthetic_ask`/`synthetic_bid` fields already present in the `/ws/market/{ticker}` tick payload — **no new backend endpoint needed for this**, it's already in the tick message (Section 17)
- [MVP] Inline validation errors on rejection, keyed to the exact reason codes in Section 10.4 (`KYC_NOT_APPROVED`, `INSUFFICIENT_BUYING_POWER`, `CONCENTRATION_LIMIT_EXCEEDED`, `NOTIONAL_LIMIT_EXCEEDED`, etc.) — the error message shown should be the GenAI rejection explanation (Section 15) where available, falling back to the raw reason code text otherwise
- [MVP] GenAI order confirmation modal (principle 2, guardrail): header "GenAI Drafted Order — Review Required," parsed details card (ticker/side/type/qty/estimated cost), explicit disclaimer "GenAI never executes trades automatically," Cancel vs. Confirm & Submit — Confirm is the only path that calls `POST /api/orders`
- [MVP] Order manager: tabs for Working Orders / Executed History; status badges using `color-info` (`NEW`/`VALIDATED`/`ROUTED`), `color-positive` (`FILLED`), `color-negative` (`REJECTED`, with hover tooltip showing the exact reason code) — **no `PARTIALLY FILLED` badge, that status doesn't exist**

### Module B — Portfolio Management
- [MVP] Capital overview cards: Net Worth, Realized P&L, Unrealized P&L, Cash Balance
- [Stretch] Collateral Reserved as a fifth card (needs `collateral_reserved`, Section 11.3 — build the field before building this card)
- [MVP] Open positions table: symbol, signed quantity, avg entry price (FIFO), current price, unrealized P&L ($/%), market value
- [Stretch] Tax lot detail modal (per-lot purchase timestamps/quantities) — needs `GET /api/portfolio/{ticker}/lots` (Section 11.1) built first
- [Stretch] Asset class allocation donut chart
- [MVP] Sector exposure bars (simple horizontal bars are enough for MVP; segmented/animated version is Stretch) with a warning marker at `MAX_CONCENTRATION_PCT` (25%) — reuse the same constant the backend enforces, don't hardcode 25% separately in the frontend

### Module C — Reporting and Charting
- [MVP] Chart control bar: symbol switcher, timeframe picker (1m/5m/15m/1h/1D — maps to the backend's `interval` param, Section 12), chart type toggle (candlestick/line)
- [MVP] Overlay checkboxes: SMA-20, SMA-50, EMA-12, EMA-26, Bollinger Bands; sub-panels for RSI-14 and MACD
- [MVP] GenAI narrative report panel: `color-component` accent header "GenAI Portfolio Performance Narrative," formatted summary text, guardrail badge "AI-generated analysis based on deterministic platform data" (reinforces principle 1 visually)
- [MVP] Fallback state for the panel above: if `GET /api/genai/portfolio-summary` returns the failure fallback (Section 15.3), show "AI summary unavailable right now" in place of the narrative text — the rest of the report (numbers, charts) renders normally regardless

### Module D — Technical Analytics
- [MVP] Indicators table per ticker with RSI color coding (`RSI > 70` → `color-negative` "overbought," `RSI < 30` → `color-positive` "oversold" — matches Section 13.2's thresholds exactly)
- [MVP] Sentiment-divergence warning badge on chart/watchlist, e.g. "Bullish Divergence: Price ↓2.1% while Sentiment ↑+0.78" — only rendered when the backend's deterministic flag (Section 13.3) actually fires, never inferred client-side

### Module E — Paper Trading
- [MVP] Simulation controls: Play/Pause, speed selector (1x/5x/10x/60x, maps to `FEED_REPLAY_SPEED_MULTIPLIER`), simulation clock display
- [MVP] Strategy builder: entry/exit rule inputs referencing Module D indicators, position size
- [MVP] Performance metric cards: Total Return, Max Drawdown, Win Rate
- [MVP] Benchmark comparison chart — now buildable since Section 14.2 adds `benchmark_return` to the backtest results; label it explicitly "vs. buy-and-hold [TICKER]," not "vs. market"

### Module H — KYC and Onboarding
- [MVP] Multi-step wizard card: document type dropdown (Passport/Driver's License/National ID), drag-and-drop upload with image/PDF preview thumbnail, a declaration checkbox confirming the uploaded document is a test/dummy document (reinforces the scope boundary from Section 0), submit button
- [MVP] Pending state card: clock icon (`color-warning`), "Your document has been submitted and is under review"
- [MVP] Rejection card: `color-negative-100` background, "Verification Rejected: [Admin's review_notes]," re-submit action button

### Module I — Admin Console
- [MVP] KYC queue table: user ID, submission date, ID type, auto-check summary badge (`PASSED` `color-positive` or `FLAGS DETECTED` `color-warning`)
- [MVP] Review workspace (can be a simple two-column layout for MVP; zoom/rotate document viewer tooling is Stretch): document image on one side, comparison table on the other — registered name vs. extracted name + fuzzy match score, DOB/age vs. minimum-age check, expiry vs. not-expired check, extraction confidence
- [MVP] Decision bar: Approve (primary, `color-positive`) / Reject (outline, `color-negative`, opens a mandatory reason text input) — wired directly to Section 9.1's approve/reject endpoints
- [MVP] Accounts overview table: username, KYC status badge, net worth, cash balance, order count, created date
- [MVP] Audit log inspector: filterable table over `order_events` (timestamp, account, order, ticker, state transition, reason)
- [MVP] Trade log table: filterable table over fills (timestamp, trade ID, account, ticker, side, qty, fill price, fee)
- [MVP] Compliance flags view: wash-trade alerts + KYC auto-check failures in one combined feed
- [Stretch] Live-updating badges on the KYC queue and flags view via `/ws/admin/notifications` — polling is an acceptable MVP fallback if the WebSocket wiring isn't ready in time
- [MVP] Feed control widget: current simulated timestamp/status (from `GET /api/admin/feed/status`) and a "Reset Market Feed" button calling `POST /api/admin/feed/reset` — this is the operator control to use right before a live demo (Section 9.6)

---

## 20. Backend task checklist

- [ ] FastAPI skeleton, router registration for all modules including `kyc.py` and `admin.py`
- [ ] SQLite engine/session, SQLAlchemy models per Section 23, WAL mode enabled on init (Section 16.1)
- [ ] JWT auth dependency scoping every trader query to `account_id`; separate `require_role("admin")` dependency
- [ ] Loaders run on startup or via a one-off script
- [ ] `feed_simulator.py` as a background asyncio task
- [ ] `order_engine.py`: full A.4 validation chain (incl. check 0) + A.5 state machine, unit-tested first
- [ ] `portfolio_engine.py`: recalculates on every fill and every tick, now including `collateral_reserved`
- [ ] `indicators.py`: pure functions, unit-tested
- [ ] `backtest_engine.py`: reuses `order_engine.py` with pluggable clock, tags every row `is_backtest = true` (Section 14.1), and computes the buy-and-hold benchmark (Section 14.2)
- [ ] `kyc_engine.py`: the four deterministic auto-checks (H.3)
- [ ] `genai_client.py`: five capabilities, caching, news pre-filter, multimodal ID extraction, bounded-timeout try/except wrapper with the per-capability fallback behavior defined in Section 15.3
- [ ] `feed_simulator.py` deterministic start + admin-triggered reset (Section 16.2), `/api/admin/feed/reset` and `/api/admin/feed/status` endpoints
- [ ] File upload handling for KYC documents (size/type validation, storage, authenticated retrieval only)
- [ ] WebSocket connection manager, multiple concurrent subscribers per channel including admin notifications
- [ ] Global error handling → consistent JSON error shape
- [ ] `/health` endpoint

---

## 21. Seed and demo data

- [ ] `backend/app/data/seed_demo.py`, run after base loaders:
  - **One bootstrap Admin account**, created from `ADMIN_BOOTSTRAP_USERNAME`/`ADMIN_BOOTSTRAP_PASSWORD` env vars
  - Two demo trader accounts, `demo_trader1`/`demo_trader2` (fixed demo passwords, documented in `README.md`, not for production)
  - **KYC submissions pre-seeded and pre-approved** for both demo traders (using a sample/dummy ID image checked into `data/sample_kyc/`, clearly labeled as fake test data) so the demo shows a fully unlocked trading account immediately
  - One additional demo trader left at `kyc_status = PENDING_REVIEW` with a real (dummy) submission on file, so the Admin console demo has something live to approve/reject on stage
  - `demo_trader1`: seeded fills producing a long AAPL position (100 shares), long MSFT (50 shares), short TSLA (20 shares), plus a couple of resting unfilled limit orders
  - `demo_trader2`: a smaller, different mix (e.g., long GOOG 30 shares)
- [ ] Document the seed command in `README.md`, with an explicit note that `data/sample_kyc/` contains fabricated test documents only
- [ ] Seeding is idempotent/reset-able for repeated rehearsals

### Definition of Done
- [ ] After seeding, `demo_trader1`/`demo_trader2` are fully KYC-approved and can place orders immediately
- [ ] The third pending demo account is visible in the Admin console's KYC queue and can be approved live during a demo
- [ ] Logging in as the bootstrap Admin account reaches the Admin console and nowhere else
- [ ] Re-running the seed script does not duplicate accounts, positions, or KYC submissions

---

## 22. Operational workflow documentation (Corporate Analysts, grounded in what's actually built)

- **Onboarding/KYC workflow:** account registration → document submission → GenAI extraction (informational) → deterministic auto-checks (informational) → Admin manual review → approve/reject → trading unlocked or blocked with a stated reason. Document explicitly that this is a simulated, document-based check, not a connection to a real identity-verification bureau.
- **Settlement workflow:** order → validated (A.4, including the KYC gate) → routed → filled (A.6) → `fills`/`cash_ledger` written → position updated (B.3) → simulated T+0 settlement (state this simplification explicitly)
- **Risk management workflow:** table the A.4 checks as "pre-trade risk controls"; describe the wash-trade flag and its Admin-console review routing (Module I.5)
- **System access workflow:** two real, implemented roles — Trader (own account only) and Admin (cross-account oversight, no trading) — document the actual `require_role` enforcement, not an aspirational model
- **Compliance/audit narrative:** `order_events` is the system of record, readable by Admin via I.3; GenAI-generated rejection explanations are shown alongside the deterministic reason code, never in place of it; KYC extraction is shown alongside the Admin's actual decision, never in place of it

---

## 23. Database schema (SQLite)

- [ ] `accounts` (id, username, password_hash, role [`trader`/`admin`], kyc_status, starting_capital, cash_balance, created_at)
- [ ] `kyc_submissions` (id, account_id, id_type, document_path, extracted_full_name, extracted_dob, extracted_id_number, extracted_expiry_date, extracted_issuing_country, extraction_confidence, auto_check_passed, auto_check_notes, status, reviewed_by_admin_id, review_notes, submitted_at, reviewed_at)
- [ ] `orders` (id, account_id, ticker, side, type, qty, limit_price, status, `is_backtest` [bool, default false], created_at)
- [ ] `order_events` (id, order_id, from_state, to_state, reason, `is_backtest`, timestamp)
- [ ] `fills` (id, order_id, fill_price, fill_qty, fees, `is_backtest`, timestamp)
- [ ] `positions` (id, account_id, ticker, signed_qty, avg_cost, realized_pnl, `is_backtest`) — unique on (account_id, ticker, `is_backtest`) so a live and a backtest position for the same ticker never collide
- [ ] `cash_ledger` (id, account_id, amount, reason, `is_backtest`, timestamp) — `reason` values now include `COLLATERAL_RESERVE`/`COLLATERAL_RELEASE` for short-sale collateral, distinct from ordinary trade debits/credits
- [ ] **All timestamp columns, in every table listed here, are stored in UTC** (principle 12) — this is a schema-wide convention, not called out per-column below
- [ ] `price_history_daily` (ticker, date, open, high, low, close, adj_close, volume)
- [ ] `price_history_minute` (ticker, timestamp, open, high, low, close, volume)
- [ ] `news_sentiment_daily` (ticker, date, avg_sentiment, headline_count)
- [ ] `strategies` (id, account_id, ticker, entry_rule, exit_rule, position_size)
- [ ] `backtest_runs` (id, strategy_id, total_return, max_drawdown, win_rate, `benchmark_return`, run_at)
- [ ] Indexes: `orders(account_id, status)`, `orders(is_backtest)`, unique `positions(account_id, ticker, is_backtest)`, `price_history_minute(ticker, timestamp)`, `news_sentiment_daily(ticker, date)`, `kyc_submissions(account_id, status)`
- [ ] No migration framework (Alembic) needed for a 3-week MVP — a single schema-creation script on startup is sufficient

---

## 24. GitLab CI/CD and containerization

### Dockerfiles
- [ ] `backend/Dockerfile`: Python slim base, `requirements.txt`, `uvicorn app.main:app --host 0.0.0.0 --port 8000`
- [ ] `frontend/Dockerfile`: multi-stage — Node build → Nginx serving `dist/`
- [ ] `.dockerignore` per service (`node_modules`, `__pycache__`, `.env`, `*.db`, `uploads/`)

### docker-compose.yml
- [ ] `backend` (8000), `frontend` (80, proxies `/api` and `/ws`), SQLite file **and** `uploads/` directory both on persistent volumes
- [ ] `/health` check on backend used by compose's `healthcheck`
- [ ] `ADMIN_BOOTSTRAP_USERNAME`/`ADMIN_BOOTSTRAP_PASSWORD` and the Claude API key passed via environment, never baked into the image

### `.gitlab-ci.yml`
```yaml
stages: [lint, test, build]

backend-lint:
  stage: lint
  rules: [{ changes: ["backend/**/*"] }]
  script: [cd backend, pip install -r requirements.txt, ruff check .]

backend-test:
  stage: test
  rules: [{ changes: ["backend/**/*"] }]
  script: [cd backend, pip install -r requirements.txt, pytest]

frontend-lint:
  stage: lint
  rules: [{ changes: ["frontend/**/*"] }]
  script: [cd frontend, npm ci, npm run lint]

backend-build:
  stage: build
  script: [docker build -t backend:$CI_COMMIT_SHORT_SHA ./backend]

frontend-build:
  stage: build
  script: [docker build -t frontend:$CI_COMMIT_SHORT_SHA ./frontend]
```
- [ ] `pytest` coverage on `order_engine.py` (incl. the KYC gate check), `indicators.py`, and `kyc_engine.py`'s auto-checks before CI is "done"
- [ ] Terraform/cloud: don't start until the pipeline is green and a full local `docker-compose up` demo works end-to-end, including the KYC → Admin-approve → trade flow

---

## 25. Build order (phased, with a Definition-of-Done gate before moving to the next phase)

- [ ] **Phase 1:** Module G + Section 23 schema + Section 7 auth/roles → gate: loaders produce correct counts, auth DoD passes (including admin-route 403 check)
- [ ] **Phase 2:** Module H (KYC) + Module I (Admin, at least the KYC review portion) → gate: submit → extract → auto-check → Admin approve/reject end-to-end works
- [ ] **Phase 3:** Module A (now including the KYC gate as check 0) → gate: full A DoD passes
- [ ] **Phase 4:** Module B (incl. `collateral_reserved`, lots endpoint) → gate: B DoD passes against a scripted trade sequence
- [ ] **Phase 5:** WebSocket channels (Section 17, including admin notifications) → gate: all four channels observably push correct messages
- [ ] **Phase 6:** Module D → gate: D DoD passes
- [ ] **Phase 7:** Module C → gate: C DoD passes
- [ ] **Phase 8:** Module E, including the `is_backtest` isolation (14.1) and the benchmark calc (14.2) → gate: E DoD passes, and a live-account portfolio check confirms a backtest run left `GET /api/portfolio` completely unchanged
- [ ] **Phase 9:** Module F remaining capabilities → gate: F DoD passes, guardrail tests explicitly verified
- [ ] **Phase 10:** Admin console remainder — accounts overview, audit logs, trade logs, compliance flags (I.2–I.5) → gate: I DoD passes fully
- [ ] **Phase 11:** Frontend — build every **[MVP]**-tagged item in Section 19 across all modules first, in the same module order as the backend phases above; only after all MVP items are done, pick up **[Stretch]** items if time remains
- [ ] **Phase 12:** Seed/demo data (Section 21) → gate: demo DoD passes, including the live-approvable pending KYC account
- [ ] **Phase 13:** Dockerization + CI (Section 24), incrementally as services stabilize
- [ ] **Phase 14:** Operational workflow docs (Section 22) and final presentation prep
