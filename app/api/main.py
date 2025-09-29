from __future__ import annotations
import os
from datetime import timedelta
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from temporalio.client import Client
from temporalio.common import RetryPolicy

from app.db import run_sql_file, get_engine
from app.workflows.order_workflow import OrderWorkflow

API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8080"))
TEMPORAL_TARGET = os.getenv("TEMPORAL_TARGET", "temporal:7233")
ORDERS_TQ = os.getenv("ORDERS_TASK_QUEUE", "orders-tq")

app = FastAPI()
app.state.temporal_client = None
app.state.ready = False

class StartOrderRequest(BaseModel):
    payment_id: str
    address: Optional[Dict[str, Any]] = None
    items: Optional[List[Dict[str, Any]]] = None

class CancelRequest(BaseModel):
    reason: str

class UpdateAddressRequest(BaseModel):
    address: Dict[str, Any]

@app.on_event("startup")
async def on_startup() -> None:
    # 1) Run idempotent migration at app start
    await run_sql_file("migrations/001_init.sql")

    # 2) Connect Temporal
    client = await Client.connect(TEMPORAL_TARGET)
    app.state.temporal_client = client

    # 3) Quick DB check (ping)
    engine = get_engine()
    async with engine.connect() as conn:
        from sqlalchemy import text
        await conn.execute(text("SELECT 1"))

    app.state.ready = True

@app.get("/readyz")
async def readyz() -> Dict[str, Any]:
    # Ready only if DB migration ran and Temporal client exists
    if not app.state.ready or app.state.temporal_client is None:
        raise HTTPException(status_code=503, detail="not ready")
    return {"ok": True}

@app.post("/orders/{order_id}/start")
async def start_order(order_id: str, req: StartOrderRequest) -> Dict[str, Any]:
    client: Client = app.state.temporal_client
    if client is None:
        raise HTTPException(503, "Temporal not connected")

    workflow_id = f"order-{order_id}"
    try:
        handle = await client.start_workflow(
            OrderWorkflow.run,
            args=[order_id, req.payment_id, req.items or [], req.address or {}],
            id=workflow_id,
            task_queue=ORDERS_TQ,
            execution_timeout=timedelta(seconds=15),  # Total workflow execution timeout
            retry_policy=RetryPolicy(maximum_attempts=1),
        )
    except Exception as e:
        raise HTTPException(500, f"Failed to start workflow: {e}")

    return {"workflow_id": workflow_id, "run_id": handle.run_id}

@app.post("/orders/{order_id}/signals/cancel")
async def signal_cancel(order_id: str, req: CancelRequest) -> Dict[str, Any]:
    client: Client = app.state.temporal_client
    handle = client.get_workflow_handle(f"order-{order_id}")
    await handle.signal("cancel_order", req.reason)
    return {"ok": True}

@app.post("/orders/{order_id}/signals/update-address")
async def signal_update_address(order_id: str, req: UpdateAddressRequest) -> Dict[str, Any]:
    client: Client = app.state.temporal_client
    handle = client.get_workflow_handle(f"order-{order_id}")
    await handle.signal("update_address", req.address)
    return {"ok": True}

@app.post("/orders/{order_id}/signals/approve")
async def signal_approve(order_id: str) -> Dict[str, Any]:
    client: Client = app.state.temporal_client
    handle = client.get_workflow_handle(f"order-{order_id}")
    await handle.signal("approve")
    return {"ok": True}

@app.get("/orders/{order_id}/status")
async def query_status(order_id: str) -> Dict[str, Any]:
    client: Client = app.state.temporal_client
    handle = client.get_workflow_handle(f"order-{order_id}")
    try:
        status = await handle.query("status")
    except Exception as e:
        raise HTTPException(404, f"Workflow not found or no status: {e}")
    return status
