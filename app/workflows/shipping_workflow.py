from __future__ import annotations
from datetime import timedelta
from typing import Dict, Any
from temporalio import workflow
from temporalio.common import RetryPolicy
from app.activities.shipping import prepare_package_activity, dispatch_carrier_activity

ACT_OPTS = {
    "start_to_close_timeout": timedelta(seconds=1),
    "schedule_to_close_timeout": timedelta(seconds=3),
    "retry_policy": RetryPolicy(
        initial_interval=timedelta(milliseconds=200),
        maximum_interval=timedelta(seconds=1),
        maximum_attempts=3,
        backoff_coefficient=2.0,
    ),
}

@workflow.defn
class ShippingWorkflow:
    @workflow.run
    async def run(self, order: Dict[str, Any]) -> str:
        await workflow.execute_activity(prepare_package_activity, args=[order], **ACT_OPTS)
        try:
            await workflow.execute_activity(dispatch_carrier_activity, args=[order], **ACT_OPTS)
        except Exception as e:
            parent = workflow.parent()
            if parent:
                await workflow.signal_external_workflow(parent, "dispatch_failed", str(e))
            raise
        return "Shipped"
