import os
import pytest
from fastapi.testclient import TestClient

from main import app
from app.models.document import DocumentStatus
from app.models.processing_job import JobStatus
from app.worker import run_worker_loop

client = TestClient(app)

def test_resume_processing_with_mocked_extractor(monkeypatch):
    """
    Test that processes a real representative extracted-text fixture
    and asserts RESUME classification with detection details.
    """
    resume_text = (
        "John Doe\n"
        "Email: john.doe@example.com\n"
        "Phone: 555-123-4567\n"
        "\n"
        "Experience:\n"
        "Software Engineer at Tech Corp (2020-Present)\n"
        "- Developed web applications using Python and React.\n"
        "\n"
        "Education:\n"
        "B.S. in Computer Science, State University\n"
        "\n"
        "Skills:\n"
        "Python, FastAPI, React, PostgreSQL\n"
    )

    # Mock extract_text so we don't need a real PDF
    monkeypatch.setattr(
        "app.services.processors.pipeline.extract_text",
        lambda file_path: resume_text
    )

    pdf_path = os.path.join(
        "..", "samples", "marksheet", "sample_transcript.pdf"
    )
    with open(pdf_path, "rb") as f:
        # Upload a document
        response = client.post(
            "/documents",
            files={
                "file": ("test_resume.pdf", f, "application/pdf")
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
    
    result = doc_data["processing_result"]
    assert result["document_type"] == "RESUME"
    assert result["detection_score"] is not None
    assert result["detection_score"] > 0
    assert result["matched_signals"] is not None
    assert len(result["matched_signals"]) > 0
    
    # Check that extracted data worked too
    assert result["extracted_data"]["email"] == "john.doe@example.com"
    assert "555-123-4567" in result["extracted_data"]["phone"]

