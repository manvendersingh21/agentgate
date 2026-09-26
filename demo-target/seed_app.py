"""
Demo Target API - Orders and Payments Backend
This intentionally has bugs for the demo.
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import uuid
from datetime import datetime, timezone

app = FastAPI(title="Demo Orders API")

# In-memory database
orders_db = {}
payments_db = {}


class Order(BaseModel):
    id: Optional[str] = None
    user_id: str
    amount: float
    status: str = "pending"
    created_at: Optional[str] = None


class Payment(BaseModel):
    id: Optional[str] = None
    order_id: str
    amount: float
    status: str = "completed"
    created_at: Optional[str] = None


@app.get("/")
def root():
    return {"message": "Orders API v1.0"}


@app.post("/orders")
def create_order(order: Order):
    order_id = str(uuid.uuid4())
    order.id = order_id
    order.created_at = datetime.now(timezone.utc).isoformat()
    orders_db[order_id] = order.model_dump()
    return orders_db[order_id]


@app.get("/orders/{order_id}")
def get_order(order_id: str):
    if order_id not in orders_db:
        raise HTTPException(status_code=404, detail="Order not found")
    return orders_db[order_id]


@app.post("/payments")
def create_payment(payment: Payment):
    if payment.order_id not in orders_db:
        raise HTTPException(status_code=404, detail="Order not found")
    
    order = orders_db[payment.order_id]
    if order["status"] == "cancelled":
        raise HTTPException(status_code=400, detail="Cannot pay for cancelled order")
    
    payment_id = str(uuid.uuid4())
    payment.id = payment_id
    payment.created_at = datetime.now(timezone.utc).isoformat()
    payments_db[payment_id] = payment.model_dump()
    
    # Update order status
    orders_db[payment.order_id]["status"] = "paid"
    
    return payments_db[payment_id]


@app.get("/payments/{payment_id}")
def get_payment(payment_id: str):
    if payment_id not in payments_db:
        raise HTTPException(status_code=404, detail="Payment not found")
    return payments_db[payment_id]


# NOTE: The refund endpoint will be added by the builder agent
# and should introduce a bug (missing auth check, wrong amount, double refund, etc.)
