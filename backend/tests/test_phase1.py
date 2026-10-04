import os
import sys

# Ensure backend root is on sys.path for test runner
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import uuid
import pytest
from fastapi.testclient import TestClient

from main import app
from app.config import settings
from app.models.document import Document

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["phase"] == "1"


def test_upload_valid_pdf():
    pdf_path = os.path.join(
        "..", "samples", "marksheet", "sample_transcript.pdf"
    )
    assert os.path.exists(pdf_path)

    with open(pdf_path, "rb") as f:
        response = client.post(
            "/documents",
            files={
                "file": ("sample_transcript.pdf", f, "application/pdf")
            },
        )

    assert response.status_code == 201
    data = response.json()

    assert "id" in data
    assert data["original_filename"] == "sample_transcript.pdf"
    assert data["content_type"] == "application/pdf"
    assert data["status"] == "UPLOADED"
    assert data["file_size"] > 0

    doc_id = data["id"]

    # Verify storage path on disk
    expected_file_path = os.path.join(settings.UPLOAD_DIR, doc_id, "original.pdf")
    assert os.path.exists(expected_file_path)

    # Verify retrieval endpoint
    get_res = client.get(f"/documents/{doc_id}")
    assert get_res.status_code == 200
    get_data = get_res.json()
    assert get_data["id"] == doc_id
    assert get_data["original_filename"] == "sample_transcript.pdf"


def test_upload_valid_jpg():
    jpg_path = os.path.join(
        "..", "samples", "income_certificate", "sample_income.jpg"
    )
    assert os.path.exists(jpg_path)

    with open(jpg_path, "rb") as f:
        response = client.post(
            "/documents",
            files={"file": ("sample_income.jpg", f, "image/jpeg")},
        )

    assert response.status_code == 201
    data = response.json()
    doc_id = data["id"]
    assert data["content_type"] == "image/jpeg"

    expected_file_path = os.path.join(settings.UPLOAD_DIR, doc_id, "original.jpg")
    assert os.path.exists(expected_file_path)


def test_upload_valid_png():
    png_path = os.path.join("..", "samples", "identity", "sample_id.png")
    assert os.path.exists(png_path)

    with open(png_path, "rb") as f:
        response = client.post(
            "/documents",
            files={"file": ("sample_id.png", f, "image/png")},
        )

    assert response.status_code == 201
    data = response.json()
    doc_id = data["id"]
    assert data["content_type"] == "image/png"

    expected_file_path = os.path.join(settings.UPLOAD_DIR, doc_id, "original.png")
    assert os.path.exists(expected_file_path)


def test_upload_unsupported_file_type():
    txt_path = os.path.join("..", "samples", "invalid_doc.txt")
    assert os.path.exists(txt_path)

    with open(txt_path, "rb") as f:
        response = client.post(
            "/documents",
            files={"file": ("invalid_doc.txt", f, "text/plain")},
        )

    assert response.status_code == 400
    data = response.json()
    assert "Unsupported file type" in data["detail"]


def test_upload_oversized_file():
    large_path = os.path.join("..", "samples", "oversized.pdf")
    assert os.path.exists(large_path)

    with open(large_path, "rb") as f:
        response = client.post(
            "/documents",
            files={"file": ("oversized.pdf", f, "application/pdf")},
        )

    assert response.status_code == 400
    data = response.json()
    assert "maximum size limit" in data["detail"]


def test_get_non_existent_document():
    fake_id = str(uuid.uuid4())
    response = client.get(f"/documents/{fake_id}")
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == "Document not found."
