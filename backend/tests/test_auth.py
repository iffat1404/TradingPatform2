import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.core.db import get_db, Base
from app.core.security import get_password_hash, create_access_token, decode_access_token
from app.models.orm import Account, Role, KYCStatus
from app.models.schemas import AccountCreate, LoginRequest

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


class TestPasswordHashing:
    """Test password hashing and verification"""
    
    def test_password_hashing(self):
        """Test that passwords are hashed correctly"""
        plain_password = "test_password_123"
        hashed = get_password_hash(plain_password)
        
        # Hash should not equal plain password
        assert hashed != plain_password
        
        # Hash should be consistent for same password
        hashed2 = get_password_hash(plain_password)
        # Note: bcrypt includes salt, so hashes will differ
        assert hashed != hashed2
    
    def test_password_verification(self):
        """Test that password verification works correctly"""
        from app.core.security import verify_password
        
        plain_password = "test_password_123"
        hashed = get_password_hash(plain_password)
        
        # Correct password should verify
        assert verify_password(plain_password, hashed) is True
        
        # Wrong password should not verify
        assert verify_password("wrong_password", hashed) is False


class TestJWTToken:
    """Test JWT token creation and verification"""
    
    def test_token_creation(self):
        """Test that JWT tokens are created correctly"""
        data = {
            "sub": "test_account_id",
            "username": "testuser",
            "role": "trader"
        }
        
        token = create_access_token(data)
        
        # Token should be a non-empty string
        assert token is not None
        assert len(token) > 0
        
        # Token should have 3 parts (header.payload.signature)
        parts = token.split(".")
        assert len(parts) == 3
    
    def test_token_decoding(self):
        """Test that JWT tokens are decoded correctly"""
        data = {
            "sub": "test_account_id",
            "username": "testuser",
            "role": "trader"
        }
        
        token = create_access_token(data)
        decoded = decode_access_token(token)
        
        # Decoded token should contain original data
        assert decoded is not None
        assert decoded["sub"] == "test_account_id"
        assert decoded["username"] == "testuser"
        assert decoded["role"] == "trader"
        assert "exp" in decoded  # Expiration time
    
    def test_invalid_token_decoding(self):
        """Test that invalid tokens return None"""
        invalid_token = "invalid.token.here"
        decoded = decode_access_token(invalid_token)
        
        assert decoded is None


class TestUserRegistration:
    """Test user registration endpoint"""
    
    def test_register_new_user(self, db_session):
        """Test registering a new user"""
        user_data = {
            "username": "newtrader",
            "password": "securepassword123",
            "starting_capital": 1000000.0
        }
        
        response = client.post("/api/auth/register", json=user_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["username"] == "newtrader"
        assert data["role"] == "trader"
        assert data["kyc_status"] == "NOT_STARTED"
        assert data["starting_capital"] == 1000000.0
        assert data["cash_balance"] == 1000000.0
        assert "id" in data
        assert "password_hash" not in data  # Password should never be returned
    
    def test_register_duplicate_username(self, db_session):
        """Test that duplicate usernames are rejected"""
        user_data = {
            "username": "duplicate",
            "password": "password123",
            "starting_capital": 1000000.0
        }
        
        # Register first user
        response1 = client.post("/api/auth/register", json=user_data)
        assert response1.status_code == 201
        
        # Try to register with same username
        response2 = client.post("/api/auth/register", json=user_data)
        assert response2.status_code == 400
        assert "already exists" in response2.json()["detail"]
    
    def test_register_default_capital(self, db_session):
        """Test that default capital is used when not specified"""
        user_data = {
            "username": "defaultcapital",
            "password": "password123"
        }
        
        response = client.post("/api/auth/register", json=user_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["starting_capital"] == 1_000_000.0  # Default from config
        assert data["cash_balance"] == 1_000_000.0
    
    def test_register_creates_trader_role(self, db_session):
        """Test that public registration always creates trader role"""
        user_data = {
            "username": "traderonly",
            "password": "password123"
        }
        
        response = client.post("/api/auth/register", json=user_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["role"] == "trader"
        # Admin accounts should not be creatable via public registration


class TestUserLogin:
    """Test user login endpoint"""
    
    def test_login_valid_credentials(self, db_session):
        """Test login with valid credentials"""
        # First register a user
        user_data = {
            "username": "loginuser",
            "password": "password123"
        }
        client.post("/api/auth/register", json=user_data)
        
        # Now login
        login_data = {
            "username": "loginuser",
            "password": "password123"
        }
        response = client.post("/api/auth/login", json=login_data)
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["role"] == "trader"
    
    def test_login_invalid_username(self, db_session):
        """Test login with invalid username"""
        login_data = {
            "username": "nonexistent",
            "password": "password123"
        }
        response = client.post("/api/auth/login", json=login_data)
        
        assert response.status_code == 401
        assert "Invalid username or password" in response.json()["detail"]
    
    def test_login_invalid_password(self, db_session):
        """Test login with invalid password"""
        # Register a user
        user_data = {
            "username": "wrongpass",
            "password": "correctpassword"
        }
        client.post("/api/auth/register", json=user_data)
        
        # Try login with wrong password
        login_data = {
            "username": "wrongpass",
            "password": "wrongpassword"
        }
        response = client.post("/api/auth/login", json=login_data)
        
        assert response.status_code == 401
        assert "Invalid username or password" in response.json()["detail"]


class TestGetCurrentUser:
    """Test getting current user information"""
    
    def test_get_me_with_valid_token(self, db_session):
        """Test getting current user with valid token"""
        # Register and login
        user_data = {
            "username": "meuser",
            "password": "password123"
        }
        client.post("/api/auth/register", json=user_data)
        
        login_response = client.post("/api/auth/login", json={
            "username": "meuser",
            "password": "password123"
        })
        token = login_response.json()["access_token"]
        
        # Get current user
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "meuser"
        assert data["role"] == "trader"
    
    def test_get_me_without_token(self, db_session):
        """Test getting current user without token"""
        response = client.get("/api/auth/me")
        
        # HTTPBearer returns 403 when no authorization header is present
        assert response.status_code == 403
    
    def test_get_me_with_invalid_token(self, db_session):
        """Test getting current user with invalid token"""
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer invalid_token"}
        )
        
        assert response.status_code == 401


class TestAdminAuthorization:
    """Test admin role authorization"""
    
    def test_admin_route_requires_admin_role(self, db_session):
        """Test that admin routes require admin role"""
        # Register a regular trader
        user_data = {
            "username": "regulartrader",
            "password": "password123"
        }
        client.post("/api/auth/register", json=user_data)
        
        # Login as trader
        login_response = client.post("/api/auth/login", json={
            "username": "regulartrader",
            "password": "password123"
        })
        trader_token = login_response.json()["access_token"]
        
        # Try to access admin route with trader token
        response = client.get(
            "/api/admin/accounts",
            headers={"Authorization": f"Bearer {trader_token}"}
        )
        
        # Should return 403 Forbidden
        assert response.status_code == 403
        assert "Access denied" in response.json()["detail"]
    
    def test_trader_cannot_access_admin_endpoints(self, db_session):
        """Test that traders cannot access any admin endpoints"""
        # Register and login as trader
        user_data = {
            "username": "traderuser",
            "password": "password123"
        }
        client.post("/api/auth/register", json=user_data)
        
        login_response = client.post("/api/auth/login", json={
            "username": "traderuser",
            "password": "password123"
        })
        trader_token = login_response.json()["access_token"]
        
        # Test various admin endpoints
        admin_endpoints = [
            "/api/admin/kyc",
            "/api/admin/accounts",
            "/api/admin/audit-logs",
            "/api/admin/trade-logs",
            "/api/admin/flags",
            "/api/admin/feed/status"
        ]
        
        for endpoint in admin_endpoints:
            response = client.get(
                endpoint,
                headers={"Authorization": f"Bearer {trader_token}"}
            )
            # All should return 403
            assert response.status_code == 403, f"Endpoint {endpoint} should return 403 for trader"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])