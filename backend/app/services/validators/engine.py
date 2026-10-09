from typing import Dict, Any
from app.models.validation_result import ValidationStatus
from app.services.validators.policy import POLICY_ID, POLICY_VERSION
from app.services.validators.models import create_check, aggregate_status
from app.services.validators.document_validators.marksheet import validate_marksheet
from app.services.validators.document_validators.income_certificate import validate_income_certificate
from app.services.validators.document_validators.identity import validate_identity
from app.services.validators.document_validators.resume import validate_resume

def validate_document(document_type: str, extracted_data: Dict[str, Any]) -> dict:
    """
    Validation engine that routes to specific validator based on document_type
    and returns a structured validation result dict ready for persistence.
    """
    checks = []
    
    if document_type == "MARKSHEET":
        checks = validate_marksheet(extracted_data)
    elif document_type == "INCOME_CERTIFICATE":
        checks = validate_income_certificate(extracted_data)
    elif document_type == "IDENTITY_DOCUMENT":
        checks = validate_identity(extracted_data)
    elif document_type == "RESUME":
        checks = validate_resume(extracted_data)
    else:
        checks.append(create_check(
            rule_id="supported_document_type",
            status=ValidationStatus.REVIEW,
            expected="Supported document type",
            actual=document_type if document_type else "None",
            reason="Unknown or unsupported document type requires manual review"
        ))
        
    overall = aggregate_status(checks)
    
    return {
        "overall_status": overall,
        "checks": checks,
        "policy_id": POLICY_ID,
        "policy_version": POLICY_VERSION
    }
