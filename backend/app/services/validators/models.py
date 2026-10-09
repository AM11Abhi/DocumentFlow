from app.models.validation_result import ValidationStatus

def create_check(rule_id: str, status: ValidationStatus, expected: str, actual: str, reason: str) -> dict:
    """Helper to create a structured check."""
    return {
        "rule_id": rule_id,
        "status": status.value,
        "expected": expected,
        "actual": actual,
        "reason": reason
    }

def aggregate_status(checks: list[dict]) -> ValidationStatus:
    """
    1. If any applicable check is FAIL, overall status is FAIL.
    2. Otherwise, if any applicable check is REVIEW, overall status is REVIEW.
    3. Otherwise, overall status is PASS.
    """
    if not checks:
        # If no rules applied, technically it passes (or requires review? 
        # The prompt says: "Rules that do not apply must be skipped, not counted as passing checks. 
        # A missing or unparseable required value must not be treated as a definitive business failure."
        # If it's literally empty, usually PASS is safest if no rules failed/reviewed.
        # But wait, unknown docs give REVIEW check. 
        pass

    has_review = False
    for check in checks:
        if check["status"] == ValidationStatus.FAIL.value:
            return ValidationStatus.FAIL
        if check["status"] == ValidationStatus.REVIEW.value:
            has_review = True
            
    if has_review:
        return ValidationStatus.REVIEW
        
    return ValidationStatus.PASS
