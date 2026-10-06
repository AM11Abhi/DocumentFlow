import uuid
from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.schemas.document import DocumentResponse
from app.services.document_service import (
    create_document,
    get_document_by_id,
    retry_document_job,
)

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post(
    "",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a document",
)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Uploads a document, creates a ProcessingJob (QUEUED), and enqueues it to Redis."""
    return await create_document(db, file)


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    status_code=status.HTTP_200_OK,
    summary="Get document metadata by ID",
)
def read_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """Retrieves document metadata and its associated processing job status."""
    return get_document_by_id(db, document_id)


@router.post(
    "/{document_id}/retry",
    response_model=DocumentResponse,
    status_code=status.HTTP_200_OK,
    summary="Retry a failed processing job",
)
def retry_job(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """Re-queues a failed processing job if attempts < 3."""
    return retry_document_job(db, document_id)
