import os
import shutil
import uuid
from typing import Tuple
from fastapi import UploadFile, HTTPException, status
from app.config import settings

ALLOWED_MIME_TYPES = {
    "application/pdf": "pdf",
    "image/jpeg": "jpg",
    "image/png": "png",
}

# Magic byte signatures
# PDF: %PDF-
# JPEG: \xff\xd8\xff
# PNG: \x89PNG\r\n\x1a\n
MAGIC_SIGNATURES = [
    (b"%PDF-", "application/pdf", "pdf"),
    (b"\xff\xd8\xff", "image/jpeg", "jpg"),
    (b"\x89PNG\r\n\x1a\n", "image/png", "png"),
]


def detect_file_type(header_bytes: bytes) -> Tuple[str, str]:
    """Inspect magic bytes to reliably determine MIME type and extension."""
    for signature, mime_type, ext in MAGIC_SIGNATURES:
        if header_bytes.startswith(signature):
            return mime_type, ext
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Unsupported file type. Only PDF, JPEG, and PNG files are allowed.",
    )


async def save_uploaded_file(
    file: UploadFile, document_id: uuid.UUID
) -> Tuple[str, str, int]:
    """Validates file magic bytes and size, then saves file under uploads/<document_id>/original.<ext>.

    Returns: (storage_path, validated_content_type, file_size)
    """
    if not file or not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file provided in upload request.",
        )

    # Read initial chunk for magic bytes inspection
    header_bytes = await file.read(1024)
    if not header_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    # Validate file type using magic bytes
    content_type, extension = detect_file_type(header_bytes)

    # Prepare storage path
    doc_dir = os.path.join(settings.UPLOAD_DIR, str(document_id))
    os.makedirs(doc_dir, exist_ok=True)
    file_name = f"original.{extension}"
    file_path = os.path.join(doc_dir, file_name)

    total_size = len(header_bytes)

    try:
        with open(file_path, "wb") as out_file:
            out_file.write(header_bytes)

            chunk_size = 64 * 1024  # 64 KB chunks
            while True:
                chunk = await file.read(chunk_size)
                if not chunk:
                    break
                total_size += len(chunk)
                if total_size > settings.MAX_FILE_SIZE_BYTES:
                    out_file.close()
                    cleanup_document_file(doc_dir)
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"File exceeds maximum size limit of {settings.MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB.",
                    )
                out_file.write(chunk)
    except HTTPException:
        raise
    except Exception as exc:
        cleanup_document_file(doc_dir)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="File storage error occurred while saving upload.",
        )

    # Normalize storage path using forward slashes for portability
    normalized_storage_path = file_path.replace("\\", "/")
    return normalized_storage_path, content_type, total_size


def cleanup_document_file(doc_dir: str):
    """Safely remove document directory and files if database save fails or during error rollback."""
    try:
        if os.path.exists(doc_dir):
            shutil.rmtree(doc_dir)
    except Exception:
        pass
