from app.services.validators.models import create_check
from app.models.validation_result import ValidationStatus

def validate_identity(extracted_data: dict) -> list[dict]:
    checks = []
    
    if not extracted_data:
        dob = None
    else:
        dob = extracted_data.get("dob")
        
    if dob:
        checks.append(create_check(
            rule_id="identity_dob_present",
            status=ValidationStatus.PASS,
            expected="DOB present",
            actual=dob,
            reason="DOB successfully extracted"
        ))
    else:
        checks.append(create_check(
            rule_id="identity_dob_present",
            status=ValidationStatus.REVIEW,
            expected="DOB present",
            actual="None",
            reason="Missing required values producing REVIEW"
        ))
        
    return checks
