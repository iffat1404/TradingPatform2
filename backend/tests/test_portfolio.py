import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.core.db import get_db, Base
from app.core.security import get_password_hash, create_access_token
from app.models.orm import Account, Role, KYCStatus, OrderSide
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


@pytest.fixture(scope="module", autouse=True)
def setup_database():
    """Create tables before running tests"""
    Base.metadata.create_all(bind=engine)
    yield
    # Note: Cleanup skipped to avoid file lock issues on Windows


@pytest.fixture
def approved_trader_token(db_session):
    """Create an approved trader user and return their token"""
    trader = Account(
        id="portfolio_test_id",
        username="portfolio_test",
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
def db_session():
    """Create a fresh database session for each test"""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


class TestPortfolioEndpoints:
    """Test portfolio API endpoints"""
    
    def test_get_portfolio_summary(self, db_session, approved_trader_token):
        """Test GET /api/portfolio returns portfolio summary"""
        response = client.get(
            "/api/portfolio",
            headers={"Authorization": f"Bearer {approved_trader_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "cash_balance" in data
        assert "net_worth" in data
        assert "positions" in data
        assert data["cash_balance"] == 1_000_000.0
    
    def test_get_portfolio_pnl(self, db_session, approved_trader_token):
        """Test GET /api/portfolio/pnl returns P&L breakdown"""
        response = client.get(
            "/api/portfolio/pnl",
            headers={"Authorization": f"Bearer {approved_trader_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "unrealized_pnl" in data
        assert "realized_pnl" in data
        assert "total_pnl" in data
    
    def test_get_portfolio_exposure(self, db_session, approved_trader_token):
        """Test GET /api/portfolio/exposure returns exposure breakdown"""
        response = client.get(
            "/api/portfolio/exposure",
            headers={"Authorization": f"Bearer {approved_trader_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "gross_exposure" in data
        assert "net_exposure" in data
        assert "ticker_exposure" in data
        assert "sector_exposure" in data
    
    def test_get_ticker_lots_empty(self, db_session, approved_trader_token):
        """Test GET /api/portfolio/{ticker}/lots returns empty list for no position"""
        response = client.get(
            "/api/portfolio/AAPL/lots",
            headers={"Authorization": f"Bearer {approved_trader_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0


class TestPortfolioCalculations:
    """Test portfolio calculation logic"""
    
    def test_net_worth_calculation_with_positions(self, db_session, approved_trader_token):
        """Test net worth calculation with positions"""
        from app.services.portfolio_engine import update_position_with_lots
        from app.models.orm import Account
        
        # Get initial cash
        account = db_session.query(Account).filter(Account.id == "portfolio_test_id").first()
        initial_cash = account.cash_balance
        
        # Create a position
        update_position_with_lots(db_session, "portfolio_test_id", "AAPL", OrderSide.BUY, 100, 150.0)
        
        # Refresh account to get updated cash
        db_session.refresh(account)
        
        # Get portfolio
        current_prices = {"AAPL": 160.0}
        from app.services.portfolio_engine import calculate_portfolio_metrics
        metrics = calculate_portfolio_metrics(db_session, "portfolio_test_id", current_prices)
        
        # Net worth = cash (after buy) + market value (100*160) - collateral (0)
        expected_market_value = 100 * 160.0
        expected_net_worth = account.cash_balance + expected_market_value
        
        assert abs(metrics["net_worth"] - expected_net_worth) < 0.01
    
    def test_unrealized_pnl_calculation(self, db_session, approved_trader_token):
        """Test unrealized P&L calculation"""
        from app.services.portfolio_engine import update_position_with_lots, calculate_portfolio_metrics
        
        # Create a position
        update_position_with_lots(db_session, "portfolio_test_id", "AAPL", OrderSide.BUY, 100, 150.0)
        
        # Calculate with higher price
        current_prices = {"AAPL": 160.0}
        metrics = calculate_portfolio_metrics(db_session, "portfolio_test_id", current_prices)
        
        # Unrealized P&L = 100 * (160 - 150) = 1000
        assert abs(metrics["unrealized_pnl"] - 1000.0) < 0.01
    
    def test_sector_mapping(self, db_session, approved_trader_token):
        """Test sector mapping for different tickers"""
        from app.services.portfolio_engine import update_position_with_lots, calculate_portfolio_metrics
        
        # Create positions in different sectors
        update_position_with_lots(db_session, "portfolio_test_id", "AAPL", OrderSide.BUY, 10, 150.0)  # Technology
        update_position_with_lots(db_session, "portfolio_test_id", "WMT", OrderSide.BUY, 10, 150.0)  # Consumer Staples
        
        current_prices = {"AAPL": 160.0, "WMT": 160.0}
        metrics = calculate_portfolio_metrics(db_session, "portfolio_test_id", current_prices)
        
        assert "Technology" in metrics["sector_exposure"]
        assert "Consumer Staples" in metrics["sector_exposure"]
        assert metrics["sector_exposure"]["Technology"] > 0
        assert metrics["sector_exposure"]["Consumer Staples"] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])