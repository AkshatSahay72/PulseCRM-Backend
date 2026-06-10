from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.customer import Customer
from app.models.order import Order
from typing import List

def evaluate_segment_rules(rules: dict, db: Session) -> List[Customer]:
    query = db.query(Customer)
    
    needs_join = any(k in rules for k in ["min_spending", "max_spending", "min_orders"])
    
    if needs_join:
        query = query.outerjoin(Order).group_by(Customer.id)
        
        if "min_spending" in rules:
            query = query.having(func.coalesce(func.sum(Order.amount), 0) >= rules["min_spending"])
            
        if "max_spending" in rules:
            query = query.having(func.coalesce(func.sum(Order.amount), 0) <= rules["max_spending"])
            
        if "min_orders" in rules:
            query = query.having(func.count(Order.id) >= rules["min_orders"])
            
    return query.all()
