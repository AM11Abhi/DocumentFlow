import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict
from app.models.document import DocumentStatus
from app.schemas.processing_job import ProcessingJobResponse
from app.schemas.processing_result import ProcessingResultResponse


class DocumentResponse(BaseModel):
    id: uuid.UUID
    original_filename: str
    content_type: str
    file_size: int
    status: DocumentStatus
    created_at: datetime
    processing_job: Optional[ProcessingJobResponse] = None
    processing_result: Optional[ProcessingResultResponse] = None

    model_config = ConfigDict(from_attributes=True)
