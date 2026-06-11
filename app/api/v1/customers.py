from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.api.deps import get_db
from app.models.customer import Customer
from app.schemas.customer import CustomerCreate, CustomerResponse

router = APIRouter()

@router.post("/", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
def create_customer(customer_in: CustomerCreate, db: Session = Depends(get_db)):
    db_customer = db.query(Customer).filter(Customer.email == customer_in.email).first()
    if db_customer:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    db_customer = Customer(
        first_name=customer_in.first_name,
        last_name=customer_in.last_name,
        email=customer_in.email,
        phone=customer_in.phone
    )
    db.add(db_customer)
    db.commit()
    db.refresh(db_customer)
    return db_customer


@router.get("/", response_model=List[CustomerResponse])
def list_customers(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(Customer).offset(skip).limit(limit).all()


@router.get("/{customer_id}", response_model=CustomerResponse)
def get_customer(customer_id: int, db: Session = Depends(get_db)):
    db_customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not db_customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found"
        )
    return db_customer


@router.get("/{customer_id}/profile")
def get_customer_profile(customer_id: int, db: Session = Depends(get_db)):
    from app.models.order import Order
    from app.models.campaign import CommunicationLog, CampaignEvent
    
    db_customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not db_customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found"
        )
        
    # LTV: sum of completed orders
    completed_orders = [o for o in db_customer.orders if o.status == "completed"]
    ltv = sum(o.amount for o in completed_orders)
    
    # Lifecycle stage
    order_count = len(completed_orders)
    if order_count == 0:
        lifecycle_stage = "Lead"
    elif order_count <= 2:
        lifecycle_stage = "Active Customer"
    else:
        lifecycle_stage = "Loyal Customer"
        
    # Order history
    orders_list = [{
        "id": o.id,
        "amount": float(o.amount),
        "status": o.status,
        "created_at": o.created_at
    } for o in sorted(db_customer.orders, key=lambda x: x.created_at, reverse=True)]
    
    # Campaign outbound history
    campaign_history = []
    for log in sorted(db_customer.communication_logs, key=lambda x: x.created_at, reverse=True):
        events_list = [{
            "event_type": e.event_type,
            "timestamp": e.timestamp
        } for e in sorted(log.events, key=lambda x: x.timestamp)]
        
        campaign_history.append({
            "log_id": log.id,
            "campaign_id": log.campaign_id,
            "campaign_name": log.campaign.name,
            "campaign_subject": log.campaign.subject,
            "status": log.status,
            "sent_at": log.sent_at or log.created_at,
            "error_message": log.error_message,
            "events": events_list
        })
        
    return {
        "customer": {
            "id": db_customer.id,
            "first_name": db_customer.first_name,
            "last_name": db_customer.last_name,
            "email": db_customer.email,
            "phone": db_customer.phone,
            "created_at": db_customer.created_at
        },
        "ltv": float(ltv),
        "lifecycle_stage": lifecycle_stage,
        "orders": orders_list,
        "campaign_history": campaign_history
    }


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_customer(customer_id: int, db: Session = Depends(get_db)):
    db_customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not db_customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found"
        )
    db.delete(db_customer)
    db.commit()
    return None


