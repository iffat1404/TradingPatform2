from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, timezone
import uuid
import os
from app.core.db import get_db
from app.core.security import get_current_user
from app.core.config import settings
from app.models.orm import Account, KYCSubmission, KYCStatus
from app.models.schemas import KYCSubmissionCreate, KYCStatusResponse
from app.services.kyc_engine import run_kyc_auto_checks
from app.services.genai_client import extract_id_document_fields

router = APIRouter()


@router.post("/submit", status_code=status.HTTP_202_ACCEPTED)
async def submit_kyc(
    id_type: str = Form(...),
    id_document: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Submit KYC document for review.
    
    Accepts ID document upload, validates file type and size,
    stores the document, and triggers GenAI extraction and auto-checks.
    """
    # Validate ID type
    valid_id_types = ["passport", "drivers_license", "national_id"]
    if id_type not in valid_id_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid ID type. Must be one of: {valid_id_types}"
        )
    
    # Validate file size
    file_content = await id_document.read()
    file_size_mb = len(file_content) / (1024 * 1024)
    
    if file_size_mb > settings.KYC_MAX_UPLOAD_SIZE_MB:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size exceeds maximum of {settings.KYC_MAX_UPLOAD_SIZE_MB}MB"
        )
    
    # Validate MIME type
    if id_document.content_type not in settings.KYC_ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Allowed types: {settings.KYC_ALLOWED_MIME_TYPES}"
        )
    
    # Generate submission ID
    submission_id = str(uuid.uuid4())
    
    # Create upload directory if it doesn't exist
    upload_dir = f"uploads/kyc/{current_user['account_id']}"
    os.makedirs(upload_dir, exist_ok=True)
    
    # Determine file extension
    file_extension = os.path.splitext(id_document.filename)[1]
    if not file_extension:
        # Default extension based on content type
        if id_document.content_type == "application/pdf":
            file_extension = ".pdf"
        elif id_document.content_type in ["image/jpeg", "image/jpg"]:
            file_extension = ".jpg"
        elif id_document.content_type == "image/png":
            file_extension = ".png"
        else:
            file_extension = ".bin"
    
    # Save file
    file_path = os.path.join(upload_dir, f"{submission_id}{file_extension}")
    with open(file_path, "wb") as f:
        f.write(file_content)
    
    # Trigger GenAI extraction (graceful degradation on failure)
    try:
        extraction_result = extract_id_document_fields(file_path, id_document.content_type)
    except Exception as e:
        # Graceful degradation - continue with null extraction if GenAI fails
        extraction_result = {
            "extracted_full_name": None,
            "extracted_dob": None,
            "extracted_id_number": None,
            "extracted_expiry_date": None,
            "extracted_issuing_country": None,
            "extraction_confidence": None
        }
    
    # Run deterministic auto-checks
    auto_check_result = run_kyc_auto_checks(
        extraction_result,
        current_user["username"]  # Registered username for name comparison
    )
    
    # Create KYC submission record
    submission = KYCSubmission(
        id=submission_id,
        account_id=current_user["account_id"],
        id_type=id_type,
        document_path=file_path,
        extracted_full_name=extraction_result.get("extracted_full_name"),
        extracted_dob=extraction_result.get("extracted_dob"),
        extracted_id_number=extraction_result.get("extracted_id_number"),
        extracted_expiry_date=extraction_result.get("extracted_expiry_date"),
        extracted_issuing_country=extraction_result.get("extracted_issuing_country"),
        extraction_confidence=extraction_result.get("extraction_confidence"),
        auto_check_passed=auto_check_result["passed"],
        auto_check_notes=auto_check_result["notes"],
        status=KYCStatus.PENDING_REVIEW,
        submitted_at=datetime.now(timezone.utc)
    )
    
    db.add(submission)
    
    # Update account KYC status
    account = db.query(Account).filter(Account.id == current_user["account_id"]).first()
    if account:
        account.kyc_status = KYCStatus.PENDING_REVIEW
    
    db.commit()
    
    return {
        "submission_id": submission_id,
        "status": "PROCESSING",
        "message": "Document submitted successfully. Processing extraction and auto-checks."
    }


@router.get("/status", response_model=KYCStatusResponse)
def get_kyc_status(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current KYC status for the authenticated user.
    """
    account = db.query(Account).filter(Account.id == current_user["account_id"]).first()
    
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found"
        )
    
    # Get the most recent submission if rejected to show review notes
    review_notes = None
    if account.kyc_status == KYCStatus.REJECTED:
        latest_submission = db.query(KYCSubmission).filter(
            KYCSubmission.account_id == current_user["account_id"]
        ).order_by(KYCSubmission.submitted_at.desc()).first()
        
        if latest_submission:
            review_notes = latest_submission.review_notes
    
    return KYCStatusResponse(
        kyc_status=account.kyc_status,
        review_notes=review_notes
    )