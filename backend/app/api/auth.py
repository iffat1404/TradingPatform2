from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import timedelta
from app.core.db import get_db
from app.core.security import (
    get_password_hash, 
    verify_password, 
    create_access_token,
    get_current_user
)
from app.core.config import settings
from app.models.orm import Account, Role, KYCStatus
from app.models.schemas import AccountCreate, AccountResponse, LoginRequest, TokenResponse
import uuid

router = APIRouter()


@router.post("/register", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
def register(user_data: AccountCreate, db: Session = Depends(get_db)):
    """
    Register a new trader account.
    
    Creates a trader account with KYC status NOT_STARTED.
    Public endpoint - no auth required.
    Note: Admin accounts cannot be created via public registration.
    """
    # Check if username already exists
    existing_user = db.query(Account).filter(Account.username == user_data.username).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists"
        )
    
    # Create new account
    account = Account(
        id=str(uuid.uuid4()),
        username=user_data.username,
        password_hash=get_password_hash(user_data.password),
        role=Role.TRADER,  # Public registration always creates trader accounts
        kyc_status=KYCStatus.NOT_STARTED,
        starting_capital=user_data.starting_capital or settings.STARTING_CAPITAL,
        cash_balance=user_data.starting_capital or settings.STARTING_CAPITAL
    )
    
    db.add(account)
    db.commit()
    db.refresh(account)
    
    return account


@router.post("/login", response_model=TokenResponse)
def login(login_data: LoginRequest, db: Session = Depends(get_db)):
    """
    Authenticate a user and return a JWT access token.
    
    Accepts username/password and returns JWT with role claim.
    Works for both trader and admin accounts.
    """
    # Find user by username
    user = db.query(Account).filter(Account.username == login_data.username).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )
    
    # Verify password
    if not verify_password(login_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )
    
    # Create access token
    access_token = create_access_token(
        data={
            "sub": user.id,
            "username": user.username,
            "role": user.role.value
        }
    )
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        role=user.role
    )


@router.get("/me", response_model=AccountResponse)
def get_me(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Get current user information.
    
    Returns account details for the authenticated user.
    Requires valid JWT token.
    """
    # Fetch full user from database
    user = db.query(Account).filter(Account.id == current_user["account_id"]).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return user