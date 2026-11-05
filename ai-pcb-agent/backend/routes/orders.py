from __future__ import annotations

import hashlib
import hmac
import os
import re
import uuid
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

import db

router = APIRouter(prefix="/api", tags=["orders"])
RAZORPAY_API = "https://api.razorpay.com/v1"


class OrderCreate(BaseModel):
    pcb_id: str
    manufacturer_id: str
    quantity: int = Field(gt=0, le=1000)
    total_price: float = Field(gt=0)


class PaymentVerification(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


def _credentials() -> tuple[str, str]:
    key_id = os.getenv("RAZORPAY_KEY_ID", "").strip()
    secret = os.getenv("RAZORPAY_KEY_SECRET", "").strip()
    if os.getenv("PAYMENT_MODE", "test").lower() != "test" or not key_id.startswith("rzp_test_") or not secret:
        raise HTTPException(503, "Razorpay Test Mode is not configured. Add your test Key ID and Secret to ai-pcb-agent/backend/.env, then restart the backend.")
    return key_id, secret


def _currency() -> str:
    currency = os.getenv("RAZORPAY_CURRENCY", "USD").upper()
    if currency != "USD":
        raise HTTPException(500, "PCB Forge quotes are in USD. Keep RAZORPAY_CURRENCY=USD; currency conversion is not implemented.")
    return currency


def _request_record(order: dict, payment_id: str) -> dict:
    return {
        "status": "PAID", "order_id": order["id"], "manufacturer": order["manufacturer_name"],
        "quantity": order["quantity"], "total_price": order["total_price"],
        "estimated_delivery_days": order["estimated_delivery_days"], "payment_id": payment_id,
        "payment_mode": "TEST", "currency": _currency(),
    }


@router.post("/orders")
async def create_order(payload: OrderCreate):
    key_id, secret = _credentials()
    project = db.PROJECTS.get(payload.pcb_id)
    if not project or "recommendation" not in project:
        raise HTTPException(404, "Analyzed PCB project not found.")
    quote = next((q for q in project["recommendation"].get("all_quotes", []) if q.get("manufacturer_id") == payload.manufacturer_id), None)
    if not quote:
        raise HTTPException(404, "Manufacturer quote not found.")
    expected_total = round(float(quote["price_usd"]) * payload.quantity / 5, 2)
    if abs(expected_total - payload.total_price) > 0.02:
        raise HTTPException(400, "The quote changed. Refresh the manufacturing estimate and try again.")

    amount_minor = round(expected_total * 100)
    currency = _currency()
    internal_id = f"ORD-{uuid.uuid4().hex[:10].upper()}"
    request_body = {
        "amount": amount_minor, "currency": currency, "receipt": internal_id,
        "notes": {"pcb_project": payload.pcb_id, "manufacturer": quote["manufacturer_name"]},
    }
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(f"{RAZORPAY_API}/orders", auth=(key_id, secret), json=request_body)
        if response.status_code >= 400:
            raise HTTPException(502, "Razorpay could not create the test checkout order. Check your Test Mode keys and supported currency.")
        provider_order = response.json()
    except httpx.HTTPError as exc:
        raise HTTPException(502, "Could not reach Razorpay. Check your internet connection and try again.") from exc
    if provider_order.get("amount") != amount_minor or provider_order.get("currency") != currency or not provider_order.get("id"):
        raise HTTPException(502, "Razorpay returned an unexpected checkout order.")

    order = {
        "id": internal_id, "pcb_id": payload.pcb_id, "manufacturer_id": payload.manufacturer_id,
        "manufacturer_name": quote["manufacturer_name"], "quantity": payload.quantity,
        "total_price": expected_total, "estimated_delivery_days": quote["lead_time_days"],
        "status": "PAYMENT_PENDING", "created_at": datetime.now(timezone.utc).isoformat(),
    }
    db.save_order(order)
    db.save_payment_attempt({
        "order_id": internal_id, "provider_order_id": provider_order["id"],
        "amount_minor": amount_minor, "currency": currency, "status": "PENDING",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return {
        "order_id": internal_id, "razorpay_order_id": provider_order["id"], "key_id": key_id,
        "amount": amount_minor, "currency": currency, "manufacturer": order["manufacturer_name"],
        "quantity": order["quantity"], "total_price": expected_total,
        "estimated_delivery_days": order["estimated_delivery_days"], "payment_mode": "TEST",
    }


@router.post("/orders/request")
async def save_prototype_request(payload: OrderCreate):
    """Save a local prototype request when Razorpay Test Mode is not configured."""
    project = db.PROJECTS.get(payload.pcb_id)
    if not project or "recommendation" not in project:
        raise HTTPException(404, "Analyzed PCB project not found.")
    quote = next((q for q in project["recommendation"].get("all_quotes", []) if q.get("manufacturer_id") == payload.manufacturer_id), None)
    if not quote:
        raise HTTPException(404, "Manufacturer quote not found.")
    expected_total = round(float(quote["price_usd"]) * payload.quantity / 5, 2)
    if abs(expected_total - payload.total_price) > 0.02:
        raise HTTPException(400, "The quote changed. Refresh the manufacturing estimate and try again.")

    order_id = f"REQ-{uuid.uuid4().hex[:10].upper()}"
    order = {
        "id": order_id, "pcb_id": payload.pcb_id, "manufacturer_id": payload.manufacturer_id,
        "manufacturer_name": quote["manufacturer_name"], "quantity": payload.quantity,
        "total_price": expected_total, "estimated_delivery_days": quote["lead_time_days"],
        "status": "REQUESTED", "created_at": datetime.now(timezone.utc).isoformat(),
    }
    db.save_order(order)
    record = {
        "status": "REQUESTED", "order_id": order_id, "manufacturer": order["manufacturer_name"],
        "quantity": order["quantity"], "total_price": expected_total,
        "estimated_delivery_days": order["estimated_delivery_days"],
        "payment_mode": "NOT_CHARGED", "currency": "USD",
    }
    project.setdefault("manufacturing_requests", []).append(record)
    db.add_history(payload.pcb_id, "Prototype request accepted (demo)", f"{order['manufacturer_name']} · {order['quantity']} boards · no payment processed")
    return record

@router.post("/orders/verify")
async def verify_payment(payload: PaymentVerification):
    attempt = db.get_payment_attempt(payload.razorpay_order_id)
    if not attempt:
        raise HTTPException(404, "Payment order was not found.")
    order = db.get_order(attempt["order_id"])
    if not order:
        raise HTTPException(404, "Manufacturing request was not found.")
    if attempt["status"] == "PAID":
        return _request_record(order, attempt["payment_id"] or payload.razorpay_payment_id)

    _, secret = _credentials()
    expected_signature = hmac.new(
        secret.encode(), f"{payload.razorpay_order_id}|{payload.razorpay_payment_id}".encode(), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected_signature, payload.razorpay_signature):
        raise HTTPException(400, "Payment signature verification failed.")

    key_id, secret = _credentials()
    try:
        async with httpx.AsyncClient(timeout=20, auth=(key_id, secret)) as client:
            response = await client.get(f"{RAZORPAY_API}/payments/{payload.razorpay_payment_id}")
            if response.status_code >= 400:
                raise HTTPException(502, "Could not verify the payment with Razorpay.")
            payment = response.json()
            if (payment.get("order_id") != payload.razorpay_order_id or
                payment.get("amount") != attempt["amount_minor"] or payment.get("currency") != attempt["currency"]):
                raise HTTPException(400, "Payment details do not match this order.")
            if payment.get("status") == "authorized":
                response = await client.post(
                    f"{RAZORPAY_API}/payments/{payload.razorpay_payment_id}/capture",
                    json={"amount": attempt["amount_minor"], "currency": attempt["currency"]},
                )
                if response.status_code >= 400:
                    raise HTTPException(502, "Payment was authorized but could not be captured. Retry verification.")
                payment = response.json()
    except httpx.HTTPError as exc:
        raise HTTPException(502, "Could not reach Razorpay to verify the payment. Retry in a moment.") from exc
    if payment.get("status") != "captured":
        raise HTTPException(402, "Payment is not captured. No manufacturing request was saved.")

    db.update_payment_attempt(payload.razorpay_order_id, "PAID", payload.razorpay_payment_id)
    db.update_order_status(order["id"], "PAID")
    project = db.PROJECTS.get(order["pcb_id"])
    if project is not None:
        requests = project.setdefault("manufacturing_requests", [])
        if not any(item.get("order_id") == order["id"] for item in requests):
            record = _request_record(order, payload.razorpay_payment_id)
            requests.append(record)
            db.add_history(order["pcb_id"], "Manufacturing request paid (test)", f"{order['manufacturer_name']} · {order['quantity']} boards · payment {payload.razorpay_payment_id}")
            db.save_project(project)
    return _request_record(order, payload.razorpay_payment_id)


@router.get("/orders/{order_id}")
async def get_order(order_id: str):
    order = db.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")
    return order



