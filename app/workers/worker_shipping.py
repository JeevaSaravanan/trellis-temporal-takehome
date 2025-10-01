import asyncio, os
import logging
from temporalio.client import Client
from temporalio.worker import Worker
from app.workflows.shipping_workflow import ShippingWorkflow
from app.activities.shipping import prepare_package_activity, dispatch_carrier_activity

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("worker_shipping")

async def main() -> None:
    target = os.getenv("TEMPORAL_TARGET", "temporal:7233")
    tq = os.getenv("SHIPPING_TASK_QUEUE", "shipping-tq")
    logger.info(f"Connecting to Temporal at {target}, polling task queue '{tq}'")
    client = await Client.connect(target)
    worker = Worker(
        client,
        task_queue=tq,
        workflows=[ShippingWorkflow],
        activities=[prepare_package_activity, dispatch_carrier_activity],
    )
    logger.info("Starting worker for shipping workflow and activities")
    await worker.run()

if __name__ == "__main__":
    asyncio.run(main())
