from fastapi import APIRouter
from app.api.v1 import customers, orders, segments, campaigns, emails

api_router = APIRouter()

api_router.include_router(customers.router, prefix="/customers", tags=["customers"])
api_router.include_router(orders.router, prefix="/orders", tags=["orders"])
api_router.include_router(segments.router, prefix="/segments", tags=["segments"])
api_router.include_router(campaigns.router, prefix="/campaigns", tags=["campaigns"])
api_router.include_router(emails.router, prefix="/emails", tags=["emails"])

