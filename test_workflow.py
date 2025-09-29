"""
Simple test script to debug workflow start calls
"""
import asyncio
import json
from temporalio.client import Client
from temporalio.common import RetryPolicy
from datetime import timedelta
from app.workflows.order_workflow import OrderWorkflow

async def test_workflow_start():
    client = await Client.connect("localhost:7233")
    
    order_id = "test-debug-001"
    payment_id = "payment-debug-123"
    items = [{"sku": "ABC", "qty": 2}]
    address = {"street": "123 Test St"}
    
    print(f"Starting workflow with args: {order_id}, {payment_id}, {items}, {address}")
    
    try:
        # Test the exact call that the API is making
        handle = await client.start_workflow(
            OrderWorkflow.run,
            args=[order_id, payment_id, items, address],
            id=f"order-{order_id}",
            task_queue="orders-tq",
            execution_timeout=timedelta(seconds=15),
            retry_policy=RetryPolicy(maximum_attempts=1),
        )
        print(f"✅ Success! Workflow started: {handle.id}")
        return handle
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

if __name__ == "__main__":
    asyncio.run(test_workflow_start())