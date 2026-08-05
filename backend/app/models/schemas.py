from pydantic import BaseModel, Field, ConfigDict, model_validator
from typing import Optional, List
from datetime import datetime
from app.models.orm import KYCStatus, OrderStatus, OrderSide, OrderType, Role


# Account Schemas
class AccountBase(BaseModel):
    username: str
    starting_capital: Optional[float] = 1_000_000.0


class AccountCreate(AccountBase):
    password: str


class AccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    username: str
    role: Role
    kyc_status: KYCStatus
    starting_capital: float
    cash_balance: float
    created_at: datetime


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: Role


# Order Schemas
class OrderCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    
    ticker: str = Field(..., description="Stock ticker symbol")
    side: OrderSide = Field(..., description="Buy or sell")
    type: OrderType = Field(..., description="Market or limit order")
    qty: int = Field(..., gt=0, description="Quantity of shares", alias="quantity")
    limit_price: Optional[float] = Field(None, description="Limit price (required for limit orders)")
    time_in_force: Optional[str] = Field("DAY", description="Time in force")


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    
    id: str
    account_id: str
    ticker: str
    side: OrderSide
    type: OrderType
    qty: int = Field(alias="quantity")
    limit_price: Optional[float]
    status: OrderStatus
    is_backtest: bool
    created_at: datetime


class OrderEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    order_id: str
    from_state: Optional[OrderStatus]
    to_state: OrderStatus
    reason: Optional[str]
    is_backtest: bool
    timestamp: datetime


class FillResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    order_id: str
    fill_price: float
    fill_qty: int
    fees: float
    is_backtest: bool
    timestamp: datetime


# KYC Schemas
class KYCSubmissionCreate(BaseModel):
    id_type: str = Field(..., description="passport, drivers_license, or national_id")


class KYCSubmissionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    account_id: str
    id_type: str
    document_path: str
    extracted_full_name: Optional[str]
    extracted_dob: Optional[datetime]
    extracted_id_number: Optional[str]
    extracted_expiry_date: Optional[datetime]
    extracted_issuing_country: Optional[str]
    extraction_confidence: Optional[str]
    auto_check_passed: Optional[bool]
    auto_check_notes: Optional[str]
    status: KYCStatus
    reviewed_by_admin_id: Optional[str]
    review_notes: Optional[str]
    submitted_at: datetime
    reviewed_at: Optional[datetime]


class KYCStatusResponse(BaseModel):
    kyc_status: KYCStatus
    review_notes: Optional[str] = None


class KYCReviewRequest(BaseModel):
    reason: Optional[str] = Field(None, description="Required for rejection")


# Price History Schemas
class PriceHistoryDailyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    ticker: str
    date: datetime
    open: float
    high: float
    low: float
    close: float
    adj_close: Optional[float]
    volume: int


class PriceHistoryMinuteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    ticker: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int


# News Sentiment Schema
class NewsSentimentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    ticker: str
    date: datetime
    avg_sentiment: float
    headline_count: int


# Portfolio Schemas
class PositionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    ticker: str
    signed_qty: int
    avg_cost: float
    realized_pnl: float
    unrealized_pnl: Optional[float] = None
    market_value: Optional[float] = None


class PortfolioResponse(BaseModel):
    account_id: str
    cash_balance: float
    net_worth: float
    positions: List[PositionResponse]
    collateral_reserved: float = 0.0


class PortfolioPnLResponse(BaseModel):
    account_id: str
    realized_pnl: float
    unrealized_pnl: float
    total_pnl: float


class ExposureResponse(BaseModel):
    gross_exposure: float
    net_exposure: float
    by_ticker: dict
    by_sector: dict


# Trading Journal Schemas
# Emotional state is a closed vocabulary so entries stay aggregatable for pattern
# detection — free text would make "which mood precedes losses?" unanswerable.
ALLOWED_EMOTIONAL_TAGS = [
    "confident",
    "disciplined",
    "neutral",
    "excited",
    "fomo",
    "greedy",
    "anxious",
    "fearful",
    "frustrated",
    "revenge",
]

ALLOWED_ENTRY_TYPES = ["trade_note", "reflection"]


class JournalEntryCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    order_id: Optional[str] = Field(None, description="Link this note to one of your orders")
    ticker: Optional[str] = Field(None, description="Ticker for a standalone reflection")
    entry_type: str = Field("trade_note", description="trade_note or reflection")
    rationale: str = Field(..., min_length=1, description="Why you took (or skipped) this trade")
    emotional_tags: Optional[List[str]] = Field(None, description="How you felt, from the allowed vocabulary")


class JournalEntryUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    rationale: Optional[str] = Field(None, min_length=1)
    emotional_tags: Optional[List[str]] = None


# Error Response Schema
class ErrorResponse(BaseModel):
    detail: dict = Field(..., description="Error details with error_code and message")


class ErrorCodeResponse(BaseModel):
    error_code: str
    message: str