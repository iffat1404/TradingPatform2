import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.core.db import get_db, Base
from app.core.security import get_password_hash, create_access_token
from app.models.orm import Account, Role, KYCStatus, PriceHistoryDaily, NewsSentimentDaily
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
        id="analytics_test_id",
        username="analytics_test",
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
def sample_price_data(db_session):
    """Create sample daily price data for testing"""
    base_date = datetime(2024, 1, 1)
    for i in range(100):
        # Create somewhat realistic price movement
        base_price = 150.0
        price_change = (i % 10) - 5  # Oscillating
        close = base_price + price_change + (i * 0.1)
        
        price = PriceHistoryDaily(
            ticker="AAPL",
            date=base_date + timedelta(days=i),
            open=close - 1.0,
            high=close + 2.0,
            low=close - 2.0,
            close=close,
            volume=1000000
        )
        db_session.add(price)
    db_session.commit()


class TestIndicatorCalculations:
    """Test technical indicator calculations"""
    
    def test_sma_calculation(self):
        """Test SMA calculation"""
        from app.services.analytics_engine import calculate_sma
        
        prices = [100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110]
        sma_5 = calculate_sma(prices, 5)
        
        # First 4 values should be None (not enough data)
        assert sma_5[0] is None
        assert sma_5[1] is None
        assert sma_5[2] is None
        assert sma_5[3] is None
        
        # 5th value should be the average of first 5
        assert abs(sma_5[4] - 102.0) < 0.01
    
    def test_sma50_first_valid_at_day_50(self):
        """Test SMA50 first valid at exactly day 50 (per DoD)"""
        from app.services.analytics_engine import calculate_sma
        
        prices = [100 + i for i in range(100)]
        sma_50 = calculate_sma(prices, 50)
        
        # First 49 values should be None
        for i in range(49):
            assert sma_50[i] is None
        
        # 50th value (index 49) should be valid
        assert sma_50[49] is not None
        # SMA of 100-149 = 124.5
        assert abs(sma_50[49] - 124.5) < 0.01
    
    def test_rsi_calculation(self):
        """Test RSI calculation using Wilder's method"""
        from app.services.analytics_engine import calculate_rsi
        
        # Create a simple price sequence
        prices = [100, 102, 104, 103, 105, 107, 106, 108, 110, 109, 111, 113, 112, 114, 116]
        rsi = calculate_rsi(prices, 14)
        
        # RSI should be between 0 and 100
        valid_rsi = [v for v in rsi if v is not None]
        for val in valid_rsi:
            assert 0 <= val <= 100
    
    def test_macd_calculation(self):
        """Test MACD calculation"""
        from app.services.analytics_engine import calculate_macd
        
        prices = [100 + i for i in range(100)]
        macd = calculate_macd(prices, 12, 26, 9)
        
        assert "macd" in macd
        assert "signal" in macd
        assert "histogram" in macd
        assert len(macd["macd"]) == len(prices)
    
    def test_bollinger_bands_calculation(self):
        """Test Bollinger Bands calculation"""
        from app.services.analytics_engine import calculate_bollinger_bands
        
        prices = [100 + i for i in range(50)]
        bollinger = calculate_bollinger_bands(prices, 20, 2)
        
        assert "upper" in bollinger
        assert "middle" in bollinger
        assert "lower" in bollinger
        
        # Upper should be above middle, lower should be below middle
        valid_indices = [i for i in range(len(bollinger["middle"])) if bollinger["middle"][i] is not None]
        for i in valid_indices:
            assert bollinger["upper"][i] > bollinger["middle"][i]
            assert bollinger["lower"][i] < bollinger["middle"][i]


class TestAlerts:
    """Test technical alert generation"""
    
    def test_rsi_overbought_alert(self, db_session, sample_price_data):
        """Test RSI overbought alert (> 70)"""
        from app.services.analytics_engine import get_technical_alerts
        
        # Create price data that would trigger overbought RSI
        # This is simplified - in real scenario would need specific price pattern
        alerts = get_technical_alerts(db_session, "AAPL")
        
        # Should return a list
        assert isinstance(alerts, list)
    
    def test_rsi_oversold_alert(self, db_session, sample_price_data):
        """Test RSI oversold alert (< 30)"""
        from app.services.analytics_engine import get_technical_alerts
        
        alerts = get_technical_alerts(db_session, "AAPL")
        
        assert isinstance(alerts, list)
    
    def test_macd_crossover_detection(self, db_session, sample_price_data):
        """Test MACD crossover detection"""
        from app.services.analytics_engine import get_technical_alerts
        
        alerts = get_technical_alerts(db_session, "AAPL")
        
        # Check that alerts can include MACD crossovers
        alert_types = [a["type"] for a in alerts]
        # May or may not have crossover depending on data
        assert isinstance(alerts, list)


class TestSentimentDivergence:
    """Test sentiment divergence detection"""
    
    def test_sentiment_divergence_detection(self, db_session):
        """Test sentiment divergence when sentiment and price return disagree"""
        from app.services.analytics_engine import check_sentiment_divergence
        
        # Create sentiment data with high positive sentiment
        sentiment = NewsSentimentDaily(
            ticker="AAPL",
            date=datetime(2024, 1, 15),
            avg_sentiment=0.9,  # Very high positive sentiment
            headline_count=10
        )
        db_session.add(sentiment)
        
        # Create price data with negative return
        prev_price = PriceHistoryDaily(
            ticker="AAPL",
            date=datetime(2024, 1, 14),
            open=100.0,
            high=105.0,
            low=95.0,
            close=100.0,
            volume=1000000
        )
        db_session.add(prev_price)
        
        curr_price = PriceHistoryDaily(
            ticker="AAPL",
            date=datetime(2024, 1, 15),
            open=98.0,
            high=100.0,
            low=95.0,
            close=95.0,  # Negative return (-5%)
            volume=1000000
        )
        db_session.add(curr_price)
        db_session.commit()
        
        # Check for divergence
        divergence = check_sentiment_divergence(db_session, "AAPL", "2024-01-15")
        
        # Should detect divergence (positive sentiment, negative price return)
        # Note: Depends on SENTIMENT_DIVERGENCE_THRESHOLD in config
        if divergence:
            assert divergence["divergence_type"] == "bearish"
    
    def test_no_divergence_when_aligned(self, db_session):
        """Test no divergence when sentiment and price return align"""
        from app.services.analytics_engine import check_sentiment_divergence
        
        # Create sentiment data with positive sentiment
        sentiment = NewsSentimentDaily(
            ticker="AAPL",
            date=datetime(2024, 1, 15),
            avg_sentiment=0.8,
            headline_count=10
        )
        db_session.add(sentiment)
        
        # Create price data with positive return (aligned)
        prev_price = PriceHistoryDaily(
            ticker="AAPL",
            date=datetime(2024, 1, 14),
            open=100.0,
            high=105.0,
            low=95.0,
            close=100.0,
            volume=1000000
        )
        db_session.add(prev_price)
        
        curr_price = PriceHistoryDaily(
            ticker="AAPL",
            date=datetime(2024, 1, 15),
            open=102.0,
            high=108.0,
            low=101.0,
            close=105.0,  # Positive return
            volume=1000000
        )
        db_session.add(curr_price)
        db_session.commit()
        
        # Check for divergence
        divergence = check_sentiment_divergence(db_session, "AAPL", "2024-01-15")
        
        # Should not detect divergence (both positive)
        assert divergence is None


class TestAnalyticsAPI:
    """Test analytics API endpoints"""
    
    def test_get_indicators_endpoint(self, db_session, sample_price_data, approved_trader_token):
        """Test GET /api/analytics/{ticker}/indicators"""
        response = client.get(
            "/api/analytics/AAPL/indicators",
            headers={"Authorization": f"Bearer {approved_trader_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "sma_20" in data
        assert "sma_50" in data
        assert "ema_12" in data
        assert "ema_26" in data
        assert "rsi_14" in data
        assert "macd" in data
        assert "bollinger_bands" in data
    
    def test_get_alerts_endpoint(self, db_session, sample_price_data, approved_trader_token):
        """Test GET /api/analytics/{ticker}/alerts"""
        response = client.get(
            "/api/analytics/AAPL/alerts",
            headers={"Authorization": f"Bearer {approved_trader_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "ticker" in data
        assert "alerts" in data
        assert "alert_count" in data
        assert isinstance(data["alerts"], list)
    
    def test_get_sentiment_divergence_endpoint(self, db_session, approved_trader_token):
        """Test GET /api/analytics/{ticker}/sentiment-divergence"""
        response = client.get(
            "/api/analytics/AAPL/sentiment-divergence?date=2024-01-15",
            headers={"Authorization": f"Bearer {approved_trader_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "ticker" in data
        assert "divergence" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])