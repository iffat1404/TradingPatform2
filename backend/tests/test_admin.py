import pytest
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.core.db import get_db, Base
from app.core.security import get_password_hash, create_access_token
from app.models.orm import Account, Order, OrderEvent, Fill, KYCSubmission, PriceHistoryMinute, Position, Role, KYCStatus, OrderStatus, OrderSide, OrderType

TEST_DATABASE_URL = "sqlite:///./test_nomura_stp.db"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def _admin_token(db_session):
    admin = Account(
        id="admin_test_id",
        username="admin_test",
        password_hash=get_password_hash("admin123"),
        role=Role.ADMIN,
        kyc_status=KYCStatus.APPROVED,
    )
    db_session.add(admin)
    db_session.commit()
    return create_access_token({"sub": admin.id, "username": admin.username, "role": admin.role.value})


def _trader_account(db_session):
    trader = Account(
        id="trader_test_id",
        username="trader_test",
        password_hash=get_password_hash("trader123"),
        role=Role.TRADER,
        kyc_status=KYCStatus.APPROVED,
    )
    db_session.add(trader)
    db_session.commit()
    return trader


def test_admin_feed_reset_and_status(db_session):
    token = _admin_token(db_session)

    status_response = client.get(
        "/api/admin/feed/status",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert status_response.status_code == 200
    payload = status_response.json()
    assert payload["running"] is True
    assert payload["replay_speed"] == 1
    assert payload["current_timestamp"].endswith("Z")

    reset_response = client.post(
        "/api/admin/feed/reset",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert reset_response.status_code == 200
    reset_payload = reset_response.json()
    assert reset_payload["current_timestamp"].endswith("Z")


def test_admin_accounts_overview_returns_net_worth_and_order_count(db_session):
    token = _admin_token(db_session)
    trader = _trader_account(db_session)
    trader.cash_balance = 1250.0
    db_session.add(trader)
    db_session.add_all([
        Order(id="order_1", account_id=trader.id, ticker="AAPL", side=OrderSide.BUY, type=OrderType.MARKET, qty=1, status=OrderStatus.NEW, is_backtest=False, created_at=datetime.now(timezone.utc)),
        Order(id="order_2", account_id=trader.id, ticker="MSFT", side=OrderSide.SELL, type=OrderType.MARKET, qty=2, status=OrderStatus.NEW, is_backtest=False, created_at=datetime.now(timezone.utc)),
    ])
    db_session.commit()

    response = client.get(
        "/api/admin/accounts",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) >= 1
    account_summary = next(item for item in payload if item["id"] == trader.id)
    assert account_summary["net_worth"] == 1250.0
    assert account_summary["order_count"] == 2


def test_admin_accounts_overview_uses_latest_market_price(db_session):
    token = _admin_token(db_session)
    trader = _trader_account(db_session)
    trader.cash_balance = 1000.0
    db_session.add(trader)
    db_session.add(Position(
        id="position_live",
        account_id=trader.id,
        ticker="AAPL",
        signed_qty=1,
        avg_cost=100.0,
        realized_pnl=0.0,
        collateral_reserved=0.0,
        is_backtest=False,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    ))
    db_session.add(PriceHistoryMinute(
        ticker="AAPL",
        timestamp=datetime.now(timezone.utc),
        open=120.0,
        high=121.0,
        low=119.0,
        close=120.0,
        volume=1000,
    ))
    db_session.commit()

    response = client.get(
        "/api/admin/accounts",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    account_summary = next(item for item in payload if item["id"] == trader.id)
    assert account_summary["net_worth"] == 1120.0


def test_admin_flags_endpoint_returns_kyc_and_trade_flags(db_session):
    token = _admin_token(db_session)
    trader = _trader_account(db_session)

    submission = KYCSubmission(
        id="kyc_flag_submission",
        account_id=trader.id,
        id_type="passport",
        document_path="/tmp/test.pdf",
        auto_check_passed=False,
        auto_check_notes="name mismatch",
        status=KYCStatus.PENDING_REVIEW,
        submitted_at=datetime.now(timezone.utc),
    )
    db_session.add(submission)

    order = Order(
        id="order_flag",
        account_id=trader.id,
        ticker="AAPL",
        side=OrderSide.BUY,
        type=OrderType.MARKET,
        qty=5,
        status=OrderStatus.NEW,
        is_backtest=False,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(order)
    db_session.flush()

    db_session.add(OrderEvent(
        id="event_flag",
        order_id=order.id,
        from_state=OrderStatus.NEW,
        to_state=OrderStatus.VALIDATED,
        reason="WASH_TRADE_FLAGGED",
        is_backtest=False,
        timestamp=datetime.now(timezone.utc),
    ))
    db_session.commit()

    response = client.get(
        "/api/admin/flags",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert any(item["type"] == "KYC_REVIEW" for item in payload)
    assert any(item["type"] == "WASH_TRADE" for item in payload)


def test_admin_audit_and_trade_logs_default_to_live_only(db_session):
    token = _admin_token(db_session)
    trader = _trader_account(db_session)

    live_order = Order(
        id="order_live",
        account_id=trader.id,
        ticker="AAPL",
        side=OrderSide.BUY,
        type=OrderType.MARKET,
        qty=10,
        status=OrderStatus.NEW,
        is_backtest=False,
        created_at=datetime.now(timezone.utc),
    )
    backtest_order = Order(
        id="order_backtest",
        account_id=trader.id,
        ticker="AAPL",
        side=OrderSide.SELL,
        type=OrderType.MARKET,
        qty=5,
        status=OrderStatus.NEW,
        is_backtest=True,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add_all([live_order, backtest_order])
    db_session.flush()

    db_session.add_all([
        OrderEvent(
            id="event_live",
            order_id=live_order.id,
            from_state=OrderStatus.NEW,
            to_state=OrderStatus.VALIDATED,
            reason="VALIDATED",
            is_backtest=False,
            timestamp=datetime.now(timezone.utc),
        ),
        OrderEvent(
            id="event_backtest",
            order_id=backtest_order.id,
            from_state=OrderStatus.NEW,
            to_state=OrderStatus.VALIDATED,
            reason="VALIDATED",
            is_backtest=True,
            timestamp=datetime.now(timezone.utc),
        ),
        Fill(
            id="fill_live",
            order_id=live_order.id,
            fill_price=100.0,
            fill_qty=10,
            fees=1.0,
            is_backtest=False,
            timestamp=datetime.now(timezone.utc),
        ),
        Fill(
            id="fill_backtest",
            order_id=backtest_order.id,
            fill_price=95.0,
            fill_qty=5,
            fees=1.0,
            is_backtest=True,
            timestamp=datetime.now(timezone.utc),
        ),
    ])
    db_session.commit()

    audit_response = client.get(
        "/api/admin/audit-logs",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert audit_response.status_code == 200
    audit_payload = audit_response.json()
    assert len(audit_payload) == 1
    assert audit_payload[0]["order_id"] == live_order.id
    assert audit_payload[0]["is_backtest"] is False

    trade_response = client.get(
        "/api/admin/trade-logs",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert trade_response.status_code == 200
    trade_payload = trade_response.json()
    assert len(trade_payload) == 1
    assert trade_payload[0]["order_id"] == live_order.id
    assert trade_payload[0]["is_backtest"] is False
