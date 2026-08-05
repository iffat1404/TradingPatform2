from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # Trading Constants
    STARTING_CAPITAL: float = 1_000_000.0
    SPREAD_BPS: int = 8
    PRICE_COLLAR_PCT: float = 10.0
    MAX_NOTIONAL_PER_ORDER: float = 250_000.0
    MAX_CONCENTRATION_PCT: float = 25.0
    SHORT_COLLATERAL_MULTIPLIER: float = 1.5
    ORDER_RATE_LIMIT_PER_MINUTE: int = 10
    WASH_TRADE_WINDOW_SECONDS: int = 60
    COMMISSION_FLAT_FEE: float = 1.0
    
    # Market Hours (derived from live feed timestamps)
    MARKET_OPEN: str = "09:30"
    MARKET_CLOSE: str = "16:00"
    
    # Feed Simulator
    FEED_REPLAY_SPEED_MULTIPLIER: int = 1
    FEED_SIMULATOR_START_TIMESTAMP: str = "2026-06-30T09:30:00Z"
    
    # Technical Indicators
    SMA_PERIODS: List[int] = [20, 50]
    EMA_PERIODS: List[int] = [12, 26]
    RSI_PERIOD: int = 14
    MACD_PARAMS: tuple = (12, 26, 9)
    BOLLINGER_PARAMS: tuple = (20, 2)
    RSI_OVERBOUGHT: float = 70.0
    RSI_OVERSOLD: float = 30.0
    SENTIMENT_DIVERGENCE_THRESHOLD: float = 0.35
    
    # KYC Constants
    KYC_MIN_AGE_YEARS: int = 18
    KYC_NAME_MATCH_THRESHOLD: float = 0.85
    KYC_MAX_UPLOAD_SIZE_MB: int = 10
    KYC_ALLOWED_MIME_TYPES: List[str] = ["image/jpeg", "image/png", "application/pdf"]
    
    # Admin Bootstrap
    ADMIN_BOOTSTRAP_USERNAME: str = "admin"
    ADMIN_BOOTSTRAP_PASSWORD: str = "admin123"
    
    # Timezone (fixed per principle 12)
    APP_TIMEZONE: str = "UTC"
    
    # JWT Settings
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Database
    DATABASE_URL: str = "sqlite:///./nomura_stp.db"
    
    class Config:
        env_file = ".env"


settings = Settings()