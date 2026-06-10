from app.core.database import SessionLocal
from app.models.customer import Customer
from app.models.order import Order
from decimal import Decimal

def seed():
    db = SessionLocal()
    try:
        # Check if database already has customers to prevent duplicate seeding
        if db.query(Customer).count() > 0:
            print("Database already contains records. Skipping seeding.")
            return
        
        print("Seeding database with sample records...")
        
        # 1. Create Customers
        c1 = Customer(first_name="Alice", last_name="Smith", email="alice@example.com", phone="1234567890")
        c2 = Customer(first_name="Bob", last_name="Jones", email="bob@example.com", phone="0987654321")
        c3 = Customer(first_name="Charlie", last_name="Brown", email="charlie@example.com", phone="5555555555")
        
        db.add_all([c1, c2, c3])
        db.commit() # Save transactions
        
        # Refresh to load auto-generated primary IDs
        db.refresh(c1)
        db.refresh(c2)
        db.refresh(c3)
        
        # 2. Create Orders bound to Customers
        o1 = Order(customer_id=c1.id, amount=Decimal("120.50"), status="completed")
        o2 = Order(customer_id=c1.id, amount=Decimal("45.00"), status="completed")
        o3 = Order(customer_id=c2.id, amount=Decimal("250.00"), status="completed")
        o4 = Order(customer_id=c3.id, amount=Decimal("15.00"), status="pending")
        
        db.add_all([o1, o2, o3, o4])
        db.commit()
        
        print("Database successfully seeded!")
        print(f"-> Seeded Customers: Alice (ID: {c1.id}), Bob (ID: {c2.id}), Charlie (ID: {c3.id})")
        print(f"-> Seeded Orders: Alice (2 orders), Bob (1 order), Charlie (1 order)")
        
    except Exception as e:
        db.rollback()
        print(f"Error seeding database: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed()
