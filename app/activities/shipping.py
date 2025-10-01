# app/activities/shipping.py
from __future__ import annotations
from typing import Dict, Any

from temporalio import activity
import logging

from app.db import db_session
from app.stubs.business import package_prepared, carrier_dispatched

logger = logging.getLogger("shipping_activities")


@activity.defn
async def prepare_package_activity(order: Dict[str, Any]) -> str:
    logger.info(f"Preparing package for order: {order}")
    async with db_session() as s:
        result = await package_prepared(s, order)
    logger.info(f"Package prepared result: {result}")
    return result


@activity.defn
async def dispatch_carrier_activity(order: Dict[str, Any]) -> str:
    logger.info(f"Dispatching carrier for order: {order}")
    async with db_session() as s:
        result = await carrier_dispatched(s, order)
    logger.info(f"Carrier dispatched result: {result}")
    return result
