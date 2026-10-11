import uuid
from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.schemas.document import DocumentResponse, DocumentListResponse
from app.services.document_service import (
    create_document,
    get_document_by_id,
    list_documents,
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
    "",
    response_model=DocumentListResponse,
    status_code=status.HTTP_200_OK,
    summary="List documents",
)
def list_all_documents(
    limit: int = Query(default=20, ge=1, le=100, description="Number of documents to return"),
    offset: int = Query(default=0, ge=0, description="Number of documents to skip"),
    db: Session = Depends(get_db),
):
    """Retrieves a paginated list of documents ordered by created_at DESC."""
    return list_documents(db=db, limit=limit, offset=offset)



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
