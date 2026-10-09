import uuid
from datetime import datetime
from typing import List, Any
from pydantic import BaseModel, ConfigDict
from app.models.validation_result import ValidationStatus

class ValidationCheckResponse(BaseModel):
    rule_id: str
    status: str
    expected: str
    actual: str
    reason: str

class ValidationResultResponse(BaseModel):
    id: uuid.UUID
    overall_status: ValidationStatus
    policy_id: str
    policy_version: str
    checks: List[ValidationCheckResponse]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
