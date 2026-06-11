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


@router.post("/bulk", status_code=status.HTTP_201_CREATED)
def bulk_import_customers(records: List[dict], db: Session = Depends(get_db)):
    if not records:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No records provided"
        )
        
    imported_count = 0
    skipped_duplicates = 0
    skipped_invalid = 0
    
    cleaned_records = []
    incoming_emails = set()
    
    for r in records:
        first_name = None
        last_name = None
        email = None
        phone = None
        
        # Case-insensitive header matching
        for k, v in r.items():
            if v is None:
                continue
            v_str = str(v).strip()
            if not v_str:
                continue
                
            k_lower = k.lower()
            
            # Match email
            if "email" in k_lower or "mail" in k_lower or "addr" in k_lower:
                if not email:
                    email = v_str
            # Match phone
            elif "phone" in k_lower or "tel" in k_lower or "cell" in k_lower or "mob" in k_lower or "contact" in k_lower:
                if not phone:
                    phone = v_str
            # Match first name
            elif "first" in k_lower or "fname" in k_lower or "given" in k_lower:
                if not first_name:
                    first_name = v_str
            # Match last name
            elif "last" in k_lower or "lname" in k_lower or "sur" in k_lower or "family" in k_lower:
                if not last_name:
                    last_name = v_str
                    
        # Check fallback for single Name column
        if not first_name:
            for k, v in r.items():
                if v is None:
                    continue
                v_str = str(v).strip()
                if not v_str:
                    continue
                k_lower = k.lower()
                if k_lower == "name" or "fullname" in k_lower or "full name" in k_lower:
                    parts = v_str.split(None, 1)
                    first_name = parts[0]
                    if len(parts) > 1:
                        last_name = parts[1]
                    break
                    
        # Fallbacks & validations
        if not first_name:
            skipped_invalid += 1
            continue
        if not last_name:
            last_name = "Customer"
            
        if not email or "@" not in email:
            skipped_invalid += 1
            continue
            
        email = email.lower()
        
        cleaned_records.append({
            "first_name": first_name[:50],
            "last_name": last_name[:50],
            "email": email[:100],
            "phone": phone[:20] if phone else None
        })
        incoming_emails.add(email)

    if not cleaned_records:
        return {
            "total_records": len(records),
            "imported": 0,
            "skipped_duplicates": 0,
            "skipped_invalid": skipped_invalid
        }

    # Query DB in a single roundtrip to identify existing duplicates
    existing_emails_rows = db.query(Customer.email).filter(Customer.email.in_(list(incoming_emails))).all()
    existing_emails = {row[0].lower() for row in existing_emails_rows}
    
    final_inserts = []
    for cr in cleaned_records:
        if cr["email"] in existing_emails:
            skipped_duplicates += 1
        else:
            final_inserts.append(cr)
            existing_emails.add(cr["email"]) # Prevent duplicate inserts within the same batch upload
            
    if final_inserts:
        try:
            db.bulk_insert_mappings(Customer, final_inserts)
            db.commit()
            imported_count = len(final_inserts)
        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Database bulk insertion failed: {e}"
            )
            
    return {
        "total_records": len(records),
        "imported": imported_count,
        "skipped_duplicates": skipped_duplicates,
        "skipped_invalid": skipped_invalid
    }



