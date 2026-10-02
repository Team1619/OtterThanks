from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class KudosCreate(BaseModel):
    recipient_type: str = Field(..., description="'individual' or 'team'")
    recipient_name: Optional[str] = None
    message: str = Field(..., min_length=2, max_length=2500)
    sender_name: Optional[str] = Field("Anonymous", max_length=100)


class KudosResponse(BaseModel):
    id: int
    recipient_type: str
    recipient_name: Optional[str] = None
    message: str
    sender_name: str
    slack_status: str
    slack_sent_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class KudosStatusUpdate(BaseModel):
    slack_status: str = Field(
        ..., pattern="^(pending|sent|failed|rejected)$", description="New status for the Slack post"
    )
    slack_sent_at: Optional[datetime] = None


class HealthResponse(BaseModel):
    status: str
    database: str
    timestamp: datetime
