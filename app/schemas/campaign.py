from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class CallbackPayload(BaseModel):
    log_id: int
    status: str
    error_message: Optional[str] = None

class CampaignBase(BaseModel):
    name: str
    subject: Optional[str] = None
    message_template: str
    segment_id: Optional[int] = None

class CampaignCreate(CampaignBase):
    pass

class CampaignResponse(CampaignBase):
    id: int
    status: str
    created_at: datetime

    model_config = {
        "from_attributes": True
    }
