import asyncio, os
from temporalio.client import Client
from temporalio.worker import Worker
from app.workflows.order_workflow import OrderWorkflow
from app.activities.order import receive_order_activity, validate_order_activity, charge_payment_activity, mark_shipped_activity

async def main() -> None:
    target = os.getenv("TEMPORAL_TARGET", "temporal:7233")
    tq = os.getenv("ORDERS_TASK_QUEUE", "orders-tq")
    client = await Client.connect(target)
    worker = Worker(
        client,
        task_queue=tq,
        workflows=[OrderWorkflow],
        activities=[receive_order_activity, validate_order_activity, charge_payment_activity, mark_shipped_activity],
    )
    await worker.run()

if __name__ == "__main__":
    asyncio.run(main())
