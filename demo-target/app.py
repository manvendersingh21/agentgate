"""
Recorded offline fix for the refund endpoint.
Live mode does not use this file. It asks the CodeRabbit Coding Agent to patch the PR.
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import uuid
from datetime import datetime, timezone

app = FastAPI(title="Demo Orders API")

orders_db = {}
payments_db = {}
refunds_db = {}


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


class Refund(BaseModel):
    payment_id: str
    amount: float
    user_id: str


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
    orders_db[payment.order_id]["status"] = "paid"
    return payments_db[payment_id]


@app.get("/payments/{payment_id}")
def get_payment(payment_id: str):
    if payment_id not in payments_db:
        raise HTTPException(status_code=404, detail="Payment not found")
    return payments_db[payment_id]


@app.post("/refunds")
def create_refund(refund: Refund):
    if refund.payment_id not in payments_db:
        raise HTTPException(status_code=404, detail="Payment not found")

    payment = payments_db[refund.payment_id]
    order = orders_db[payment["order_id"]]

    if order["user_id"] != refund.user_id:
        raise HTTPException(status_code=403, detail="Unauthorized: cannot refund another user's order")

    if refund.amount > payment["amount"]:
        raise HTTPException(status_code=400, detail="Refund amount exceeds payment amount")

    for existing in refunds_db.values():
        if existing["payment_id"] == refund.payment_id:
            raise HTTPException(status_code=400, detail="Payment already refunded")

    refund_id = str(uuid.uuid4())
    refund_data = {
        "id": refund_id,
        "payment_id": refund.payment_id,
        "amount": refund.amount,
        "user_id": refund.user_id,
        "status": "completed",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    refunds_db[refund_id] = refund_data
    return refund_data
