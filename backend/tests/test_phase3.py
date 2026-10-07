import os
import sys
import uuid
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from main import app
from app.models.document import DocumentStatus
from app.models.processing_job import JobStatus
from app.worker import run_worker_loop

client = TestClient(app)

def test_phase3_successful_processing_with_result():
    pdf_path = os.path.join(
        "..", "samples", "marksheet", "sample_transcript.pdf"
    )
    with open(pdf_path, "rb") as f:
        # Upload a document
        response = client.post(
            "/documents",
            files={
                "file": ("test_marksheet.pdf", f, "application/pdf")
            },
        )
    assert response.status_code == 201
    doc_id = response.json()["id"]

    # Run the worker to process the queued job
    run_worker_loop(max_runs=1)

    # Get the document
    response = client.get(f"/documents/{doc_id}")
    assert response.status_code == 200
    doc_data = response.json()

    assert doc_data["status"] == DocumentStatus.COMPLETED
    assert doc_data["processing_job"]["status"] == JobStatus.COMPLETED
    assert doc_data["processing_result"] is not None
    assert "document_type" in doc_data["processing_result"]
    assert "detection_score" in doc_data["processing_result"]
    assert "matched_signals" in doc_data["processing_result"]
    assert "extracted_text" in doc_data["processing_result"]
    assert "extracted_data" in doc_data["processing_result"]
