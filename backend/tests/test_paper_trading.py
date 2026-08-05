import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.core.db import get_db, Base
from app.core.security import get_password_hash, create_access_token
from app.models.orm import Account, Role, KYCStatus, PriceHistoryDaily, BacktestStrategy, BacktestRun
from datetime import datetime, timedelta
import pandas as pd
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
        id="paper_test_id",
        username="paper_test",
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
    """Create sample daily price data for backtesting from CSV"""
    import pandas as pd
    csv_path = "C:/Users/New/Desktop/Soham/backend/app/data/simulation_historical_data/simulated_AAPL_2026_historical.csv"
    df = pd.read_csv(csv_path)
    
    # Load into database
    for _, row in df.iterrows():
        price = PriceHistoryDaily(
            ticker="AAPL",
            date=datetime.strptime(row["timestamp"], "%Y-%m-%d"),
            open=row["open"],
            high=row["high"],
            low=row["low"],
            close=row["close"],
            volume=int(row["volume"])
        )
        db_session.add(price)
    db_session.commit()


class TestStrategyManagement:
    """Test strategy creation and management"""
    
    def test_create_strategy(self, db_session, approved_trader_token):
        """Test POST /api/paper-trading/strategies"""
        strategy_data = {
            "name": "RSI Strategy",
            "ticker": "AAPL",
            "entry_rule": {"type": "rsi_oversold", "threshold": 30},
            "exit_rule": {"type": "rsi_overbought", "threshold": 70},
            "position_size": 100
        }
        
        response = client.post(
            "/api/paper-trading/strategies",
            json=strategy_data,
            headers={"Authorization": f"Bearer {approved_trader_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["name"] == "RSI Strategy"
        assert data["ticker"] == "AAPL"
        assert data["position_size"] == 100
    
    def test_list_strategies(self, db_session, approved_trader_token):
        """Test GET /api/paper-trading/strategies"""
        # Create a strategy first
        strategy = BacktestStrategy(
            id="test_strategy_id",
            account_id="paper_test_id",
            name="Test Strategy",
            ticker="AAPL",
            entry_rule='{"type": "rsi_oversold", "threshold": 30}',
            exit_rule='{"type": "rsi_overbought", "threshold": 70}',
            position_size=100
        )
        db_session.add(strategy)
        db_session.commit()
        
        response = client.get(
            "/api/paper-trading/strategies",
            headers={"Authorization": f"Bearer {approved_trader_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert data[0]["name"] == "Test Strategy"


class TestBacktestExecution:
    """Test backtest execution"""
    
    def test_run_backtest(self, db_session, approved_trader_token, sample_price_data):
        """Test POST /api/paper-trading/backtest/{strategy_id}/run"""
        # Create a strategy
        strategy = BacktestStrategy(
            id="backtest_strategy_id",
            account_id="paper_test_id",
            name="Backtest Strategy",
            ticker="AAPL",
            entry_rule='{"type": "rsi_oversold", "threshold": 30}',
            exit_rule='{"type": "rsi_overbought", "threshold": 70}',
            position_size=100
        )
        db_session.add(strategy)
        db_session.commit()
        
        # Run backtest
        run_params = {
            "start_date": "2026-01-02",
            "end_date": "2026-01-31"
        }
        
        response = client.post(
            "/api/paper-trading/backtest/backtest_strategy_id/run",
            json=run_params,
            headers={"Authorization": f"Bearer {approved_trader_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "run_id" in data
        assert data["status"] in ["running", "completed", "failed"]
        assert "total_return" in data
        assert "benchmark_return" in data
    
    def test_get_backtest_results(self, db_session, approved_trader_token):
        """Test GET /api/paper-trading/backtest/{run_id}/results"""
        # Create a completed backtest run
        run = BacktestRun(
            id="test_run_id",
            strategy_id="test_strategy_id",
            account_id="paper_test_id",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
            starting_capital=1_000_000.0,
            ending_capital=1_050_000.0,
            total_return=0.05,
            benchmark_return=0.03,
            max_drawdown=0.02,
            win_rate=0.6,
            total_trades=10,
            winning_trades=6,
            status="completed"
        )
        db_session.add(run)
        db_session.commit()
        
        response = client.get(
            "/api/paper-trading/backtest/test_run_id/results",
            headers={"Authorization": f"Bearer {approved_trader_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["run_id"] == "test_run_id"
        assert data["total_return"] == 0.05
        assert data["benchmark_return"] == 0.03
        assert data["win_rate"] == 0.6
    
    def test_backtest_isolation(self, db_session, approved_trader_token):
        """Test that backtest doesn't affect live portfolio (isolation)"""
        # Load historical data from CSV
        import pandas as pd
        csv_path = "C:/Users/New/Desktop/Soham/backend/app/data/simulation_historical_data/simulated_AAPL_2026_historical.csv"
        df = pd.read_csv(csv_path)
        
        # Load into database
        from datetime import datetime
        for _, row in df.iterrows():
            price = PriceHistoryDaily(
                ticker="AAPL",
                date=datetime.strptime(row["timestamp"], "%Y-%m-%d"),
                open=row["open"],
                high=row["high"],
                low=row["low"],
                close=row["close"],
                volume=int(row["volume"])
            )
            db_session.add(price)
        db_session.commit()
        
        # Get initial portfolio state
        initial_response = client.get(
            "/api/portfolio",
            headers={"Authorization": f"Bearer {approved_trader_token}"}
        )
        initial_portfolio = initial_response.json()
        initial_cash = initial_portfolio["cash_balance"]
        
        # Create and run a backtest
        strategy = BacktestStrategy(
            id="isolation_strategy_id",
            account_id="paper_test_id",
            name="Isolation Test",
            ticker="AAPL",
            entry_rule='{"type": "rsi_oversold", "threshold": 30}',
            exit_rule='{"type": "rsi_overbought", "threshold": 70}',
            position_size=100
        )
        db_session.add(strategy)
        db_session.commit()
        
        run_params = {
            "start_date": "2026-01-02",
            "end_date": "2026-01-31"
        }
        
        client.post(
            "/api/paper-trading/backtest/isolation_strategy_id/run",
            json=run_params,
            headers={"Authorization": f"Bearer {approved_trader_token}"}
        )
        
        # Check portfolio state after backtest
        final_response = client.get(
            "/api/portfolio",
            headers={"Authorization": f"Bearer {approved_trader_token}"}
        )
        final_portfolio = final_response.json()
        final_cash = final_portfolio["cash_balance"]
        
        # Cash balance should be unchanged (backtest isolation)
        assert abs(final_cash - initial_cash) < 0.01


class TestBenchmarkComparison:
    """Test benchmark calculation"""
    
    def test_benchmark_return_calculation(self, db_session):
        """Test buy-and-hold benchmark calculation"""
        from app.services.backtest_engine import calculate_benchmark_return
        
        # Create price data
        base_date = datetime(2024, 1, 1)
        for i in range(30):
            price = PriceHistoryDaily(
                ticker="AAPL",
                date=base_date + timedelta(days=i),
                open=100.0 + i,
                high=105.0 + i,
                low=95.0 + i,
                close=102.0 + i,
                volume=1000000
            )
            db_session.add(price)
        db_session.commit()
        
        # Calculate benchmark
        benchmark = calculate_benchmark_return(
            "AAPL",
            datetime(2024, 1, 1),
            datetime(2024, 1, 30),
            db_session
        )
        
        # Should be positive (price went up)
        assert benchmark > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])