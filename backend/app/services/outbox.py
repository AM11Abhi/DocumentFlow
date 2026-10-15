import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List
from sqlalchemy import or_
from sqlalchemy.orm import Session
from app.config import settings
from app.db.session import SessionLocal
from app.models.outbox import OutboxEvent, OutboxStatus
from app.services.queue import enqueue_job

logger = logging.getLogger("documentflow.outbox")


def create_outbox_event(
    db: Session,
    job_id: uuid.UUID,
    document_id: uuid.UUID,
    event_type: str = "JOB_QUEUED",
    payload: Optional[dict] = None,
) -> OutboxEvent:
    """Creates a new OutboxEvent in PENDING status within the caller's active database transaction.

    Does NOT commit the session; the caller is responsible for committing or rolling back
    atomically with associated entity state changes.
    """
    event = OutboxEvent(
        id=uuid.uuid4(),
        event_type=event_type,
        job_id=job_id,
        document_id=document_id,
        payload=payload,
        status=OutboxStatus.PENDING,
        retry_count=0,
        last_error=None,
    )
    db.add(event)
    return event


def dispatch_pending_outbox_events(
    db: Optional[Session] = None,
    batch_size: Optional[int] = None,
    now: Optional[datetime] = None,
) -> int:
    """Selects eligible PENDING outbox events in bounded batches and publishes them to Redis.

    Uses PostgreSQL row locking with SKIP LOCKED for safe concurrent dispatch across
    multiple worker instances without lock contention or duplicate publishing.

    Transaction boundary:
    Row locks are acquired via `with_for_update(skip_locked=True)` on a bounded batch.
    Individual Redis enqueue operations are executed per event. Any Redis transport errors
    are caught per event so that one failure does not prevent other valid events in the batch
    from being processed. The session is committed immediately following the batch, releasing
    all row locks promptly.

    Returns the count of successfully published events in this sweep.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    if batch_size is None:
        batch_size = settings.OUTBOX_BATCH_SIZE

    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True

    dispatched_count = 0
    try:
        # Select pending events eligible for dispatch (next_retry_at is None or in the past)
        events: List[OutboxEvent] = (
            db.query(OutboxEvent)
            .filter(
                OutboxEvent.status == OutboxStatus.PENDING,
                or_(
                    OutboxEvent.next_retry_at.is_(None),
                    OutboxEvent.next_retry_at <= now,
                ),
            )
            .order_by(OutboxEvent.created_at.asc())
            .limit(batch_size)
            .with_for_update(skip_locked=True)
            .all()
        )

        if not events:
            return 0

        for event in events:
            try:
                # Attempt publish to Redis queue
                enqueue_job(event.job_id, event.document_id)
                event.status = OutboxStatus.PUBLISHED
                event.published_at = datetime.now(timezone.utc)
                event.last_error = None
                dispatched_count += 1
            except Exception as exc:
                event.retry_count += 1
                event.last_error = str(exc)
                backoff_seconds = min(
                    settings.OUTBOX_BASE_BACKOFF_SECONDS * (2 ** (event.retry_count - 1)),
                    settings.OUTBOX_MAX_BACKOFF_SECONDS,
                )
                event.next_retry_at = datetime.now(timezone.utc) + timedelta(
                    seconds=backoff_seconds
                )

                if event.retry_count >= settings.OUTBOX_MAX_RETRIES:
                    logger.warning(
                        f"OutboxEvent {event.id} for Job {event.job_id} exceeded retry threshold "
                        f"({event.retry_count}/{settings.OUTBOX_MAX_RETRIES}). "
                        f"Last error: {event.last_error}. Event remains PENDING with capped backoff."
                    )
                else:
                    logger.info(
                        f"OutboxEvent {event.id} publish attempt {event.retry_count} failed: {event.last_error}. "
                        f"Retrying in {backoff_seconds:.1f}s."
                    )

        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error(f"Unexpected error during outbox dispatch sweep: {exc}")
    finally:
        if should_close:
            db.close()

    return dispatched_count
