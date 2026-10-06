import os
import uuid
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from fastapi import UploadFile, HTTPException, status
from app.models.document import Document, DocumentStatus
from app.models.processing_job import ProcessingJob, JobStatus
from app.services.file_storage import save_uploaded_file, cleanup_document_file
from app.services.queue import enqueue_job


async def create_document(db: Session, file: UploadFile) -> Document:
    document_id = uuid.uuid4()
    job_id = uuid.uuid4()

    # Step 1: Validate and save file to local filesystem
    storage_path, content_type, file_size = await save_uploaded_file(
        file, document_id
    )

    # Step 2: Create DB models (Document & ProcessingJob)
    doc = Document(
        id=document_id,
        original_filename=file.filename,
        content_type=content_type,
        file_size=file_size,
        storage_path=storage_path,
        status=DocumentStatus.UPLOADED,
    )

    job = ProcessingJob(
        id=job_id,
        document_id=document_id,
        status=JobStatus.QUEUED,
        attempts=0,
    )

    # Step 3: Persist models to DB with rollback safety
    try:
        db.add(doc)
        db.add(job)
        db.commit()
        db.refresh(doc)
    except SQLAlchemyError as exc:
        db.rollback()
        doc_dir = os.path.dirname(storage_path)
        cleanup_document_file(doc_dir)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database persistence error occurred.",
        )

    # Step 4: Enqueue processing job payload to Redis
    enqueue_job(job.id, doc.id)

    return doc


def get_document_by_id(db: Session, document_id: uuid.UUID) -> Document:
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )
    return doc


def retry_document_job(db: Session, document_id: uuid.UUID) -> Document:
    doc = get_document_by_id(db, document_id)
    job = doc.processing_job

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Processing job not found for document.",
        )

    if job.attempts >= 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum processing attempts reached (3/3). Job cannot be retried.",
        )

    if job.status not in (JobStatus.FAILED, JobStatus.QUEUED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot retry job in status '{job.status}'. Only FAILED jobs can be retried.",
        )

    # Re-queue the job
    job.status = JobStatus.QUEUED
    job.error = None
    doc.status = DocumentStatus.PROCESSING
    db.commit()
    db.refresh(doc)

    enqueue_job(job.id, doc.id)
    return doc
