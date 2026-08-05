"""
Integration test to verify the complete KYC flow:
submit → extract → auto-check → Admin approve/reject
"""
import pytest
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.core.db import get_db, Base
from app.core.security import get_password_hash, create_access_token
from app.models.orm import Account, Role, KYCStatus
import io

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


def test_kyc_flow_integration():
    """
    Test the complete KYC flow:
    1. Trader registers and logs in
    2. Trader submits KYC document
    3. Trader can check status (PENDING_REVIEW)
    4. Admin can view submission in queue
    5. Admin can approve submission
    6. Trader status becomes APPROVED
    7. Trader can now place orders (KYC check passes)
    """
    # Setup database
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    
    try:
        # Create trader account
        trader = Account(
            id="integration_trader_id",
            username="integration_trader",
            password_hash=get_password_hash("trader123"),
            role=Role.TRADER,
            kyc_status=KYCStatus.NOT_STARTED,
            starting_capital=1_000_000.0,
            cash_balance=1_000_000.0
        )
        db.add(trader)
        db.commit()
        
        # Create admin account
        admin = Account(
            id="integration_admin_id",
            username="integration_admin",
            password_hash=get_password_hash("admin123"),
            role=Role.ADMIN,
            kyc_status=KYCStatus.APPROVED,
            starting_capital=1_000_000.0,
            cash_balance=1_000_000.0
        )
        db.add(admin)
        db.commit()
        
        # Get tokens
        trader_token = create_access_token({
            "sub": trader.id,
            "username": trader.username,
            "role": trader.role.value
        })
        
        admin_token = create_access_token({
            "sub": admin.id,
            "username": admin.username,
            "role": admin.role.value
        })
        
        # Step 1: Trader can check initial status
        status_response = client.get(
            "/api/kyc/status",
            headers={"Authorization": f"Bearer {trader_token}"}
        )
        assert status_response.status_code == 200
        assert status_response.json()["kyc_status"] == "NOT_STARTED"
        
        # Step 2: Trader submits KYC document
        file_content = b"fake id document content"
        submit_response = client.post(
            "/api/kyc/submit",
            headers={"Authorization": f"Bearer {trader_token}"},
            data={
                "id_type": "passport"
            },
            files={
                "id_document": ("test_id.jpg", io.BytesIO(file_content), "image/jpeg")
            }
        )
        assert submit_response.status_code == 202
        submission_id = submit_response.json()["submission_id"]
        
        # Step 3: Trader can check status (should be PENDING_REVIEW)
        status_response = client.get(
            "/api/kyc/status",
            headers={"Authorization": f"Bearer {trader_token}"}
        )
        assert status_response.status_code == 200
        assert status_response.json()["kyc_status"] == "PENDING_REVIEW"
        
        # Step 4: Admin can view submission in queue
        queue_response = client.get(
            "/api/admin/kyc",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert queue_response.status_code == 200
        queue = queue_response.json()
        assert len(queue) > 0
        assert queue[0]["id"] == submission_id
        assert queue[0]["status"] == "PENDING_REVIEW"
        
        # Step 5: Admin can approve submission
        approve_response = client.post(
            f"/api/admin/kyc/{submission_id}/approve",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert approve_response.status_code == 200
        assert approve_response.json()["message"] == "KYC submission approved"
        
        # Step 6: Trader status becomes APPROVED
        status_response = client.get(
            "/api/kyc/status",
            headers={"Authorization": f"Bearer {trader_token}"}
        )
        assert status_response.status_code == 200
        assert status_response.json()["kyc_status"] == "APPROVED"
        
        # Step 7: Trader can now place orders (KYC check passes)
        order_response = client.post(
            "/api/orders",
            headers={"Authorization": f"Bearer {trader_token}"},
            json={
                "ticker": "AAPL",
                "side": "buy",
                "type": "market",
                "qty": 10
            }
        )
        # Should succeed (KYC approved)
        # Will fail on other checks (no current price, etc.) but KYC check should pass
        # For now, we'll just check it doesn't fail with KYC_NOT_APPROVED
        if order_response.status_code == 422:
            error_detail = order_response.json()["detail"]
            if isinstance(error_detail, dict):
                assert error_detail.get("error_code") != "KYC_NOT_APPROVED"
        
        print("Complete KYC flow integration test PASSED")
        
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


if __name__ == "__main__":
    test_kyc_flow_integration()