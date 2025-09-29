import asyncio, os
from temporalio.client import Client
from temporalio.worker import Worker
from app.workflows.shipping_workflow import ShippingWorkflow
from app.activities.shipping import prepare_package_activity, dispatch_carrier_activity

async def main() -> None:
    target = os.getenv("TEMPORAL_TARGET", "temporal:7233")
    tq = os.getenv("SHIPPING_TASK_QUEUE", "shipping-tq")
    client = await Client.connect(target)
    worker = Worker(
        client,
        task_queue=tq,
        workflows=[ShippingWorkflow],
        activities=[prepare_package_activity, dispatch_carrier_activity],
    )
    await worker.run()

if __name__ == "__main__":
    asyncio.run(main())
