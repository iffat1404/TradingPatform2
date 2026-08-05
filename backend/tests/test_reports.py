import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.core.db import get_db, Base
from app.core.security import get_password_hash, create_access_token
from app.models.orm import Account, Role, KYCStatus, PriceHistoryDaily, PriceHistoryMinute
from datetime import datetime, timedelta
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
        id="reports_test_id",
        username="reports_test",
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


@pytest.fixture
def sample_daily_data(db_session):
    """Create sample daily price data"""
    base_date = datetime(2024, 1, 1)
    for i in range(130):
        price = PriceHistoryDaily(
            ticker="AAPL",
            date=base_date + timedelta(days=i),
            open=150.0 + i,
            high=155.0 + i,
            low=145.0 + i,
            close=152.0 + i,
            volume=1000000
        )
        db_session.add(price)
    db_session.commit()


@pytest.fixture
def sample_minute_data(db_session):
    """Create sample minute-level price data"""
    base_time = datetime(2024, 1, 1, 9, 30)
    for i in range(100):
        price = PriceHistoryMinute(
            ticker="AAPL",
            timestamp=base_time + timedelta(minutes=i),
            open=150.0 + (i * 0.1),
            high=155.0 + (i * 0.1),
            low=145.0 + (i * 0.1),
            close=152.0 + (i * 0.1),
            volume=10000
        )
        db_session.add(price)
    db_session.commit()


class TestDailyPrices:
    """Test daily price endpoints"""
    
    def test_get_daily_prices(self, db_session, sample_daily_data):
        """Test GET /api/prices/{ticker}/daily returns 130 bars"""
        response = client.get("/api/prices/AAPL/daily")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 130
        # Verify structure
        assert "date" in data[0]
        assert "open" in data[0]
        assert "high" in data[0]
        assert "low" in data[0]
        assert "close" in data[0]
        assert "volume" in data[0]
    
    def test_get_daily_prices_not_found(self, db_session):
        """Test GET /api/prices/{ticker}/daily returns 404 for invalid ticker"""
        response = client.get("/api/prices/INVALID/daily")
        
        assert response.status_code == 404


class TestIntradayPrices:
    """Test intraday price endpoints"""
    
    def test_get_intraday_prices_default_interval(self, db_session, sample_minute_data):
        """Test GET /api/prices/{ticker}/intraday with default 5m interval"""
        response = client.get("/api/prices/AAPL/intraday")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        assert "timestamp" in data[0]
        assert "open" in data[0]
        assert "high" in data[0]
        assert "low" in data[0]
        assert "close" in data[0]
        assert "volume" in data[0]
    
    def test_get_intraday_prices_1m_interval(self, db_session, sample_minute_data):
        """Test GET /api/prices/{ticker}/intraday with 1m interval"""
        response = client.get("/api/prices/AAPL/intraday?interval=1m")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    def test_get_intraday_prices_invalid_interval(self, db_session):
        """Test GET /api/prices/{ticker}/intraday with invalid interval"""
        response = client.get("/api/prices/AAPL/intraday?interval=invalid")
        
        assert response.status_code == 400
    
    def test_get_intraday_prices_not_found(self, db_session):
        """Test GET /api/prices/{ticker}/intraday returns 404 for invalid ticker"""
        response = client.get("/api/prices/INVALID/intraday")
        
        assert response.status_code == 404


class TestPortfolioReports:
    """Test portfolio report endpoints"""
    
    def test_get_portfolio_report(self, db_session, approved_trader_token):
        """Test GET /api/reports/portfolio returns portfolio report"""
        response = client.get(
            "/api/reports/portfolio",
            headers={"Authorization": f"Bearer {approved_trader_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "generated_at" in data
        assert "account_id" in data
        assert "metrics" in data
        assert "positions" in data
    
    def test_export_portfolio_csv(self, db_session, approved_trader_token):
        """Test GET /api/reports/portfolio/export returns CSV"""
        response = client.get(
            "/api/reports/portfolio/export?format=csv",
            headers={"Authorization": f"Bearer {approved_trader_token}"}
        )
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"
        assert "attachment" in response.headers["content-disposition"]
        
        # Verify CSV content
        csv_content = response.text
        assert "Position Report" in csv_content
        assert "Ticker" in csv_content
        assert "Net Worth" in csv_content
    
    def test_export_portfolio_invalid_format(self, db_session, approved_trader_token):
        """Test GET /api/reports/portfolio/export with invalid format"""
        response = client.get(
            "/api/reports/portfolio/export?format=pdf",
            headers={"Authorization": f"Bearer {approved_trader_token}"}
        )
        
        assert response.status_code == 400


if __name__ == "__main__":
    pytest.main([__file__, "-v"])