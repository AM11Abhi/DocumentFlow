import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from app.models.document import DocumentStatus


class DocumentResponse(BaseModel):
    id: uuid.UUID
    original_filename: str
    content_type: str
    file_size: int
    status: DocumentStatus
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
