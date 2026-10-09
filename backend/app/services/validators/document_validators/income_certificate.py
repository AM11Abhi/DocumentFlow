from app.services.validators.models import create_check
from app.models.validation_result import ValidationStatus
from app.services.validators.policy import THRESHOLDS

def validate_income_certificate(extracted_data: dict) -> list[dict]:
    checks = []
    
    if not extracted_data:
        amount_str = None
    else:
        amount_str = extracted_data.get("amount") or extracted_data.get("income_amount_found")
        
    if amount_str:
        try:
            clean_str = amount_str.replace(",", "")
            amount = float(clean_str)
            max_income = THRESHOLDS["MAX_INCOME_INR"]
            
            if amount <= max_income:
                checks.append(create_check(
                    rule_id="max_income",
                    status=ValidationStatus.PASS,
                    expected=f"<= {max_income}",
                    actual=str(amount),
                    reason="Income is at or below the maximum threshold"
                ))
            else:
                checks.append(create_check(
                    rule_id="max_income",
                    status=ValidationStatus.FAIL,
                    expected=f"<= {max_income}",
                    actual=str(amount),
                    reason="Income exceeds the maximum threshold"
                ))
        except ValueError:
            checks.append(create_check(
                rule_id="max_income",
                status=ValidationStatus.REVIEW,
                expected="Numeric Income Amount",
                actual=amount_str,
                reason="Malformed numeric value producing REVIEW"
            ))
    else:
        checks.append(create_check(
            rule_id="max_income",
            status=ValidationStatus.REVIEW,
            expected="Numeric Income Amount",
            actual="None",
            reason="Missing required values producing REVIEW"
        ))
        
    return checks
