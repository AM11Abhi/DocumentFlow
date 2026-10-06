import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.document import Document, DocumentStatus
from app.models.processing_job import ProcessingJob, JobStatus
from app.services.queue import dequeue_job

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("documentflow.worker")

MAX_ATTEMPTS = 3


def process_job_by_id(
    db: Session,
    job_id: uuid.UUID,
    document_id: uuid.UUID,
    force_fail: bool = False,
) -> bool:
    """Processes a single job attempt with explicit DB state transitions and error handling."""
    job = (
        db.query(ProcessingJob)
        .filter(ProcessingJob.id == job_id)
        .first()
    )
    doc = db.query(Document).filter(Document.id == document_id).first()

    if not job or not doc:
        logger.error(
            f"Job {job_id} or Document {document_id} not found in database. Skipping."
        )
        return False

    # Check max attempts limit
    if job.attempts >= MAX_ATTEMPTS:
        logger.warning(
            f"Job {job_id} has reached maximum allowed attempts ({job.attempts}/{MAX_ATTEMPTS}). Permanently FAILED."
        )
        job.status = JobStatus.FAILED
        doc.status = DocumentStatus.FAILED
        db.commit()
        return False

    # Step 1: Mark job and document as PROCESSING and increment attempts
    job.status = JobStatus.PROCESSING
    job.attempts += 1
    if not job.started_at:
        job.started_at = datetime.now(timezone.utc)
    doc.status = DocumentStatus.PROCESSING
    db.commit()

    logger.info(
        f"Processing attempt {job.attempts}/{MAX_ATTEMPTS} for Document {document_id} (Job {job_id})"
    )

    # Step 2: Execute simulated processing
    try:
        # Check if file name contains 'fail' or force_fail flag is set to simulate failure
        if force_fail or "fail" in doc.original_filename.lower():
            raise ValueError(
                f"Simulated processing error for file: {doc.original_filename}"
            )

        # Simulate small delay for processing
        time.sleep(0.5)

        # Step 3: Success transition
        job.status = JobStatus.COMPLETED
        job.completed_at = datetime.now(timezone.utc)
        job.error = None
        doc.status = DocumentStatus.COMPLETED
        db.commit()
        logger.info(
            f"Successfully processed Document {document_id} (Job {job_id})"
        )
        return True

    except Exception as exc:
        db.rollback()

        # Step 4: Failure transition
        error_msg = str(exc)
        logger.error(
            f"Attempt {job.attempts}/{MAX_ATTEMPTS} failed for Document {document_id}: {error_msg}"
        )

        job.status = JobStatus.FAILED
        job.completed_at = datetime.now(timezone.utc)
        job.error = error_msg
        doc.status = DocumentStatus.FAILED
        db.commit()
        return False


def run_worker_loop(poll_timeout: int = 2, max_runs: Optional[int] = None):
    """Main worker loop popping jobs from Redis queue and executing them."""
    logger.info("Starting DocumentFlow background worker...")
    runs = 0

    while True:
        if max_runs is not None and runs >= max_runs:
            logger.info("Worker reached max_runs limit. Shutting down.")
            break

        try:
            job_item = dequeue_job(timeout=poll_timeout)
            if not job_item:
                if max_runs is not None:
                    runs += 1
                continue

            job_id, document_id = job_item
            db = SessionLocal()
            try:
                process_job_by_id(db, job_id, document_id)
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
