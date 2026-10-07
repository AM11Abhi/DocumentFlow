import uuid
from datetime import datetime
from typing import Optional, Any, Dict
from pydantic import BaseModel, ConfigDict

class ProcessingResultResponse(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    document_type: str
    detection_score: Optional[int] = None
    matched_signals: Optional[list[str]] = None
    extracted_text: Optional[str] = None
    extracted_data: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
