import uuid
from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.schemas.document import DocumentResponse
from app.services.document_service import create_document, get_document_by_id

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
    """Uploads a document (PDF, JPEG, PNG <= 10MB), validates content type and magic bytes,

    stores the file on disk, and persists metadata in PostgreSQL.
    """
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
    """Retrieves document metadata by document_id."""
    return get_document_by_id(db, document_id)
