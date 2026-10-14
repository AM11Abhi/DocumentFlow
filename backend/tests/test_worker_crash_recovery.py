import os
import sys
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional
import pytest
from sqlalchemy.orm import Session

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config import settings
from app.db.session import SessionLocal
from app.models.document import Document, DocumentStatus
from app.models.processing_job import ProcessingJob, JobStatus
from app.models.processing_result import ProcessingResult
from app.services.queue import dequeue_job, enqueue_job
from app.worker import (
    process_job_by_id,
    recover_stale_jobs,
    renew_lease,
    run_worker_loop,
    JobHeartbeat,
    MAX_ATTEMPTS,
)


@pytest.fixture
def clean_db():
    """Provides a fresh database session and cleans up any created documents at teardown."""
    db = SessionLocal()
    created_doc_ids = []

    def _create_doc_and_job(
        status: JobStatus = JobStatus.QUEUED,
        doc_status: DocumentStatus = DocumentStatus.UPLOADED,
        attempts: int = 0,
        lease_token: Optional[uuid.UUID] = None,
        lease_expires_at: Optional[datetime] = None,
        filename: str = "recovery_test.pdf",
        storage_path: Optional[str] = None,
    ) -> tuple[Document, ProcessingJob]:
        doc_id = uuid.uuid4()
        job_id = uuid.uuid4()
        if storage_path is None:
            storage_path = os.path.abspath(
                os.path.join(
                    os.path.dirname(__file__),
                    "..",
                    "..",
                    "samples",
                    "marksheet",
                    "sample_transcript.pdf",
                )
            )

        doc = Document(
            id=doc_id,
            original_filename=filename,
            content_type="application/pdf",
            file_size=1024,
            storage_path=storage_path,
            status=doc_status,
        )
        job = ProcessingJob(
            id=job_id,
            document_id=doc_id,
            status=status,
            attempts=attempts,
            lease_token=lease_token,
            lease_expires_at=lease_expires_at,
        )
        db.add(doc)
        db.add(job)
        db.commit()
        db.refresh(doc)
        db.refresh(job)

        created_doc_ids.append(doc_id)
        return doc, job

    yield db, _create_doc_and_job

    # Teardown: delete created documents (cascades to jobs and results)
    for d_id in created_doc_ids:
        doc = db.query(Document).filter(Document.id == d_id).first()
        if doc:
            db.delete(doc)
    db.commit()
    db.close()


def test_healthy_job_remains_processing_while_lease_valid(clean_db):
    """Scenario 1: A healthy job in PROCESSING with a future lease expiration is not reclaimed."""
    db, create_fn = clean_db
    now = datetime.now(timezone.utc)
    token = uuid.uuid4()

    doc, job = create_fn(
        status=JobStatus.PROCESSING,
        doc_status=DocumentStatus.PROCESSING,
        attempts=1,
        lease_token=token,
        lease_expires_at=now + timedelta(seconds=60),
    )

    recovered = recover_stale_jobs(db=db, now=now)

    assert job.id not in recovered
    db.refresh(job)
    assert job.status == JobStatus.PROCESSING
    assert job.attempts == 1
    assert job.lease_token == token
    assert job.lease_expires_at == now + timedelta(seconds=60)


def test_expired_job_recovered_and_requeued(clean_db):
    """Scenario 2: An expired PROCESSING job with attempts < MAX_ATTEMPTS is re-queued."""
    db, create_fn = clean_db
    now = datetime.now(timezone.utc)
    token = uuid.uuid4()

    doc, job = create_fn(
        status=JobStatus.PROCESSING,
        doc_status=DocumentStatus.PROCESSING,
        attempts=1,
        lease_token=token,
        lease_expires_at=now - timedelta(seconds=10),
    )

    recovered = recover_stale_jobs(db=db, now=now)

    assert job.id in recovered
    db.refresh(job)
    db.refresh(doc)

    assert job.status == JobStatus.QUEUED
    assert job.lease_token is None
    assert job.lease_expires_at is None
    assert "expired" in job.error.lower()
    assert doc.status == DocumentStatus.UPLOADED

    # Verify re-enqueued to Redis
    item = dequeue_job(timeout=1)
    assert item is not None
    assert item == (job.id, doc.id)


def test_expired_job_at_max_attempts_becomes_failed(clean_db):
    """Scenario 3: An expired PROCESSING job that has reached MAX_ATTEMPTS is marked FAILED."""
    db, create_fn = clean_db
    now = datetime.now(timezone.utc)
    token = uuid.uuid4()

    doc, job = create_fn(
        status=JobStatus.PROCESSING,
        doc_status=DocumentStatus.PROCESSING,
        attempts=MAX_ATTEMPTS,
        lease_token=token,
        lease_expires_at=now - timedelta(seconds=10),
    )

    recovered = recover_stale_jobs(db=db, now=now)

    assert job.id in recovered
    db.refresh(job)
    db.refresh(doc)

    assert job.status == JobStatus.FAILED
    assert job.lease_token is None
    assert job.lease_expires_at is None
    assert job.completed_at is not None
    assert "maximum" in job.error.lower()
    assert doc.status == DocumentStatus.FAILED

    # Verify NOT re-enqueued
    item = dequeue_job(timeout=1)
    assert item is None


def test_duplicate_messages_do_not_start_duplicate_processing(clean_db):
    """Scenario 4: Duplicate queue messages for an already PROCESSING or COMPLETED job are rejected."""
    db, create_fn = clean_db
    now = datetime.now(timezone.utc)
    token = uuid.uuid4()

    doc, job = create_fn(
        status=JobStatus.PROCESSING,
        doc_status=DocumentStatus.PROCESSING,
        attempts=1,
        lease_token=token,
        lease_expires_at=now + timedelta(seconds=60),
    )

    # Worker attempts to claim an already PROCESSING job from a duplicate queue message
    success = process_job_by_id(db, job.id, doc.id)
    assert success is False

    db.refresh(job)
    assert job.attempts == 1  # Not incremented
    assert job.lease_token == token  # Ownership token not overwritten

    # Set to COMPLETED and test duplicate message
    job.status = JobStatus.COMPLETED
    job.lease_token = None
    db.commit()

    success_completed = process_job_by_id(db, job.id, doc.id)
    assert success_completed is False
    db.refresh(job)
    assert job.status == JobStatus.COMPLETED
    assert job.attempts == 1


def test_stale_worker_cannot_commit_after_ownership_changes(clean_db, monkeypatch):
    """Scenario 5: A slow worker whose lease was recovered cannot commit results."""
    db, create_fn = clean_db
    doc, job = create_fn(status=JobStatus.QUEUED, attempts=0)

    # Hook process_document to simulate lease expiration & recovery mid-processing
    def slow_process_with_hijack(file_path):
        # Simulate recovery sweep or another worker claiming the job
        with SessionLocal() as hijack_db:
            hj = hijack_db.query(ProcessingJob).filter(ProcessingJob.id == job.id).first()
            hj.lease_token = uuid.uuid4()  # Changed to new worker's token
            hj.status = JobStatus.QUEUED
            hijack_db.commit()

        return {
            "document_type": "MARKSHEET",
            "detection_score": 90,
            "matched_signals": ["transcript"],
            "extracted_text": "sample",
            "extracted_data": {"gpa": "9.0"},
        }

    monkeypatch.setattr(
        "app.services.processors.pipeline.process_document",
        slow_process_with_hijack,
    )

    success = process_job_by_id(db, job.id, doc.id, enable_heartbeat=False)
    assert success is False

    # Verify no ProcessingResult was committed by the stale worker
    result = db.query(ProcessingResult).filter(ProcessingResult.document_id == doc.id).first()
    assert result is None

    # Job is still QUEUED with the new token
    db.refresh(job)
    assert job.status == JobStatus.QUEUED


def test_concurrent_recovery_attempts_do_not_reclaim_same_job_twice(clean_db):
    """Scenario 6: Concurrent recovery runs skip locked rows and do not double-reclaim."""
    db, create_fn = clean_db
    now = datetime.now(timezone.utc)
    token = uuid.uuid4()

    doc, job = create_fn(
        status=JobStatus.PROCESSING,
        doc_status=DocumentStatus.PROCESSING,
        attempts=1,
        lease_token=token,
        lease_expires_at=now - timedelta(seconds=10),
    )

    # First recovery sweep
    rec1 = recover_stale_jobs(db=db, now=now)
    assert job.id in rec1

    # Immediate second recovery sweep
    rec2 = recover_stale_jobs(db=db, now=now)
    assert job.id not in rec2  # Already reclaimed and transitioned to QUEUED

    # Redis queue should contain exactly 1 message
    item1 = dequeue_job(timeout=1)
    assert item1 == (job.id, doc.id)

    item2 = dequeue_job(timeout=1)
    assert item2 is None  # No duplicate message


def test_postgresql_concurrent_recovery_skip_locked(clean_db):
    """Scenario 6b: Real PostgreSQL multi-session integration test for SKIP LOCKED row locks.

    Connection 1 holds an uncommitted row lock on an expired job.
    Connection 2 runs recover_stale_jobs() and skips the locked row without blocking.
    """
    db, create_fn = clean_db
    now = datetime.now(timezone.utc)
    token = uuid.uuid4()

    doc, job = create_fn(
        status=JobStatus.PROCESSING,
        doc_status=DocumentStatus.PROCESSING,
        attempts=1,
        lease_token=token,
        lease_expires_at=now - timedelta(seconds=10),
    )

    # Open a separate independent PostgreSQL session (Connection 1)
    conn1_session = SessionLocal()
    try:
        # Connection 1 locks the job row with FOR UPDATE in an active transaction
        locked_job = (
            conn1_session.query(ProcessingJob)
            .filter(ProcessingJob.id == job.id)
            .with_for_update()
            .first()
        )
        assert locked_job is not None

        # While Connection 1 holds the row lock, Connection 2 runs recover_stale_jobs()
        # With PostgreSQL SKIP LOCKED, Connection 2 skips the locked row without blocking
        conn2_session = SessionLocal()
        try:
            recovered_by_conn2 = recover_stale_jobs(db=conn2_session, now=now)
            # Connection 2 skipped the row held by Connection 1
            assert job.id not in recovered_by_conn2
        finally:
            conn2_session.close()

    finally:
        conn1_session.rollback()
        conn1_session.close()

    # Now that Connection 1 released its lock, recovery successfully reclaims the job
    recovered_after_release = recover_stale_jobs(db=db, now=now)
    assert job.id in recovered_after_release


def test_heartbeat_renewal_extends_lease_only_for_current_owner(clean_db):
    """Scenario 7: renew_lease extends lease only when ownership token matches and job is PROCESSING."""
    db, create_fn = clean_db
    now = datetime.now(timezone.utc)
    token_a = uuid.uuid4()

    doc, job = create_fn(
        status=JobStatus.PROCESSING,
        doc_status=DocumentStatus.PROCESSING,
        attempts=1,
        lease_token=token_a,
        lease_expires_at=now + timedelta(seconds=10),
    )

    # Valid renewal
    renewed = renew_lease(
        job_id=job.id,
        lease_token=token_a,
        lease_duration=60,
        now=now,
        db=db,
    )
    assert renewed is True
    db.refresh(job)
    assert job.lease_expires_at == now + timedelta(seconds=60)

    # Invalid renewal with mismatched token
    renewed_bad = renew_lease(
        job_id=job.id,
        lease_token=uuid.uuid4(),
        lease_duration=60,
        now=now,
        db=db,
    )
    assert renewed_bad is False
    db.refresh(job)
    assert job.lease_expires_at == now + timedelta(seconds=60)  # Unchanged

    # Invalid renewal when not in PROCESSING
    job.status = JobStatus.COMPLETED
    db.commit()

    renewed_completed = renew_lease(
        job_id=job.id,
        lease_token=token_a,
        lease_duration=60,
        now=now,
        db=db,
    )
    assert renewed_completed is False


def test_job_heartbeat_stops_at_max_execution_time(clean_db):
    """Scenario 7b: JobHeartbeat stops renewing once max_execution_time is reached."""
    import time

    db, create_fn = clean_db
    now = datetime.now(timezone.utc)
    token = uuid.uuid4()

    doc, job = create_fn(
        status=JobStatus.PROCESSING,
        doc_status=DocumentStatus.PROCESSING,
        attempts=1,
        lease_token=token,
        lease_expires_at=now + timedelta(seconds=10),
    )

    # Configure short interval and max_execution_time
    heartbeat = JobHeartbeat(
        job_id=job.id,
        lease_token=token,
        interval=0.05,
        lease_duration=10,
        max_execution_time=0.1,
    )

    with heartbeat:
        time.sleep(0.25)
        # Heartbeat should have detected max_execution_time exceeded and flagged lost_ownership
        assert heartbeat.lost_ownership is True

    # Confirm thread stopped cleanly
    assert not heartbeat._thread.is_alive()


def test_worker_startup_and_periodic_recovery_e2e(clean_db):
    """Scenario 8: Worker startup recovers an expired job and successfully processes it."""
    db, create_fn = clean_db
    now = datetime.now(timezone.utc)
    token = uuid.uuid4()

    # Create a job that expired in PROCESSING from a prior crashed worker
    doc, job = create_fn(
        status=JobStatus.PROCESSING,
        doc_status=DocumentStatus.PROCESSING,
        attempts=1,
        lease_token=token,
        lease_expires_at=now - timedelta(seconds=60),
    )

    # Queue is initially empty
    assert dequeue_job(timeout=1) is None

    # Run worker loop for 1 run:
    # 1. Startup recovery finds expired job, resets to QUEUED, pushes to Redis
    # 2. Worker pops job, claims it, processes it to COMPLETED
    run_worker_loop(poll_timeout=1, max_runs=1)

    db.refresh(job)
    db.refresh(doc)

    assert doc.status == DocumentStatus.COMPLETED
    assert job.status == JobStatus.COMPLETED
    assert job.attempts == 2  # 1 initial + 1 recovered attempt
    assert job.completed_at is not None
    assert job.lease_token is None
    assert job.lease_expires_at is None
