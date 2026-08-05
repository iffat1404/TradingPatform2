# Frontend Build Plan — Nomura STP

Status: in progress. This is the working plan for the React frontend, built against the
existing FastAPI backend in `backend/`. (Earlier claims in `README.md` that a frontend was
already complete were aspirational — no `frontend/` directory existed before this plan.)

## Stack

Vite + React 18, plain JavaScript. `react-router-dom`, `axios`, `recharts`,
`lightweight-charts`. No Tailwind/component library/state-management library — a hand-rolled
CSS design system (`src/styles/tokens.css`) and React Context are enough for this app.

## Design system

**Palette** — Cape Cod `#414648` (dark ink), Tana `#d4d6bc` (warm khaki), Envy `#86a48a`
(sage — primary/trader accent), Manatee `#8689aa` (muted violet — secondary/admin accent),
White `#ffffff`, plus one added negative/danger color, Sienna `#b3624b` (the given palette
has no red).

- Landing page: light/warm register (Tana canvas, Cape Cod text, Envy CTA).
- Trader & Admin dashboards: dark register (Cape Cod canvas), same shell/components, but the
  accent swaps — Envy for trader, Manatee for admin — so the two modes are visually distinct
  without duplicating UI.

**Type** — Fraunces (display/headlines only), Inter (UI/body), IBM Plex Mono (tickers,
prices, order IDs, tabular data).

**Signature — the Process Rail**: orders in this system move through a real, deterministic
pipeline (`NEW → VALIDATED → ROUTED → FILLED`, or diverted to `REJECTED`/`CANCELLED`). One
stepper component visualizes this in three places: the landing hero (animated), each Recent
Orders / Orders row (compact), and the dashboard topbar as a live "pulse" driven by the
`/ws/session` MarketClock broadcast.

## Ground-truth API contract

The backend's own `BACKEND_ARCHITECTURE.md` has several inaccuracies versus the actual code
(`orm.py` / `schemas.py` / `security.py` / `config.py`). The frontend is built against the
**code**, not the doc:

- JWT: `Authorization: Bearer <token>`, claims `sub` (account id) / `username` / `role` /
  `exp`. **Expires in 30 minutes** (doc says 60).
- Role wire values: lowercase `"trader"` / `"admin"`.
- KYCStatus: `NOT_STARTED, PENDING_REVIEW, APPROVED, REJECTED` (doc wrongly has
  `PENDING_SUBMISSION`).
- OrderSide `"buy"`/`"sell"`, OrderType `"market"`/`"limit"` — lowercase in requests **and**
  responses.
- OrderStatus: `NEW, VALIDATED, ROUTED, FILLED, REJECTED, CANCELLED` — no `PENDING` or
  `PARTIAL_FILLED` (no partial fills, ever).
- `OrderCreate`: `ticker, side, type, qty` (alias `quantity`), `limit_price?`,
  `time_in_force?`. `PortfolioResponse`: `account_id, cash_balance, net_worth, positions[],
  collateral_reserved`. `PositionResponse` has no embedded current price — fetch from
  `/api/prices/*` when needed.
- Backend runs at `http://127.0.0.1:8000`, CORS wide open. Frontend reads base URL from
  `VITE_API_BASE_URL`.

## AI Trading Journal (2026-08-05)

A trader-private journal where a trader logs the rationale and emotional state behind a
trade; the app correlates that with real order/fill history to flag behavioural patterns
(FOMO, revenge trading, overtrading, low journaling discipline) and coaches on them.

**Architecture — deterministic first, AI second.** `backend/app/services/journal_engine.py`
computes every flag with plain rules over real `Order`/`Fill` rows
(`detect_patterns`). Claude is only ever asked to *narrate* those findings; it never
decides them. This upholds platform principle 1 and means the feature works fully with no
`ANTHROPIC_API_KEY` — the deterministic branch returns real coaching text, tagged
`generated_by: "deterministic"` (the UI states which was used).

- **Model**: `JournalEntry` in `orm.py`. Emotional tags / AI flags are stored comma-joined
  (matching the existing `auto_check_notes` precedent) and expanded to lists in
  `serialize_entry`. `Account.journal_entries` relationship added.
- **Vocabulary**: `ALLOWED_EMOTIONAL_TAGS` in `schemas.py` is a closed list — free text
  would make "which mood precedes losses?" unanswerable in aggregate. Unknown tags are
  silently dropped at write time.
- **Endpoints**: `/api/journal/{tags,entries,entries/{id},entries/{id}/analyze,insights}`.
  Every one is scoped to `current_user["account_id"]`; a foreign entry or a foreign
  `order_id` returns 404, so there is no cross-account leakage (principle 4). Note
  `/insights` is declared **before** `/entries/{entry_id}` in the router — FastAPI matches
  in declaration order, so the reverse would make `insights` be parsed as an entry id.
- **Caching**: `analyze` caches feedback on the row; `?regenerate=true` forces a fresh call.
  Nothing calls Claude automatically — only an explicit button press does.
- **Admin visibility**: none, by design. Journals are private to the trader.

Frontend is `src/pages/trader/JournalPage.jsx` + `src/api/journal.js`, reusing `Card`,
`StatCard`, `Badge`, `Modal`, `Button`, `Field`; journal-specific CSS lives in the
"Trading journal" section of `trader-pages.css`. Tag chips are colour-coded by behavioural
meaning (risk emotions negative, disciplined/confident positive) so a wall of chips still
reads at a glance.

**Also fixed here**: `.topbar-actions` (clock + bell + avatar) was wider than a phone
viewport, putting *every* trader page into horizontal scroll at 390px. The topbar now wraps
to a second row under 720px — a pre-existing bug the journal's responsive check surfaced.

## Landing page motion pass (2026-08-05)

Added `framer-motion` (scoped to the landing page only — the rest of the app stays on plain
CSS transitions) for: staggered hero fade-up on load, `whileInView` scroll-triggered feature
card entrances, and hover/tap gestures on the primary CTA. Everything else uses CSS
keyframes. Notes for future edits:

- **Vite dep-cache gotcha**: installing a new npm package while the Vite dev server is
  already running can leave its `optimizeDeps` cache stale, producing a cryptic
  `Cannot read properties of null (reading 'useContext')` crash from the new library. Fix is
  `rm -rf node_modules/.vite` and restart the dev server, not a code change.
- **Never let Framer Motion and CSS animate the same transform on the same element.** The
  feature cards use Framer's `whileHover={{ y: -6 }}` for the lift, while CSS `:hover` only
  touches `border-color`/`box-shadow`/the icon's `background`/`color` — if both tried to set
  `transform`, one clobbers the other on every re-render.
- Reduced motion is handled two ways: `<MotionConfig reducedMotion="user">` wraps the page
  for Framer-driven animation, and plain `@media (prefers-reduced-motion: reduce)` blocks
  disable the CSS keyframes (beam sweep, ping, mesh blobs, ticker marquee).
- `TickerTape` now reads `useMarketClock().marketStatus` to distinguish a genuine feed
  failure from the simulator's normal closed-market state (its minute-level dataset only
  has ticks during 09:30–16:00 UTC) — don't revert that to a blind "no rows = error" check.

## Bugs found and fixed during integration

Two backend bugs made the app appear dead ("stuck connecting to live feed", "no order is
getting placed"):

1. **DB connection-pool exhaustion via WebSockets** (`app/api/websockets.py`). The
   `/ws/market/{ticker}`, `/ws/market/all` and `/ws/account/{id}` handlers each held a
   pooled SQLAlchemy session for the *entire lifetime* of the socket. With the default pool
   (5 + 10 overflow), ~15 open sockets starved every HTTP request of a connection, so every
   DB-backed endpoint returned 500 while `/health` still looked fine. Fixed by opening a
   short-lived session per tick (`_with_session`) and giving the pool real headroom in
   `app/core/db.py`. Reproduced at 18 sockets, verified fixed at 60.
2. **Market-hours checked against real wall-clock time** (`app/services/order_engine.py`).
   `validate_order` used `datetime.now(timezone.utc)` instead of the MarketClock, so orders
   were rejected with `MARKET_CLOSED` unless the operator's real-world UTC time happened to
   fall between 09:30-16:00 — regardless of the simulated session. Every other timestamp in
   that same file already used `market_clock.now()`. Fixed to use the MarketClock, which is
   the platform's stated single source of truth.

Frontend fixes made alongside: WebSocket reconnect now uses exponential backoff and detaches
handlers on teardown (a teardown-triggered `onclose` could previously schedule a reconnect
for an abandoned socket); the ticker tape reports a real failure instead of showing
"Connecting…" forever; the Trade page re-checks KYC on mount so an admin approval lifts the
gate without a re-login; and several tables were reading field names the API never sends
(see below).

## Field-name mismatches to watch

The API's wire format differs from what the architecture doc implies in several places.
Verified against the live server:

- `OrderResponse.qty` is declared with `alias="quantity"` and serializes as **`quantity`**.
- `GET /api/orders/{id}/events` returns **`from_status` / `to_status` / `event_type` /
  `notes`** — not the `OrderEventResponse` schema's `from_state`/`to_state`/`reason`.
- `GET /api/admin/audit-logs` returns `from_state`/`to_state`/`reason`/`order_id` — there is
  **no** `username`, `ticker`, `action`, `details`, or `reason_code`.
- `GET /api/admin/trade-logs` returns fills: `fill_price`/`fill_qty`/`fees`/`order_id` —
  **no** `side`, `qty`, `status`, or `username`.
- `GET /api/admin/kyc` (list) has **no username** — only `account_id`, plus
  `auto_check_passed`/`auto_check_notes`. The detail endpoint adds **`account_username`**
  (not `username`) and the `extracted_*` fields.

`src/utils/format.js` has `orderQty()` and `shortId()` helpers for these.

## Routes

```
/                      Landing (public)
/login                 Login (redirects to /trader or /admin if already authed)
/register              Register (creates trader accounts only)
/trader/*              overview | trade | portfolio | orders | analytics | backtesting | ai-assistant | kyc | settings
/admin/*               overview | kyc-queue | accounts | audit-logs | trade-logs | compliance | feed-control
```

## Backend endpoint coverage map

| Module | Surfaces in |
|---|---|
| auth | Register, Login, AuthContext (topbar identity everywhere) |
| kyc | Trader → KYC page |
| admin (kyc) | Admin → KYC Queue |
| admin (accounts) | Admin → Accounts |
| admin (logs/flags) | Admin → Audit Logs, Trade Logs, Compliance Flags |
| admin (session/feed) | Admin → Feed & Session Control |
| orders | Trader → Trade (create/cancel), Orders (list/events) |
| portfolio | Trader → Portfolio (summary/pnl/exposure/positions/lots drill-down) |
| reports | Trader → Portfolio (report view + CSV export) |
| analytics | Trader → Analytics |
| paper_trading | Trader → Backtesting |
| genai | Trader → Overview AI card, AI Assistant page, inline on rejected orders |
| prices | Trade chart, Overview market/top-movers, ticker tape |
| websockets | Ticker tape + chart live updates, topbar pulse, order-fill toasts, admin bell |

## Build phases

1. Scaffold — tokens, layout primitives, router, AuthContext, axios client, Landing, Login, Register.
2. Trader core — layout, Overview, Trade, Portfolio, Orders + charts.
3. Trader secondary — Analytics, Backtesting, AI Assistant, KYC, Settings, Logout.
4. Admin console — layout + 7 pages.
5. Polish + end-to-end verification against the live backend.
