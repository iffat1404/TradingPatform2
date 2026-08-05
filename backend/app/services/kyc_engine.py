from datetime import datetime, timedelta, timezone
from typing import Dict, Any
from app.core.config import settings


def run_kyc_auto_checks(extraction_result: Dict[str, Any], registered_username: str) -> Dict[str, Any]:
    """
    Run deterministic KYC auto-checks per Section H.3.
    
    These are plain code checks, not GenAI. They provide informational
    suggestions to the Admin but never auto-approve KYC.
    
    Checks:
    1. Not expired - extracted_expiry_date > today
    2. Minimum age - today - extracted_dob >= KYC_MIN_AGE_YEARS
    3. Name match - fuzzy match >= KYC_NAME_MATCH_THRESHOLD
    4. Extraction confidence - must be "high"
    
    Returns:
        {
            "passed": bool,
            "notes": str
        }
    """
    failed_checks = []
    
    # Check 1: Not expired
    extracted_expiry = extraction_result.get("extracted_expiry_date")
    if extracted_expiry:
        if isinstance(extracted_expiry, str):
            try:
                extracted_expiry = datetime.strptime(extracted_expiry, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except ValueError:
                failed_checks.append("Could not parse expiry date")
                extracted_expiry = None
        
        if extracted_expiry and extracted_expiry <= datetime.now(timezone.utc):
            failed_checks.append("ID expired")
    else:
        failed_checks.append("Missing expiry date")
    
    # Check 2: Minimum age
    extracted_dob = extraction_result.get("extracted_dob")
    if extracted_dob:
        if isinstance(extracted_dob, str):
            try:
                extracted_dob = datetime.strptime(extracted_dob, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except ValueError:
                failed_checks.append("Could not parse date of birth")
                extracted_dob = None
        
        if extracted_dob:
            age = datetime.now(timezone.utc) - extracted_dob
            age_years = age.days / 365.25
            if age_years < settings.KYC_MIN_AGE_YEARS:
                failed_checks.append(f"Under minimum age ({settings.KYC_MIN_AGE_YEARS} years)")
    else:
        failed_checks.append("Missing date of birth")
    
    # Check 3: Name match (fuzzy)
    extracted_name = extraction_result.get("extracted_full_name")
    if extracted_name and registered_username:
        # Simple fuzzy match - check if registered username is contained in extracted name
        # or vice versa, or if they're similar after removing spaces/case
        extracted_lower = extracted_name.lower().replace(" ", "")
        username_lower = registered_username.lower().replace(" ", "")
        
        # Calculate simple similarity ratio
        from difflib import SequenceMatcher
        similarity = SequenceMatcher(None, extracted_lower, username_lower).ratio()
        
        if similarity < settings.KYC_NAME_MATCH_THRESHOLD:
            failed_checks.append(f"Name mismatch (similarity: {similarity:.2f})")
    elif not extracted_name:
        failed_checks.append("Missing extracted name")
    
    # Check 4: Extraction confidence
    confidence = extraction_result.get("extraction_confidence")
    if confidence != "high":
        failed_checks.append(f"Low extraction confidence: {confidence}")
    
    # Determine overall result
    passed = len(failed_checks) == 0
    
    # Format notes
    if passed:
        notes = "All auto-checks passed"
    else:
        notes = "; ".join(failed_checks)
    
    return {
        "passed": passed,
        "notes": notes
    }