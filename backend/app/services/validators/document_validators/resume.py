from app.services.validators.models import create_check
from app.models.validation_result import ValidationStatus

def validate_resume(extracted_data: dict) -> list[dict]:
    checks = []
    
    if not extracted_data:
        email = None
        phone = None
    else:
        email = extracted_data.get("email")
        phone = extracted_data.get("phone")
        
    if email:
        checks.append(create_check(
            rule_id="resume_email_present",
            status=ValidationStatus.PASS,
            expected="Email present",
            actual=email,
            reason="Email extracted successfully"
        ))
    else:
        checks.append(create_check(
            rule_id="resume_email_present",
            status=ValidationStatus.REVIEW,
            expected="Email present",
            actual="None",
            reason="Missing required email producing REVIEW"
        ))
        
    # Phone is optional, if present, we note it. If missing, we skip it.
    if phone:
        checks.append(create_check(
            rule_id="resume_phone_present",
            status=ValidationStatus.PASS,
            expected="Phone present (optional)",
            actual=phone,
            reason="Optional phone extracted"
        ))
        
    return checks
