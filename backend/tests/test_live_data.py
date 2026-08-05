from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.db import Base, get_db
from app.main import app
from app.models.orm import PriceHistoryMinute

TEST_DATABASE_URL = "sqlite:///./test_live_data.db"
engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
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


def setup_function():
    Base.metadata.create_all(bind=engine)


def teardown_function():
    Base.metadata.drop_all(bind=engine)


def test_get_latest_price_returns_latest_minute_tick():
    db = TestingSessionLocal()
    db.add(
        PriceHistoryMinute(
            ticker="AAPL",
            timestamp=datetime(2026, 8, 1, 9, 30),
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.5,
            volume=1200,
        )
    )
    db.commit()
    db.close()

    response = client.get("/api/prices/AAPL/latest")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ticker"] == "AAPL"
    assert payload["close"] == 100.5
    assert payload["timestamp"] == "2026-08-01 09:30:00"
