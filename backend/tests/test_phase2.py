import os
import sys
import uuid
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from main import app
from app.config import settings
from app.db.session import SessionLocal
from app.models.document import Document, DocumentStatus
from app.models.processing_job import ProcessingJob, JobStatus
from app.services.queue import dequeue_job, get_redis_client
from app.worker import process_job_by_id, run_worker_loop

client = TestClient(app)



def test_upload_creates_queued_processing_job():
    pdf_path = os.path.join(
        "..", "samples", "marksheet", "sample_transcript.pdf"
    )
    assert os.path.exists(pdf_path)

    with open(pdf_path, "rb") as f:
        response = client.post(
            "/documents",
            files={
                "file": ("phase2_sample.pdf", f, "application/pdf")
            },
        )

    assert response.status_code == 201
    data = response.json()

    assert data["status"] == "UPLOADED"
    assert "processing_job" in data
    assert data["processing_job"] is not None

    job_info = data["processing_job"]
    assert job_info["status"] == "QUEUED"
    assert job_info["attempts"] == 0
    assert job_info["document_id"] == data["id"]

    # Verify message is in Redis queue
    job_item = dequeue_job(timeout=1)
    assert job_item is not None
    job_id, doc_id = job_item
    assert str(job_id) == job_info["id"]
    assert str(doc_id) == data["id"]


def test_successful_worker_processing():
    pdf_path = os.path.join(
        "..", "samples", "marksheet", "sample_transcript.pdf"
    )
    with open(pdf_path, "rb") as f:
        response = client.post(
            "/documents",
            files={
                "file": ("success_sample.pdf", f, "application/pdf")
            },
        )
    assert response.status_code == 201
    doc_id = response.json()["id"]

    # Run worker loop for 1 run
    run_worker_loop(poll_timeout=1, max_runs=1)

    # Inspect document and job state
    get_res = client.get(f"/documents/{doc_id}")
    assert get_res.status_code == 200
    doc_data = get_res.json()

    assert doc_data["status"] == "COMPLETED"
    job_data = doc_data["processing_job"]
    assert job_data["status"] == "COMPLETED"
    assert job_data["attempts"] == 1
    assert job_data["started_at"] is not None
    assert job_data["completed_at"] is not None
    assert job_data["error"] is None


def test_failed_worker_processing():
    pdf_path = os.path.join(
        "..", "samples", "marksheet", "sample_transcript.pdf"
    )
    with open(pdf_path, "rb") as f:
        response = client.post(
            "/documents",
            files={
                "file": ("fail_sample.pdf", f, "application/pdf")
            },
        )
    assert response.status_code == 201
    doc_data = response.json()
    doc_id = doc_data["id"]
    job_id = doc_data["processing_job"]["id"]

    # Pop item from queue and process with forced failure
    db = SessionLocal()
    try:
        success = process_job_by_id(
            db, uuid.UUID(job_id), uuid.UUID(doc_id), force_fail=True
        )
        assert success is False
    finally:
        db.close()

    # Verify status changed to FAILED and error populated
    get_res = client.get(f"/documents/{doc_id}")
    assert get_res.status_code == 200
    res_data = get_res.json()

    assert res_data["status"] == "FAILED"
    job_info = res_data["processing_job"]
    assert job_info["status"] == "FAILED"
    assert job_info["attempts"] == 1
    assert job_info["error"] is not None
    assert "Simulated processing error" in job_info["error"]


def test_job_retry_and_max_attempts_limit():
    pdf_path = os.path.join(
        "..", "samples", "marksheet", "sample_transcript.pdf"
    )
    with open(pdf_path, "rb") as f:
        response = client.post(
            "/documents",
            files={
                "file": ("retry_fail_test.pdf", f, "application/pdf")
            },
        )
    doc_id = response.json()["id"]
    job_id = response.json()["processing_job"]["id"]

    db = SessionLocal()
    try:
        # Attempt 1 -> Fail
        process_job_by_id(
            db, uuid.UUID(job_id), uuid.UUID(doc_id), force_fail=True
        )

        # Retry 1 via API
        retry_res1 = client.post(f"/documents/{doc_id}/retry")
        assert retry_res1.status_code == 200
        assert retry_res1.json()["processing_job"]["status"] == "QUEUED"

        # Attempt 2 -> Fail
        process_job_by_id(
            db, uuid.UUID(job_id), uuid.UUID(doc_id), force_fail=True
        )

        # Retry 2 via API
        retry_res2 = client.post(f"/documents/{doc_id}/retry")
        assert retry_res2.status_code == 200

        # Attempt 3 -> Fail (reaches max 3 attempts)
        process_job_by_id(
            db, uuid.UUID(job_id), uuid.UUID(doc_id), force_fail=True
        )

        # Attempt 4th retry -> should fail with HTTP 400 (max attempts reached)
        retry_res3 = client.post(f"/documents/{doc_id}/retry")
        assert retry_res3.status_code == 400
        assert "Maximum processing attempts reached" in retry_res3.json()["detail"]

        # Further worker attempt on job with 3 attempts -> should remain FAILED
        result = process_job_by_id(
            db, uuid.UUID(job_id), uuid.UUID(doc_id), force_fail=True
        )
        assert result is False

        # Verify job remains FAILED and attempts is 3
        get_res = client.get(f"/documents/{doc_id}")
        job_data = get_res.json()["processing_job"]
        assert job_data["status"] == "FAILED"
        assert job_data["attempts"] == 3
        # Same job ID reused across retries
        assert job_data["id"] == job_id

    finally:
        db.close()
