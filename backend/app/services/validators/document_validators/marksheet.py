from app.services.validators.models import create_check
from app.models.validation_result import ValidationStatus
from app.services.validators.policy import THRESHOLDS

def validate_marksheet(extracted_data: dict) -> list[dict]:
    checks = []
    
    if not extracted_data:
        checks.append(create_check(
            rule_id="min_cgpa",
            status=ValidationStatus.REVIEW,
            expected="CGPA or Percentage",
            actual="None",
            reason="Missing required values producing REVIEW"
        ))
        return checks
        
    gpa_str = extracted_data.get("gpa")
    percentage_str = extracted_data.get("percentage")
    
    if gpa_str:
        try:
            gpa = float(gpa_str)
            min_cgpa = THRESHOLDS["MIN_CGPA"]
            if gpa >= min_cgpa:
                checks.append(create_check(
                    rule_id="min_cgpa",
                    status=ValidationStatus.PASS,
                    expected=f">= {min_cgpa}",
                    actual=str(gpa),
                    reason="CGPA meets the minimum requirement"
                ))
            else:
                checks.append(create_check(
                    rule_id="min_cgpa",
                    status=ValidationStatus.FAIL,
                    expected=f">= {min_cgpa}",
                    actual=str(gpa),
                    reason="CGPA is below the minimum requirement"
                ))
        except ValueError:
            checks.append(create_check(
                rule_id="min_cgpa",
                status=ValidationStatus.REVIEW,
                expected="Numeric CGPA",
                actual=gpa_str,
                reason="Malformed numeric value producing REVIEW"
            ))
    elif percentage_str:
        checks.append(create_check(
            rule_id="min_cgpa",
            status=ValidationStatus.REVIEW,
            expected="CGPA available",
            actual="Only percentage available",
            reason="Percentage available but CGPA is not; unsupported requirement for review"
        ))
    else:
        checks.append(create_check(
            rule_id="min_cgpa",
            status=ValidationStatus.REVIEW,
            expected="CGPA or Percentage",
            actual="None",
            reason="Missing required values producing REVIEW"
        ))
        
    return checks
