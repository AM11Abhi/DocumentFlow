import os
import uuid
import pytest
from fastapi.testclient import TestClient

from main import app
from app.models.document import DocumentStatus
from app.models.processing_job import JobStatus
from app.worker import run_worker_loop

client = TestClient(app)

def _upload_and_process(file_name, monkeypatch, mock_doc_type, mock_data):
    """Helper to upload a file and run worker with a mocked process_document."""
    
    # Mock the pipeline so we don't need real parsing logic here
    def mock_process_document(file_path):
        return {
            "document_type": mock_doc_type,
            "detection_score": 10,
            "matched_signals": ["mocked"],
            "extracted_text": "mocked text",
            "extracted_data": mock_data
        }
        
    monkeypatch.setattr("app.services.processors.pipeline.process_document", mock_process_document)
    
    pdf_path = os.path.join("..", "samples", "marksheet", "sample_transcript.pdf")
    with open(pdf_path, "rb") as f:
        response = client.post(
            "/documents",
            files={"file": (file_name, f, "application/pdf")},
        )
    assert response.status_code == 201
    doc_id = response.json()["id"]

    run_worker_loop(max_runs=1)
    
    response = client.get(f"/documents/{doc_id}")
    assert response.status_code == 200
    return response.json()

def test_successful_processing_with_validation_pass(monkeypatch):
    doc_data = _upload_and_process(
        "pass.pdf", monkeypatch, "MARKSHEET", {"gpa": "8.0"}
    )
    assert doc_data["status"] == DocumentStatus.COMPLETED
    assert doc_data["processing_job"]["status"] == JobStatus.COMPLETED
    
    pr = doc_data["processing_result"]
    assert pr is not None
    vr = pr["validation_result"]
    assert vr is not None
    assert vr["overall_status"] == "PASS"

def test_successful_processing_with_validation_fail(monkeypatch):
    doc_data = _upload_and_process(
        "bad_gpa.pdf", monkeypatch, "MARKSHEET", {"gpa": "5.0"}
    )
    # Validation FAIL is a business outcome, so job is COMPLETED
    assert doc_data["status"] == DocumentStatus.COMPLETED
    assert doc_data["processing_job"]["status"] == JobStatus.COMPLETED
    
    vr = doc_data["processing_result"]["validation_result"]
    assert vr["overall_status"] == "FAIL"

def test_successful_processing_with_validation_review(monkeypatch):
    doc_data = _upload_and_process(
        "review.pdf", monkeypatch, "MARKSHEET", {} # missing fields
    )
    assert doc_data["status"] == DocumentStatus.COMPLETED
    assert doc_data["processing_job"]["status"] == JobStatus.COMPLETED
    
    vr = doc_data["processing_result"]["validation_result"]
    assert vr["overall_status"] == "REVIEW"

def test_unexpected_validator_exception_follows_retry_mechanism(monkeypatch):
    def mock_process_document(file_path):
        return {
            "document_type": "MARKSHEET",
            "detection_score": 10,
            "matched_signals": [],
            "extracted_text": "",
            "extracted_data": {}
        }
        
    def mock_validate_document(doc_type, data):
        raise ValueError("Simulated unexpected validator crash")
        
    monkeypatch.setattr("app.services.processors.pipeline.process_document", mock_process_document)
    monkeypatch.setattr("app.services.validators.engine.validate_document", mock_validate_document)
    
    pdf_path = os.path.join("..", "samples", "marksheet", "sample_transcript.pdf")
    with open(pdf_path, "rb") as f:
        response = client.post(
            "/documents",
            files={"file": ("crash.pdf", f, "application/pdf")},
        )
    doc_id = response.json()["id"]

    # Run worker once
    run_worker_loop(max_runs=1)
    
    response = client.get(f"/documents/{doc_id}")
    doc_data = response.json()
    
    assert doc_data["status"] == DocumentStatus.FAILED
    assert doc_data["processing_job"]["status"] == JobStatus.FAILED
    assert doc_data["processing_job"]["attempts"] == 1
    assert "Simulated unexpected validator crash" in doc_data["processing_job"]["error"]
    
    # Validation result should NOT be persisted because transaction rolled back
    assert doc_data["processing_result"] is None

def test_retry_idempotency(monkeypatch):
    # Mock to pass successfully
    def mock_process_document(file_path):
        return {
            "document_type": "MARKSHEET",
            "detection_score": 10,
            "matched_signals": [],
            "extracted_text": "",
            "extracted_data": {"gpa": "8.0"}
        }
    monkeypatch.setattr("app.services.processors.pipeline.process_document", mock_process_document)
    
    pdf_path = os.path.join("..", "samples", "marksheet", "sample_transcript.pdf")
    with open(pdf_path, "rb") as f:
        response = client.post(
            "/documents",
            files={"file": ("retry.pdf", f, "application/pdf")},
        )
    doc_id = response.json()["id"]

    # Run worker once -> success
    run_worker_loop(max_runs=1)
    
    response = client.get(f"/documents/{doc_id}")
    assert response.json()["status"] == DocumentStatus.COMPLETED
    
    # We force the job status back to FAILED to test retry
    from app.db.session import SessionLocal
    from app.models.processing_job import ProcessingJob
    db = SessionLocal()
    job = db.query(ProcessingJob).filter(ProcessingJob.document_id == doc_id).first()
    job.status = JobStatus.FAILED
    db.commit()
    db.close()
    
    # Hit the retry endpoint
    retry_resp = client.post(f"/documents/{doc_id}/retry")
    assert retry_resp.status_code == 200
    
    # Run worker again
    run_worker_loop(max_runs=1)
    
    # Verify we didn't duplicate
    from app.models.processing_result import ProcessingResult
    from app.models.validation_result import ValidationResult
    db = SessionLocal()
    prs = db.query(ProcessingResult).filter(ProcessingResult.document_id == doc_id).all()
    vrs = db.query(ValidationResult).filter(ValidationResult.processing_result_id == prs[0].id).all()
    db.close()
    
    assert len(prs) == 1, "Should not duplicate ProcessingResult"
    assert len(vrs) == 1, "Should not duplicate ValidationResult"
