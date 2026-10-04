import os
import uuid
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from fastapi import UploadFile, HTTPException, status
from app.models.document import Document, DocumentStatus
from app.services.file_storage import save_uploaded_file, cleanup_document_file


async def create_document(db: Session, file: UploadFile) -> Document:
    document_id = uuid.uuid4()

    # Step 1: Validate and save file to local filesystem
    storage_path, content_type, file_size = await save_uploaded_file(
        file, document_id
    )

    # Step 2: Create DB model
    doc = Document(
        id=document_id,
        original_filename=file.filename,
        content_type=content_type,
        file_size=file_size,
        storage_path=storage_path,
        status=DocumentStatus.UPLOADED,
    )

    # Step 3: Persist to DB with rollback and file cleanup safety
    try:
        db.add(doc)
        db.commit()
        db.refresh(doc)
        return doc
    except SQLAlchemyError:
        db.rollback()
        # Clean up orphaned storage file if DB save fails
        doc_dir = os.path.dirname(storage_path)
        cleanup_document_file(doc_dir)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database persistence error occurred.",
        )


def get_document_by_id(db: Session, document_id: uuid.UUID) -> Document:
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )
    return doc
