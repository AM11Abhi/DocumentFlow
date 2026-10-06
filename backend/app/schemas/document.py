import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict
from app.models.document import DocumentStatus
from app.schemas.processing_job import ProcessingJobResponse


class DocumentResponse(BaseModel):
    id: uuid.UUID
    original_filename: str
    content_type: str
    file_size: int
    status: DocumentStatus
    created_at: datetime
    processing_job: Optional[ProcessingJobResponse] = None

    model_config = ConfigDict(from_attributes=True)
