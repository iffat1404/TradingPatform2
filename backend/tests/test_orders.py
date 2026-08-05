import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.core.db import get_db, Base
from app.core.security import get_password_hash, create_access_token
from app.models.orm import Account, Role, KYCStatus, OrderSide, OrderType
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

# Create test database
TEST_DATABASE_URL = "sqlite:///./test_nomura_stp.db"
engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


@pytest.fixture
def db_session():
    """Create a fresh database session for each test"""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def approved_trader_token(db_session):
    """Create an approved trader user and return their token"""
    trader = Account(
        id="order_test_id",
        username="order_test",
        password_hash=get_password_hash("trader123"),
        role=Role.TRADER,
        kyc_status=KYCStatus.APPROVED,
        starting_capital=1_000_000.0,
        cash_balance=1_000_000.0
    )
    db_session.add(trader)
    db_session.commit()
    
    token = create_access_token({
        "sub": trader.id,
        "username": trader.username,
        "role": trader.role.value
    })
    
    return token


@pytest.fixture
def pending_trader_token(db_session):
    """Create a pending KYC trader user"""
    trader = Account(
        id="pending_test_id",
        username="pending_test",
        password_hash=get_password_hash("trader123"),
        role=Role.TRADER,
        kyc_status=KYCStatus.PENDING_REVIEW,
        starting_capital=1_000_000.0,
        cash_balance=1_000_000.0
    )
    db_session.add(trader)
    db_session.commit()
    
    token = create_access_token({
        "sub": trader.id,
        "username": trader.username,
        "role": trader.role.value
    })
    
    return token


class TestOrderValidation:
    """Test order validation chain"""
    
    def test_order_with_kyc_not_approved_rejected(self, db_session, pending_trader_token):
        """Test that order is rejected when KYC not approved (check 0)"""
        response = client.post(
            "/api/orders",
            headers={"Authorization": f"Bearer {pending_trader_token}"},
            json={
                "ticker": "AAPL",
                "side": "buy",
                "type": "market",
                "qty": 10
            }
        )
        
        assert response.status_code == 422
        data = response.json()["detail"]
        assert data["error_code"] == "KYC_NOT_APPROVED"
    
    def test_order_with_invalid_ticker_rejected(self, db_session, approved_trader_token):
        """Test that order is rejected with invalid ticker (check 1)"""
        response = client.post(
            "/api/orders",
            headers={"Authorization": f"Bearer {approved_trader_token}"},
            json={
                "ticker": "INVALID",
                "side": "buy",
                "type": "market",
                "qty": 10
            }
        )
        
        assert response.status_code == 422
        data = response.json()["detail"]
        assert data["error_code"] == "INVALID_TICKER"
    
    def test_order_with_price_collar_breach_rejected(self, db_session, approved_trader_token):
        """Test that limit order is rejected with price collar breach (check 3)"""
        response = client.post(
            "/api/orders",
            headers={"Authorization": f"Bearer {approved_trader_token}"},
            json={
                "ticker": "AAPL",
                "side": "buy",
                "type": "limit",
                "qty": 10,
                "limit_price": 50.0  # Way below current price of 100
            }
        )
        
        assert response.status_code == 422
        data = response.json()["detail"]
        assert data["error_code"] == "PRICE_COLLAR_BREACH"
    
    def test_order_with_notional_limit_exceeded_rejected(self, db_session, approved_trader_token):
        """Test that order is rejected with notional limit exceeded (check 4)"""
        response = client.post(
            "/api/orders",
            headers={"Authorization": f"Bearer {approved_trader_token}"},
            json={
                "ticker": "AAPL",
                "side": "buy",
                "type": "market",
                "qty": 10000  # 10000 * 100 = 1,000,000 > 250,000 limit
            }
        )
        
        assert response.status_code == 422
        data = response.json()["detail"]
        assert data["error_code"] == "NOTIONAL_LIMIT_EXCEEDED"
    
    def test_order_with_insufficient_buying_power_rejected(self, db_session, approved_trader_token):
        """Test that order is rejected with insufficient buying power (check 6)"""
        # Update account to have low cash
        db = TestingSessionLocal()
        account = db.query(Account).filter(Account.username == "order_test").first()
        account.cash_balance = 100.0
        db.commit()
        
        response = client.post(
            "/api/orders",
            headers={"Authorization": f"Bearer {approved_trader_token}"},
            json={
                "ticker": "AAPL",
                "side": "buy",
                "type": "market",
                "qty": 10  # 10 * 100 = 1000 + 1 fee = 1001 > 100
            }
        )
        
        assert response.status_code == 422
        data = response.json()["detail"]
        assert data["error_code"] == "INSUFFICIENT_BUYING_POWER"
        
        db.close()
    
    def test_order_with_insufficient_collateral_rejected(self, db_session, approved_trader_token):
        """Test that short order is rejected with insufficient collateral (check 6)"""
        # Update account to have low cash
        db = TestingSessionLocal()
        account = db.query(Account).filter(Account.username == "order_test").first()
        account.cash_balance = 100.0
        db.commit()
        
        response = client.post(
            "/api/orders",
            headers={"Authorization": f"Bearer {approved_trader_token}"},
            json={
                "ticker": "AAPL",
                "side": "sell",
                "type": "market",
                "qty": 100  # 100 * 100 * 1.5 = 15,000 > 100
            }
        )
        
        assert response.status_code == 422
        data = response.json()["detail"]
        assert data["error_code"] == "INSUFFICIENT_BUYING_POWER"
        
        db.close()


class TestOrderExecution:
    """Test order execution and state machine"""
    
    def test_market_order_fills_immediately(self, db_session, approved_trader_token):
        """Test that market order fills immediately at synthetic bid/ask"""
        response = client.post(
            "/api/orders",
            headers={"Authorization": f"Bearer {approved_trader_token}"},
            json={
                "ticker": "AAPL",
                "side": "buy",
                "type": "market",
                "qty": 10
            }
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "FILLED"
        assert data["ticker"] == "AAPL"
        assert data["side"] == "buy"
        assert data["qty"] == 10
    
    def test_limit_order_marketable_on_arrival_fills(self, db_session, approved_trader_token):
        """Test that limit order fills immediately if marketable on arrival"""
        response = client.post(
            "/api/orders",
            headers={"Authorization": f"Bearer {approved_trader_token}"},
            json={
                "ticker": "AAPL",
                "side": "buy",
                "type": "limit",
                "qty": 10,
                "limit_price": 105.0  # Above synthetic ask (100 + 0.04)
            }
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "FILLED"
    
    def test_limit_order_not_marketable_rests(self, db_session, approved_trader_token):
        """Test that limit order rests if not marketable on arrival"""
        response = client.post(
            "/api/orders",
            headers={"Authorization": f"Bearer {approved_trader_token}"},
            json={
                "ticker": "AAPL",
                "side": "buy",
                "type": "limit",
                "qty": 10,
                "limit_price": 95.0  # Below synthetic bid (100 - 0.04)
            }
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "VALIDATED"  # Rests, not filled


class TestOrderManagement:
    """Test order management endpoints"""
    
    def test_get_orders_returns_user_orders(self, db_session, approved_trader_token):
        """Test that GET /api/orders returns user's orders"""
        # Create an order first
        client.post(
            "/api/orders",
            headers={"Authorization": f"Bearer {approved_trader_token}"},
            json={
                "ticker": "AAPL",
                "side": "buy",
                "type": "market",
                "qty": 10
            }
        )
        
        response = client.get(
            "/api/orders",
            headers={"Authorization": f"Bearer {approved_trader_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0
        assert data[0]["ticker"] == "AAPL"
    
    def test_get_order_by_id(self, db_session, approved_trader_token):
        """Test that GET /api/orders/{id} returns specific order"""
        # Create an order first
        create_response = client.post(
            "/api/orders",
            headers={"Authorization": f"Bearer {approved_trader_token}"},
            json={
                "ticker": "AAPL",
                "side": "buy",
                "type": "limit",
                "qty": 10,
                "limit_price": 95.0
            }
        )
        
        order_id = create_response.json()["id"]
        
        response = client.get(
            f"/api/orders/{order_id}",
            headers={"Authorization": f"Bearer {approved_trader_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == order_id
        assert data["ticker"] == "AAPL"
    
    def test_cancel_resting_limit_order(self, db_session, approved_trader_token):
        """Test that DELETE /api/orders/{id} cancels resting limit order"""
        # Create a resting limit order
        create_response = client.post(
            "/api/orders",
            headers={"Authorization": f"Bearer {approved_trader_token}"},
            json={
                "ticker": "AAPL",
                "side": "buy",
                "type": "limit",
                "qty": 10,
                "limit_price": 95.0
            }
        )
        
        order_id = create_response.json()["id"]
        
        # Cancel it
        response = client.delete(
            f"/api/orders/{order_id}",
            headers={"Authorization": f"Bearer {approved_trader_token}"}
        )
        
        assert response.status_code == 200
        assert response.json()["message"] == "Order cancelled"
    
    def test_cancel_filled_order_fails(self, db_session, approved_trader_token):
        """Test that cancelling a filled order fails"""
        # Create a market order (will fill immediately)
        create_response = client.post(
            "/api/orders",
            headers={"Authorization": f"Bearer {approved_trader_token}"},
            json={
                "ticker": "AAPL",
                "side": "buy",
                "type": "market",
                "qty": 10
            }
        )
        
        order_id = create_response.json()["id"]
        
        # Try to cancel it
        response = client.delete(
            f"/api/orders/{order_id}",
            headers={"Authorization": f"Bearer {approved_trader_token}"}
        )
        
        assert response.status_code == 400
    
    def test_get_order_events(self, db_session, approved_trader_token):
        """Test that GET /api/orders/{id}/events returns event trail"""
        # Create an order
        create_response = client.post(
            "/api/orders",
            headers={"Authorization": f"Bearer {approved_trader_token}"},
            json={
                "ticker": "AAPL",
                "side": "buy",
                "type": "market",
                "qty": 10
            }
        )
        
        order_id = create_response.json()["id"]
        
        # Get events
        response = client.get(
            f"/api/orders/{order_id}/events",
            headers={"Authorization": f"Bearer {approved_trader_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0
        # Should have events for state transitions
        event_types = [e["event_type"] for e in data]
        assert "VALIDATION_PASSED" in event_types
        assert "ROUTED" in event_types
        assert "FILL" in event_types


if __name__ == "__main__":
    pytest.main([__file__, "-v"])