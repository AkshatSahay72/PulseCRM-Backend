from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Dict, Any

class SegmentBase(BaseModel):
    name: str
    description: Optional[str] = None
    rules: Dict[str, Any]

class SegmentCreate(SegmentBase):
    pass

class SegmentResponse(SegmentBase):
    id: int
    created_at: datetime

    model_config = {
        "from_attributes": True
    }
