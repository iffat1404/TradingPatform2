import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.core.db import get_db, Base
from app.core.security import get_password_hash, create_access_token
from app.models.orm import Account, Role, KYCStatus, KYCSubmission
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
def admin_token(db_session):
    """Create an admin user and return their token"""
    admin = Account(
        id="admin_test_id",
        username="admin_test",
        password_hash=get_password_hash("admin123"),
        role=Role.ADMIN,
        kyc_status=KYCStatus.APPROVED,
        starting_capital=1_000_000.0,
        cash_balance=1_000_000.0
    )
    db_session.add(admin)
    db_session.commit()
    
    token = create_access_token({
        "sub": admin.id,
        "username": admin.username,
        "role": admin.role.value
    })
    
    return token


@pytest.fixture
def trader_token(db_session):
    """Create a trader user and return their token"""
    trader = Account(
        id="trader_test_id",
        username="trader_test",
        password_hash=get_password_hash("trader123"),
        role=Role.TRADER,
        kyc_status=KYCStatus.NOT_STARTED,
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


class TestKYCSubmission:
    """Test KYC document submission"""
    
    def test_submit_kyc_with_valid_file(self, db_session, trader_token):
        """Test submitting a valid KYC document"""
        # Create a test file
        file_content = b"fake image content"
        
        response = client.post(
            "/api/kyc/submit",
            headers={"Authorization": f"Bearer {trader_token}"},
            data={
                "id_type": "passport"
            },
            files={
                "id_document": ("test_id.jpg", io.BytesIO(file_content), "image/jpeg")
            }
        )
        
        assert response.status_code == 202
        data = response.json()
        assert "submission_id" in data
        assert data["status"] == "PROCESSING"
    
    def test_submit_kyc_invalid_id_type(self, db_session, trader_token):
        """Test submitting with invalid ID type"""
        file_content = b"fake image content"
        
        response = client.post(
            "/api/kyc/submit",
            headers={"Authorization": f"Bearer {trader_token}"},
            data={
                "id_type": "invalid_type"
            },
            files={
                "id_document": ("test_id.jpg", io.BytesIO(file_content), "image/jpeg")
            }
        )
        
        assert response.status_code == 400
        assert "Invalid ID type" in response.json()["detail"]
    
    def test_submit_kyc_unauthorized(self, db_session):
        """Test submitting without authentication"""
        file_content = b"fake image content"
        
        response = client.post(
            "/api/kyc/submit",
            data={
                "id_type": "passport"
            },
            files={
                "id_document": ("test_id.jpg", io.BytesIO(file_content), "image/jpeg")
            }
        )
        
        assert response.status_code == 403
    
    def test_submit_kyc_updates_account_status(self, db_session, trader_token):
        """Test that submission updates account KYC status to PENDING_REVIEW"""
        file_content = b"fake image content"
        
        response = client.post(
            "/api/kyc/submit",
            headers={"Authorization": f"Bearer {trader_token}"},
            data={
                "id_type": "passport"
            },
            files={
                "id_document": ("test_id.jpg", io.BytesIO(file_content), "image/jpeg")
            }
        )
        
        assert response.status_code == 202
        
        # Check account status was updated
        db = TestingSessionLocal()
        account = db.query(Account).filter(Account.username == "trader_test").first()
        assert account.kyc_status == KYCStatus.PENDING_REVIEW
        db.close()


class TestKYCStatus:
    """Test KYC status endpoint"""
    
    def test_get_kyc_status_not_started(self, db_session, trader_token):
        """Test getting KYC status when not started"""
        response = client.get(
            "/api/kyc/status",
            headers={"Authorization": f"Bearer {trader_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["kyc_status"] == "NOT_STARTED"
    
    def test_get_kyc_status_pending_review(self, db_session, trader_token):
        """Test getting KYC status when pending review"""
        # Submit KYC first
        file_content = b"fake image content"
        
        client.post(
            "/api/kyc/submit",
            headers={"Authorization": f"Bearer {trader_token}"},
            data={
                "id_type": "passport"
            },
            files={
                "id_document": ("test_id.jpg", io.BytesIO(file_content), "image/jpeg")
            }
        )
        
        # Check status
        response = client.get(
            "/api/kyc/status",
            headers={"Authorization": f"Bearer {trader_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["kyc_status"] == "PENDING_REVIEW"


class TestAdminKYCQueue:
    """Test admin KYC queue management"""
    
    def test_get_kyc_queue_as_admin(self, db_session, admin_token, trader_token):
        """Test admin can view KYC queue"""
        # Create a submission first
        file_content = b"fake image content"
        
        client.post(
            "/api/kyc/submit",
            headers={"Authorization": f"Bearer {trader_token}"},
            data={
                "id_type": "passport"
            },
            files={
                "id_document": ("test_id.jpg", io.BytesIO(file_content), "image/jpeg")
            }
        )
        
        # Admin views queue
        response = client.get(
            "/api/admin/kyc",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0
        assert data[0]["status"] == "PENDING_REVIEW"
    
    def test_get_kyc_queue_as_trader_forbidden(self, db_session, trader_token):
        """Test trader cannot view KYC queue"""
        response = client.get(
            "/api/admin/kyc",
            headers={"Authorization": f"Bearer {trader_token}"}
        )
        
        assert response.status_code == 403
    
    def test_get_kyc_submission_details(self, db_session, admin_token, trader_token):
        """Test admin can view submission details"""
        # Create a submission
        file_content = b"fake image content"
        
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
        
        submission_id = submit_response.json()["submission_id"]
        
        # Admin views details
        response = client.get(
            f"/api/admin/kyc/{submission_id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == submission_id
        assert data["account_username"] == "trader_test"


class TestAdminKYCReview:
    """Test admin KYC approval and rejection"""
    
    def test_approve_kyc_submission(self, db_session, admin_token, trader_token):
        """Test admin can approve KYC submission"""
        # Create a submission
        file_content = b"fake image content"
        
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
        
        submission_id = submit_response.json()["submission_id"]
        
        # Admin approves
        response = client.post(
            f"/api/admin/kyc/{submission_id}/approve",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        assert response.json()["message"] == "KYC submission approved"
        
        # Verify account status updated
        db = TestingSessionLocal()
        account = db.query(Account).filter(Account.username == "trader_test").first()
        assert account.kyc_status == KYCStatus.APPROVED
        db.close()
    
    def test_reject_kyc_submission(self, db_session, admin_token, trader_token):
        """Test admin can reject KYC submission with reason"""
        # Create a submission
        file_content = b"fake image content"
        
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
        
        submission_id = submit_response.json()["submission_id"]
        
        # Admin rejects with reason
        response = client.post(
            f"/api/admin/kyc/{submission_id}/reject",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"reason": "Document quality too poor"}
        )
        
        assert response.status_code == 200
        assert response.json()["message"] == "KYC submission rejected"
        
        # Verify account status updated
        db = TestingSessionLocal()
        account = db.query(Account).filter(Account.username == "trader_test").first()
        assert account.kyc_status == KYCStatus.REJECTED
        
        # Verify review notes stored
        submission = db.query(KYCSubmission).filter(KYCSubmission.id == submission_id).first()
        assert submission.review_notes == "Document quality too poor"
        db.close()
    
    def test_reject_without_reason_fails(self, db_session, admin_token, trader_token):
        """Test rejection without reason fails"""
        # Create a submission
        file_content = b"fake image content"
        
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
        
        submission_id = submit_response.json()["submission_id"]
        
        # Try to reject without reason
        response = client.post(
            f"/api/admin/kyc/{submission_id}/reject",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={}
        )
        
        assert response.status_code == 400
        assert "Reason is required" in response.json()["detail"]
    
    def test_trader_cannot_approve_kyc(self, db_session, trader_token):
        """Test trader cannot approve KYC"""
        response = client.post(
            "/api/admin/kyc/test_submission_id/approve",
            headers={"Authorization": f"Bearer {trader_token}"}
        )
        
        assert response.status_code == 403


class TestKYCAutoChecks:
    """Test KYC auto-checks functionality"""
    
    def test_auto_checks_expired_id(self):
        """Test auto-check catches expired ID"""
        from app.services.kyc_engine import run_kyc_auto_checks
        from datetime import datetime, timedelta
        
        extraction_result = {
            "extracted_full_name": "Test User",
            "extracted_dob": "1990-01-01",
            "extracted_id_number": "123456",
            "extracted_expiry_date": (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d"),  # Expired yesterday
            "extracted_issuing_country": "US",
            "extraction_confidence": "high"
        }
        
        result = run_kyc_auto_checks(extraction_result, "testuser")
        
        assert result["passed"] is False
        assert "expired" in result["notes"].lower()
    
    def test_auto_checks_under_age(self):
        """Test auto-check catches under-age applicant"""
        from app.services.kyc_engine import run_kyc_auto_checks
        from datetime import datetime, timedelta
        
        extraction_result = {
            "extracted_full_name": "Test User",
            "extracted_dob": (datetime.utcnow() - timedelta(days=365 * 10)).strftime("%Y-%m-%d"),  # 10 years old
            "extracted_id_number": "123456",
            "extracted_expiry_date": (datetime.utcnow() + timedelta(days=365)).strftime("%Y-%m-%d"),
            "extracted_issuing_country": "US",
            "extraction_confidence": "high"
        }
        
        result = run_kyc_auto_checks(extraction_result, "testuser")
        
        assert result["passed"] is False
        assert "age" in result["notes"].lower()
    
    def test_auto_checks_low_confidence(self):
        """Test auto-check catches low extraction confidence"""
        from app.services.kyc_engine import run_kyc_auto_checks
        from datetime import datetime, timedelta
        
        extraction_result = {
            "extracted_full_name": "Test User",
            "extracted_dob": "1990-01-01",
            "extracted_id_number": "123456",
            "extracted_expiry_date": (datetime.utcnow() + timedelta(days=365)).strftime("%Y-%m-%d"),
            "extracted_issuing_country": "US",
            "extraction_confidence": "low"  # Low confidence
        }
        
        result = run_kyc_auto_checks(extraction_result, "testuser")
        
        assert result["passed"] is False
        assert "confidence" in result["notes"].lower()
    
    def test_auto_checks_all_pass(self):
        """Test auto-checks pass with valid data"""
        from app.services.kyc_engine import run_kyc_auto_checks
        from datetime import datetime, timedelta
        
        extraction_result = {
            "extracted_full_name": "testuser",
            "extracted_dob": "1990-01-01",
            "extracted_id_number": "123456",
            "extracted_expiry_date": (datetime.utcnow() + timedelta(days=365)).strftime("%Y-%m-%d"),
            "extracted_issuing_country": "US",
            "extraction_confidence": "high"
        }
        
        result = run_kyc_auto_checks(extraction_result, "testuser")
        
        assert result["passed"] is True
        assert result["notes"] == "All auto-checks passed"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])