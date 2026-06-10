from pydantic import BaseModel
from datetime import datetime
from decimal import Decimal

class OrderBase(BaseModel):
    customer_id: int
    amount: Decimal
    status: str = "pending"

class OrderCreate(OrderBase):
    pass

class OrderResponse(OrderBase):
    id: int
    created_at: datetime

    model_config = {
        "from_attributes": True
    }
