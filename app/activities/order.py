# app/activities/order.py
from __future__ import annotations
from typing import Dict, Any, Optional, List

from temporalio import activity

from app.db import db_session
from app.stubs.business import (
    order_received,
    order_validated,
    payment_charged,
    order_shipped,
)


@activity.defn
async def receive_order_activity(
    order_id: str,
    items: Optional[List[Dict[str, Any]]] = None,
    address: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Insert a new order and emit an event."""
    async with db_session() as s:
        return await order_received(s, order_id, items or [], address or {})


@activity.defn
async def validate_order_activity(order: Dict[str, Any]) -> bool:
    """Validate order items and mark order validated."""
    async with db_session() as s:
        return await order_validated(s, order)


@activity.defn
async def charge_payment_activity(order: Dict[str, Any], payment_id: str) -> Dict[str, Any]:
    """Charge payment idempotently using payment_id."""
    async with db_session() as s:
        return await payment_charged(s, order, payment_id)


@activity.defn
async def mark_shipped_activity(order: Dict[str, Any]) -> str:
    """Mark order as shipped (used by parent if desired)."""
    async with db_session() as s:
        return await order_shipped(s, order)
