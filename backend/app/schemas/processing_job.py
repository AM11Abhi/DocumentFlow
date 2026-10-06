import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict
from app.models.processing_job import JobStatus


class ProcessingJobResponse(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    status: JobStatus
    attempts: int
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
