# app/activities/shipping.py
from __future__ import annotations
from typing import Dict, Any

from temporalio import activity

from app.db import db_session
from app.stubs.business import package_prepared, carrier_dispatched


@activity.defn
async def prepare_package_activity(order: Dict[str, Any]) -> str:
    """Record package preparation."""
    async with db_session() as s:
        return await package_prepared(s, order)


@activity.defn
async def dispatch_carrier_activity(order: Dict[str, Any]) -> str:
    """Record carrier dispatch (may be flaky to trigger retries)."""
    async with db_session() as s:
        return await carrier_dispatched(s, order)
