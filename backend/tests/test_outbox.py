import os
import sys
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional
import pytest
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from main import app
from app.config import settings
from app.db.session import SessionLocal
from app.models.document import Document, DocumentStatus
from app.models.processing_job import ProcessingJob, JobStatus
from app.models.outbox import OutboxEvent, OutboxStatus
from app.services.outbox import create_outbox_event, dispatch_pending_outbox_events
from app.services.queue import dequeue_job, enqueue_job, get_redis_client
from app.worker import process_job_by_id, recover_stale_jobs, run_worker_loop

client = TestClient(app)


@pytest.fixture
def outbox_test_db():
    """Provides a fresh database session and ensures test documents and events are deleted at teardown."""
    db = SessionLocal()
    created_doc_ids = []

    def _create_doc_and_job(
        status: JobStatus = JobStatus.QUEUED,
        doc_status: DocumentStatus = DocumentStatus.UPLOADED,
        attempts: int = 0,
        lease_token: Optional[uuid.UUID] = None,
        lease_expires_at: Optional[datetime] = None,
        filename: str = "outbox_test.pdf",
    ) -> tuple[Document, ProcessingJob]:
        doc_id = uuid.uuid4()
        job_id = uuid.uuid4()
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

    yield db, _create_doc_and_job, created_doc_ids

    # Teardown: delete test documents (cascades to processing_jobs and outbox_events)
    for d_id in created_doc_ids:
        doc = db.query(Document).filter(Document.id == d_id).first()
        if doc:
            db.delete(doc)
    db.commit()
    db.close()


def test_atomic_outbox_creation_on_upload(outbox_test_db):
    """Uploading a document creates Document, ProcessingJob, and OutboxEvent atomically."""
    db, _, created_doc_ids = outbox_test_db
    pdf_path = os.path.join("..", "samples", "marksheet", "sample_transcript.pdf")

    with open(pdf_path, "rb") as f:
        response = client.post(
            "/documents",
            files={"file": ("outbox_upload.pdf", f, "application/pdf")},
        )
    assert response.status_code == 201
    doc_id = uuid.UUID(response.json()["id"])
    created_doc_ids.append(doc_id)

    # Verify OutboxEvent exists in PENDING state
    event = (
        db.query(OutboxEvent)
        .filter(OutboxEvent.document_id == doc_id)
        .first()
    )
    assert event is not None
    assert event.event_type == "JOB_QUEUED"
    assert event.status == OutboxStatus.PENDING
    assert event.retry_count == 0
    assert event.published_at is None
    assert event.last_error is None

    # Before dispatch, Redis should NOT have the job
    assert get_redis_client().llen(settings.REDIS_QUEUE_NAME) == 0

    # After dispatch, Redis should have the job and event becomes PUBLISHED
    count = dispatch_pending_outbox_events(db=db)
    assert count >= 1

    db.refresh(event)
    assert event.status == OutboxStatus.PUBLISHED
    assert event.published_at is not None

    queued_item = dequeue_job(timeout=1)
    assert queued_item is not None
    assert queued_item[1] == doc_id


def test_atomic_outbox_creation_on_retry(outbox_test_db):
    """Retrying a FAILED job creates an OutboxEvent in the same transaction."""
    db, create_fn, _ = outbox_test_db
    doc, job = create_fn(
        status=JobStatus.FAILED,
        doc_status=DocumentStatus.FAILED,
        attempts=1,
    )

    response = client.post(f"/documents/{doc.id}/retry")
    assert response.status_code == 200

    # Verify OutboxEvent is created in PENDING status
    event = (
        db.query(OutboxEvent)
        .filter(OutboxEvent.job_id == job.id, OutboxEvent.status == OutboxStatus.PENDING)
        .first()
    )
    assert event is not None
    assert event.document_id == doc.id
    assert event.retry_count == 0

    # Dispatch to Redis
    count = dispatch_pending_outbox_events(db=db)
    assert count >= 1

    item = dequeue_job(timeout=1)
    assert item == (job.id, doc.id)


def test_atomic_outbox_creation_on_crash_recovery(outbox_test_db):
    """Crash recovery transitions expired job to QUEUED and inserts OutboxEvent atomically."""
    db, create_fn, _ = outbox_test_db
    now = datetime.now(timezone.utc)
    token = uuid.uuid4()

    doc, job = create_fn(
        status=JobStatus.PROCESSING,
        doc_status=DocumentStatus.PROCESSING,
        attempts=1,
        lease_token=token,
        lease_expires_at=now - timedelta(seconds=20),
    )

    recovered = recover_stale_jobs(db=db, now=now)
    assert job.id in recovered

    db.refresh(job)
    db.refresh(doc)
    assert job.status == JobStatus.QUEUED
    assert doc.status == DocumentStatus.UPLOADED

    # Verify OutboxEvent exists in PENDING status
    event = (
        db.query(OutboxEvent)
        .filter(OutboxEvent.job_id == job.id, OutboxEvent.status == OutboxStatus.PENDING)
        .first()
    )
    assert event is not None
    assert event.document_id == doc.id

    # Dispatcher publishes to Redis
    count = dispatch_pending_outbox_events(db=db)
    assert count >= 1

    item = dequeue_job(timeout=1)
    assert item == (job.id, doc.id)


def test_transaction_rollback_leaves_no_partial_state(outbox_test_db):
    """If the database transaction rolls back, neither job nor outbox event is persisted."""
    db, _, _ = outbox_test_db
    test_job_id = uuid.uuid4()
    test_doc_id = uuid.uuid4()

    # Emulate transaction rollback
    try:
        create_outbox_event(db, test_job_id, test_doc_id)
        # Force a rollback
        raise SQLAlchemyError("Simulated database failure")
    except SQLAlchemyError:
        db.rollback()

    event = db.query(OutboxEvent).filter(OutboxEvent.job_id == test_job_id).first()
    assert event is None


def test_redis_unavailable_during_upload_and_eventual_dispatch(outbox_test_db, monkeypatch):
    """When Redis is down during upload, outbox event is preserved and dispatched once Redis recovers."""
    db, _, created_doc_ids = outbox_test_db
    pdf_path = os.path.join("..", "samples", "marksheet", "sample_transcript.pdf")

    # Upload succeeds in PostgreSQL regardless of Redis status
    with open(pdf_path, "rb") as f:
        response = client.post(
            "/documents",
            files={"file": ("redis_down_test.pdf", f, "application/pdf")},
        )
    assert response.status_code == 201
    doc_id = uuid.UUID(response.json()["id"])
    created_doc_ids.append(doc_id)

    # Simulate Redis connection failure during dispatch
    def mock_failing_enqueue(job_id, document_id):
        raise ConnectionError("Redis is offline")

    monkeypatch.setattr("app.services.outbox.enqueue_job", mock_failing_enqueue)

    # Dispatcher runs but fails to push to Redis
    dispatched = dispatch_pending_outbox_events(db=db)
    assert dispatched == 0

    event = db.query(OutboxEvent).filter(OutboxEvent.document_id == doc_id).first()
    assert event.status == OutboxStatus.PENDING
    assert event.retry_count == 1
    assert "Redis is offline" in event.last_error
    assert event.next_retry_at is not None

    # Restore Redis connection and advance time past next_retry_at
    monkeypatch.undo()
    future_time = datetime.now(timezone.utc) + timedelta(seconds=10)
    dispatched = dispatch_pending_outbox_events(db=db, now=future_time)
    assert dispatched >= 1

    db.refresh(event)
    assert event.status == OutboxStatus.PUBLISHED
    assert event.last_error is None

    # Job is in Redis
    item = dequeue_job(timeout=1)
    assert item is not None
    assert item[1] == doc_id


def test_crash_after_redis_accepts_message_followed_by_safe_duplicate_delivery(outbox_test_db):
    """Duplicate Redis messages (at-least-once delivery) are handled safely without duplicate processing."""
    db, create_fn, _ = outbox_test_db
    doc, job = create_fn(
        status=JobStatus.QUEUED,
        doc_status=DocumentStatus.UPLOADED,
    )

    # Simulate duplicate Redis pushes for the same job
    enqueue_job(job.id, doc.id)
    enqueue_job(job.id, doc.id)

    # First worker run: claims job and completes processing
    success1 = process_job_by_id(db, job.id, doc.id, enable_heartbeat=False)
    assert success1 is True

    db.refresh(job)
    assert job.status == JobStatus.COMPLETED

    # Second worker pop: receives duplicate message from Redis
    duplicate_item = dequeue_job(timeout=1)
    assert duplicate_item == (job.id, doc.id)

    # Second attempt ignores duplicate message cleanly
    success2 = process_job_by_id(db, job.id, doc.id, enable_heartbeat=False)
    assert success2 is False  # Rejected duplicate message
    db.refresh(job)
    assert job.status == JobStatus.COMPLETED  # State intact


def test_dispatcher_exponential_backoff_and_retry_threshold(outbox_test_db, monkeypatch):
    """Dispatcher applies exponential backoff on failures and logs threshold warnings."""
    db, create_fn, _ = outbox_test_db
    doc, job = create_fn()
    event = create_outbox_event(db, job.id, doc.id)
    db.commit()
    db.refresh(event)

    def failing_enqueue(jid, did):
        raise ConnectionError("Connection refused")

    monkeypatch.setattr("app.services.outbox.enqueue_job", failing_enqueue)

    now = datetime.now(timezone.utc)

    # Attempt 1
    dispatch_pending_outbox_events(db=db, now=now)
    db.refresh(event)
    assert event.retry_count == 1
    assert event.status == OutboxStatus.PENDING
    retry_1_time = event.next_retry_at

    # Attempt before next_retry_at: should be skipped
    dispatch_pending_outbox_events(db=db, now=now)
    db.refresh(event)
    assert event.retry_count == 1  # Not incremented yet

    # Advance time and attempt 2
    dispatch_pending_outbox_events(db=db, now=retry_1_time + timedelta(seconds=1))
    db.refresh(event)
    assert event.retry_count == 2
    retry_2_time = event.next_retry_at
    assert retry_2_time > retry_1_time  # Exponential backoff increased

    # Advance past max retries (5)
    current_time = retry_2_time + timedelta(seconds=1)
    for attempt in range(3, settings.OUTBOX_MAX_RETRIES + 2):
        dispatch_pending_outbox_events(db=db, now=current_time)
        db.refresh(event)
        current_time = event.next_retry_at + timedelta(seconds=1)

    assert event.retry_count >= settings.OUTBOX_MAX_RETRIES
    # Crucially, event is NOT silently deleted; it remains PENDING with capped backoff
    assert event.status == OutboxStatus.PENDING


def test_postgresql_concurrent_dispatchers_skip_locked(outbox_test_db):
    """Two concurrent PostgreSQL sessions lock disjoint batches using SKIP LOCKED."""
    db, create_fn, _ = outbox_test_db

    # Create 4 distinct documents and outbox events
    event_ids = []
    for i in range(4):
        doc, job = create_fn(filename=f"concurrent_outbox_{i}.pdf")
        ev = create_outbox_event(db, job.id, doc.id)
        event_ids.append(ev.id)
    db.commit()

    # Open two distinct database sessions
    session_a = SessionLocal()
    session_b = SessionLocal()

    try:
        now = datetime.now(timezone.utc)
        # Session A locks 2 rows with SKIP LOCKED
        batch_a = (
            session_a.query(OutboxEvent)
            .filter(OutboxEvent.status == OutboxStatus.PENDING)
            .order_by(OutboxEvent.created_at.asc())
            .limit(2)
            .with_for_update(skip_locked=True)
            .all()
        )
        assert len(batch_a) == 2
        batch_a_ids = {e.id for e in batch_a}

        # Session B concurrently queries with SKIP LOCKED: must skip Session A's locked rows
        batch_b = (
            session_b.query(OutboxEvent)
            .filter(OutboxEvent.status == OutboxStatus.PENDING)
            .order_by(OutboxEvent.created_at.asc())
            .limit(2)
            .with_for_update(skip_locked=True)
            .all()
        )
        assert len(batch_b) == 2
        batch_b_ids = {e.id for e in batch_b}

        # Sets of locked IDs must be completely disjoint
        assert batch_a_ids.isdisjoint(batch_b_ids)

        session_a.commit()
        session_b.commit()
    finally:
        session_a.close()
        session_b.close()


def test_dispatcher_failures_do_not_terminate_worker_loop(monkeypatch):
    """Unexpected exceptions during outbox dispatch do not crash the worker loop."""
    def broken_dispatch(*args, **kwargs):
        raise RuntimeError("Simulated unexpected dispatcher crash")

    monkeypatch.setattr("app.worker.dispatch_pending_outbox_events", broken_dispatch)

    # Worker loop runs for 2 iterations without raising unhandled exception
    run_worker_loop(poll_timeout=0.01, max_runs=2, enable_heartbeat=False)
