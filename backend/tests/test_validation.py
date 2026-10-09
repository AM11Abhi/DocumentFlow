import pytest
import json
from app.services.validators.engine import validate_document
from app.services.validators.models import aggregate_status, create_check
from app.models.validation_result import ValidationStatus

def test_cgpa_meeting_minimum():
    res = validate_document("MARKSHEET", {"gpa": "7.5"})
    assert res["overall_status"] == ValidationStatus.PASS
    assert len(res["checks"]) == 1
    assert res["checks"][0]["status"] == "PASS"

def test_cgpa_below_minimum():
    res = validate_document("MARKSHEET", {"gpa": "6.5"})
    assert res["overall_status"] == ValidationStatus.FAIL
    assert len(res["checks"]) == 1
    assert res["checks"][0]["status"] == "FAIL"

def test_income_at_or_below_threshold():
    res = validate_document("INCOME_CERTIFICATE", {"amount": "500000"})
    assert res["overall_status"] == ValidationStatus.PASS
    
    res2 = validate_document("INCOME_CERTIFICATE", {"amount": "400,000.50"})
    assert res2["overall_status"] == ValidationStatus.PASS

def test_income_above_threshold():
    res = validate_document("INCOME_CERTIFICATE", {"amount": "600,000"})
    assert res["overall_status"] == ValidationStatus.FAIL

def test_missing_required_values_producing_review():
    res_marksheet = validate_document("MARKSHEET", {})
    assert res_marksheet["overall_status"] == ValidationStatus.REVIEW
    assert "Missing required values" in res_marksheet["checks"][0]["reason"]
    
    res_income = validate_document("INCOME_CERTIFICATE", {})
    assert res_income["overall_status"] == ValidationStatus.REVIEW

    res_identity = validate_document("IDENTITY_DOCUMENT", {})
    assert res_identity["overall_status"] == ValidationStatus.REVIEW
    
    res_resume = validate_document("RESUME", {})
    assert res_resume["overall_status"] == ValidationStatus.REVIEW

def test_malformed_numeric_values_producing_review():
    res = validate_document("MARKSHEET", {"gpa": "A"})
    assert res["overall_status"] == ValidationStatus.REVIEW
    assert "Malformed numeric value" in res["checks"][0]["reason"]
    
    res2 = validate_document("INCOME_CERTIFICATE", {"amount": "Fifty Thousand"})
    assert res2["overall_status"] == ValidationStatus.REVIEW
    
def test_unknown_document_type_producing_review():
    res = validate_document("UNKNOWN", {"some": "data"})
    assert res["overall_status"] == ValidationStatus.REVIEW
    assert "Unknown or unsupported" in res["checks"][0]["reason"]
    
def test_overall_status_aggregation():
    checks_mixed = [
        create_check("r1", ValidationStatus.PASS, "E", "A", "R"),
        create_check("r2", ValidationStatus.FAIL, "E", "A", "R"),
        create_check("r3", ValidationStatus.REVIEW, "E", "A", "R")
    ]
    assert aggregate_status(checks_mixed) == ValidationStatus.FAIL
    
    checks_review = [
        create_check("r1", ValidationStatus.PASS, "E", "A", "R"),
        create_check("r3", ValidationStatus.REVIEW, "E", "A", "R")
    ]
    assert aggregate_status(checks_review) == ValidationStatus.REVIEW

def test_rules_not_apply_skipped():
    # If phone is missing in RESUME, it doesn't create a check (it is optional)
    res = validate_document("RESUME", {"email": "test@test.com"})
    assert res["overall_status"] == ValidationStatus.PASS
    assert len(res["checks"]) == 1
    assert res["checks"][0]["rule_id"] == "resume_email_present"

def test_json_serialization():
    res = validate_document("MARKSHEET", {"gpa": "8.0"})
    json_str = json.dumps(res["checks"])
    assert "PASS" in json_str
