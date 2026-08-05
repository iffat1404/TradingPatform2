"""
Seed script to create an admin account.
Run this script to create an admin user for testing.
Per spec Section 6: Admin credentials should be set via .env, never committed.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.orm import Session
from app.core.db import SessionLocal
from app.core.security import get_password_hash
from app.core.config import settings
from app.models.orm import Account, Role, KYCStatus
import uuid

def create_admin_account():
    db: Session = SessionLocal()
    try:
        # Get admin credentials from environment or config per spec Section 6
        admin_username = settings.ADMIN_BOOTSTRAP_USERNAME
        admin_password = settings.ADMIN_BOOTSTRAP_PASSWORD
        
        # Check if admin already exists
        existing_admin = db.query(Account).filter(Account.username == admin_username).first()
        if existing_admin:
            print("Admin account already exists!")
            print(f"Username: {admin_username}")
            print(f"Role: {existing_admin.role}")
            return

        # Create admin account
        admin = Account(
            id=str(uuid.uuid4()),
            username=admin_username,
            password_hash=get_password_hash(admin_password),
            role=Role.ADMIN,
            kyc_status=KYCStatus.APPROVED,  # Admins don't need KYC
            starting_capital=0,
            cash_balance=0
        )
        
        db.add(admin)
        db.commit()
        db.refresh(admin)
        
        print("Admin account created successfully!")
        print(f"Username: {admin_username}")
        print(f"Password: {admin_password}")
        print(f"Role: {admin.role}")
        print(f"ID: {admin.id}")
        
    except Exception as e:
        print(f"Error creating admin account: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    create_admin_account()
