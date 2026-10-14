import logging
import threading
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy import or_
from sqlalchemy.orm import Session
from app.config import settings
from app.db.session import SessionLocal
from app.models.document import Document, DocumentStatus
from app.models.processing_job import ProcessingJob, JobStatus
from app.services.queue import dequeue_job, enqueue_job

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("documentflow.worker")

MAX_ATTEMPTS = 3


def renew_lease(
    job_id: uuid.UUID,
    lease_token: uuid.UUID,
    lease_duration: Optional[int] = None,
    now: Optional[datetime] = None,
    db: Optional[Session] = None,
) -> bool:
    """Renews a job's lease_expires_at timestamp if it is currently PROCESSING

    and its lease_token matches. Returns True if successfully renewed, False otherwise.
    """
    if lease_duration is None:
        lease_duration = settings.WORKER_LEASE_DURATION_SECONDS
    if now is None:
        now = datetime.now(timezone.utc)

    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True

    try:
        new_expiry = now + timedelta(seconds=lease_duration)
        rows_updated = (
            db.query(ProcessingJob)
            .filter(
                ProcessingJob.id == job_id,
                ProcessingJob.lease_token == lease_token,
                ProcessingJob.status == JobStatus.PROCESSING,
            )
            .update(
                {"lease_expires_at": new_expiry},
                synchronize_session=False,
            )
        )
        db.commit()
        return rows_updated > 0
    except Exception as exc:
        db.rollback()
        logger.error(f"Error renewing lease for Job {job_id}: {exc}")
        return False
    finally:
        if should_close:
            db.close()


class JobHeartbeat:
    """Background heartbeat manager that periodically extends a job's lease

    while processing is active. Stops when processing finishes, max execution time
    is reached, or ownership is lost.
    """

    def __init__(
        self,
        job_id: uuid.UUID,
        lease_token: uuid.UUID,
        interval: Optional[float] = None,
        lease_duration: Optional[int] = None,
        max_execution_time: Optional[int] = None,
    ):
        self.job_id = job_id
        self.lease_token = lease_token
        self.interval = (
            interval
            if interval is not None
            else settings.WORKER_HEARTBEAT_INTERVAL_SECONDS
        )
        self.lease_duration = (
            lease_duration
            if lease_duration is not None
            else settings.WORKER_LEASE_DURATION_SECONDS
        )
        self.max_execution_time = (
            max_execution_time
            if max_execution_time is not None
            else settings.WORKER_MAX_EXECUTION_TIME_SECONDS
        )
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.lost_ownership = False
        self.start_time = 0.0

    def start(self):
        self.start_time = time.monotonic()
        self._thread = threading.Thread(
            target=self._run,
            name=f"heartbeat-{self.job_id}",
            daemon=True,
        )
        self._thread.start()

    def _run(self):
        while not self._stop_event.wait(timeout=self.interval):
            elapsed = time.monotonic() - self.start_time
            if elapsed >= self.max_execution_time:
                logger.warning(
                    f"Job {self.job_id} exceeded maximum execution time "
                    f"({elapsed:.1f}s >= {self.max_execution_time}s). Stopping heartbeat."
                )
                self.lost_ownership = True
                break

            renewed = renew_lease(
                job_id=self.job_id,
                lease_token=self.lease_token,
                lease_duration=self.lease_duration,
            )
            if not renewed:
                logger.warning(
                    f"Heartbeat renewal failed for Job {self.job_id}. "
                    f"Ownership token mismatch or job no longer PROCESSING. Stopping heartbeat."
                )
                self.lost_ownership = True
                break

    def stop(self):
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()


def recover_stale_jobs(
    db: Optional[Session] = None,
    now: Optional[datetime] = None,
) -> list[uuid.UUID]:
    """Scans for PROCESSING jobs whose lease has expired or is missing.

    Re-queues jobs if attempts < MAX_ATTEMPTS; marks them FAILED if attempts >= MAX_ATTEMPTS.
    Safe for concurrent execution across multiple workers via row locking (SKIP LOCKED).
    Returns list of recovered job IDs.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True

    recovered_ids = []
    try:
        # Find candidate IDs whose lease has expired or that have been in PROCESSING without lease
        stale_filter = or_(
            ProcessingJob.lease_expires_at < now,
            (ProcessingJob.lease_expires_at.is_(None))
            & (
                ProcessingJob.started_at
                < now - timedelta(seconds=settings.WORKER_LEASE_DURATION_SECONDS)
            ),
        )

        candidate_ids = [
            row[0]
            for row in db.query(ProcessingJob.id)
            .filter(
                ProcessingJob.status == JobStatus.PROCESSING,
                stale_filter,
            )
            .all()
        ]

        for jid in candidate_ids:
            job = (
                db.query(ProcessingJob)
                .filter(
                    ProcessingJob.id == jid,
                    ProcessingJob.status == JobStatus.PROCESSING,
                    stale_filter,
                )
                .with_for_update(skip_locked=True)
                .first()
            )
            if not job:
                continue

            doc = (
                db.query(Document)
                .filter(Document.id == job.document_id)
                .with_for_update()
                .first()
            )

            if job.attempts >= MAX_ATTEMPTS:
                logger.warning(
                    f"Recovering expired Job {job.id}: reached max attempts ({job.attempts}/{MAX_ATTEMPTS}). "
                    f"Marking as FAILED."
                )
                job.status = JobStatus.FAILED
                job.completed_at = now
                job.lease_token = None
                job.lease_expires_at = None
                job.error = (
                    f"Worker lease expired and maximum processing attempts reached ({job.attempts}/{MAX_ATTEMPTS}). "
                    f"Worker may have crashed or become unresponsive."
                )
                if doc:
                    doc.status = DocumentStatus.FAILED
                db.commit()
            else:
                logger.info(
                    f"Recovering expired Job {job.id} (attempt {job.attempts}/{MAX_ATTEMPTS}). "
                    f"Resetting to QUEUED and re-enqueueing."
                )
                job.status = JobStatus.QUEUED
                job.lease_token = None
                job.lease_expires_at = None
                job.error = (
                    f"Worker lease expired on attempt {job.attempts}/{MAX_ATTEMPTS}. "
                    f"Automatically recovered and re-queued."
                )
                if doc:
                    doc.status = DocumentStatus.UPLOADED
                db.commit()

                # Re-enqueue to Redis queue
                enqueue_job(job.id, job.document_id)

            recovered_ids.append(job.id)

    except Exception as exc:
        db.rollback()
        logger.error(f"Error during stale job recovery sweep: {exc}")
    finally:
        if should_close:
            db.close()

    return recovered_ids


def process_job_by_id(
    db: Session,
    job_id: uuid.UUID,
    document_id: uuid.UUID,
    force_fail: bool = False,
    enable_heartbeat: bool = True,
) -> bool:
    """Processes a single job attempt with atomic claiming, lease ownership, and error handling."""
    # Step 1: Atomically lock and claim the job
    job = (
        db.query(ProcessingJob)
        .filter(ProcessingJob.id == job_id)
        .with_for_update()
        .first()
    )
    doc = db.query(Document).filter(Document.id == document_id).first()

    if not job or not doc:
        logger.error(
            f"Job {job_id} or Document {document_id} not found in database. Skipping."
        )
        return False

    # Reject stale, duplicate, or invalid queue messages when job is already PROCESSING or COMPLETED
    if job.status in (JobStatus.PROCESSING, JobStatus.COMPLETED):
        logger.warning(
            f"Ignoring duplicate/stale queue message for Job {job_id}: status is already '{job.status}'."
        )
        return False

    if job.status == JobStatus.FAILED:
        logger.warning(
            f"Ignoring queue message for Job {job_id}: status is already 'FAILED'."
        )
        return False

    # Check max attempts limit
    if job.attempts >= MAX_ATTEMPTS:
        logger.warning(
            f"Job {job_id} has reached maximum allowed attempts ({job.attempts}/{MAX_ATTEMPTS}). Permanently FAILED."
        )
        job.status = JobStatus.FAILED
        doc.status = DocumentStatus.FAILED
        job.lease_token = None
        job.lease_expires_at = None
        db.commit()
        return False

    # Claim the job with a unique ownership token and lease duration
    lease_token = uuid.uuid4()
    claim_time = datetime.now(timezone.utc)
    lease_expires_at = claim_time + timedelta(seconds=settings.WORKER_LEASE_DURATION_SECONDS)

    job.status = JobStatus.PROCESSING
    job.attempts += 1
    job.started_at = claim_time
    job.lease_token = lease_token
    job.lease_expires_at = lease_expires_at
    job.error = None
    doc.status = DocumentStatus.PROCESSING
    db.commit()

    logger.info(
        f"Claimed attempt {job.attempts}/{MAX_ATTEMPTS} for Document {document_id} (Job {job_id}) "
        f"with lease token {lease_token}"
    )

    # Step 2: Start heartbeat (if enabled) and execute processing
    heartbeat = None
    if enable_heartbeat:
        heartbeat = JobHeartbeat(job_id=job_id, lease_token=lease_token)
        heartbeat.start()

    try:
        from app.services.processors.pipeline import process_document
        from app.models.processing_result import ProcessingResult

        # Check if file name contains 'fail' or force_fail flag is set to simulate failure
        if force_fail or "fail" in doc.original_filename.lower():
            raise ValueError(
                f"Simulated processing error for file: {doc.original_filename}"
            )

        # Process the document using the pipeline
        result_data = process_document(doc.storage_path)

        from app.services.validators.engine import validate_document
        from app.models.validation_result import ValidationResult

        validation_data = validate_document(
            result_data["document_type"], result_data["extracted_data"]
        )

        # Check if heartbeat detected lost ownership during processing
        if heartbeat and heartbeat.lost_ownership:
            logger.warning(
                f"Heartbeat signaled lost ownership for Job {job_id}. "
                f"Rolling back and aborting result commit."
            )
            db.rollback()
            return False

        # Step 3: Verify ownership atomically before writing results and marking COMPLETED
        now = datetime.now(timezone.utc)
        locked_job = (
            db.query(ProcessingJob)
            .filter(
                ProcessingJob.id == job_id,
                ProcessingJob.lease_token == lease_token,
                ProcessingJob.status == JobStatus.PROCESSING,
            )
            .with_for_update()
            .first()
        )

        if not locked_job or (
            locked_job.lease_expires_at is not None
            and locked_job.lease_expires_at < now
        ):
            logger.warning(
                f"Worker lost ownership or lease expired for Job {job_id} (token {lease_token}). "
                f"Rolling back and aborting commit."
            )
            db.rollback()
            return False

        # Delete existing result if this is a retry
        existing_result = (
            db.query(ProcessingResult)
            .filter(ProcessingResult.document_id == document_id)
            .first()
        )
        if existing_result:
            db.delete(existing_result)
            db.flush()

        # Create and store processing result
        new_result = ProcessingResult(
            document_id=document_id,
            document_type=result_data["document_type"],
            detection_score=result_data["detection_score"],
            matched_signals=result_data["matched_signals"],
            extracted_text=result_data["extracted_text"],
            extracted_data=result_data["extracted_data"],
        )
        db.add(new_result)
        db.flush()

        new_validation = ValidationResult(
            processing_result_id=new_result.id,
            overall_status=validation_data["overall_status"],
            checks=validation_data["checks"],
            policy_id=validation_data["policy_id"],
            policy_version=validation_data["policy_version"],
        )
        db.add(new_validation)

        # Success transition
        locked_job.status = JobStatus.COMPLETED
        locked_job.completed_at = datetime.now(timezone.utc)
        locked_job.lease_token = None
        locked_job.lease_expires_at = None
        locked_job.error = None

        doc = db.query(Document).filter(Document.id == document_id).first()
        if doc:
            doc.status = DocumentStatus.COMPLETED

        db.commit()
        logger.info(
            f"Successfully processed Document {document_id} (Job {job_id})"
        )
        return True

    except Exception as exc:
        db.rollback()
        error_msg = str(exc)
        logger.error(
            f"Attempt failed for Document {document_id} (Job {job_id}): {error_msg}"
        )

        # Verify that this worker still owns the job before recording failure
        try:
            now = datetime.now(timezone.utc)
            locked_job = (
                db.query(ProcessingJob)
                .filter(
                    ProcessingJob.id == job_id,
                    ProcessingJob.lease_token == lease_token,
                    ProcessingJob.status == JobStatus.PROCESSING,
                )
                .with_for_update()
                .first()
            )
            if locked_job and (
                locked_job.lease_expires_at is None
                or locked_job.lease_expires_at >= now
            ):
                locked_job.status = JobStatus.FAILED
                locked_job.completed_at = now
                locked_job.lease_token = None
                locked_job.lease_expires_at = None
                locked_job.error = error_msg

                doc = db.query(Document).filter(Document.id == document_id).first()
                if doc:
                    doc.status = DocumentStatus.FAILED
                db.commit()
            else:
                logger.warning(
                    f"Worker lost ownership for Job {job_id} before recording failure. "
                    f"Suppressing failure transition from stale worker."
                )
        except Exception as commit_exc:
            db.rollback()
            logger.error(f"Failed to record failure for Job {job_id}: {commit_exc}")

        return False
    finally:
        if heartbeat:
            heartbeat.stop()


def run_worker_loop(
    poll_timeout: int = 2,
    max_runs: Optional[int] = None,
    enable_heartbeat: bool = True,
):
    """Main worker loop popping jobs from Redis queue and executing them.

    Runs startup recovery sweep and periodic recovery sweeps.
    """
    logger.info("Starting DocumentFlow background worker...")

    # Startup recovery sweep
    logger.info("Running worker startup crash recovery sweep...")
    recover_stale_jobs()

    runs = 0
    last_recovery_mono = time.monotonic()

    while True:
        if max_runs is not None and runs >= max_runs:
            logger.info("Worker reached max_runs limit. Shutting down.")
            break

        # Periodic recovery sweep check
        now_mono = time.monotonic()
        if now_mono - last_recovery_mono >= settings.WORKER_RECOVERY_INTERVAL_SECONDS:
            recover_stale_jobs()
            last_recovery_mono = now_mono

        try:
            job_item = dequeue_job(timeout=poll_timeout)
            if not job_item:
                if max_runs is not None:
                    runs += 1
                continue

            job_id, document_id = job_item
            db = SessionLocal()
            try:
                process_job_by_id(
                    db, job_id, document_id, enable_heartbeat=enable_heartbeat
                )
            finally:
                db.close()

            runs += 1

        except KeyboardInterrupt:
            logger.info("Worker interrupted by user. Exiting.")
            break
        except Exception as exc:
            logger.error(f"Unexpected worker error: {exc}")
            time.sleep(1)


if __name__ == "__main__":
    run_worker_loop()
