from __future__ import annotations
from datetime import timedelta
from typing import Dict, Any, Optional, List
from temporalio import workflow
from temporalio.common import RetryPolicy
from app.activities.order import (
    receive_order_activity, validate_order_activity, charge_payment_activity
)
from app.workflows.shipping_workflow import ShippingWorkflow

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
class OrderWorkflow:
    def __init__(self) -> None:
        self.order_id = ""
        self.payment_id = ""
        self.address: Optional[Dict[str, Any]] = None
        self.items: List[Dict[str, Any]] = []
        self.approved = False
        self.canceled = False
        self.current_step = "init"
        self.dispatch_failed_reason: Optional[str] = None

    @workflow.signal
    def cancel_order(self, reason: str) -> None:
        self.canceled = True

    @workflow.signal
    def update_address(self, address: Dict[str, Any]) -> None:
        self.address = address

    @workflow.signal
    def approve(self) -> None:
        self.approved = True

    @workflow.signal
    def dispatch_failed(self, reason: str) -> None:
        self.dispatch_failed_reason = reason

    @workflow.query
    def status(self) -> Dict[str, Any]:
        return {
            "step": self.current_step,
            "approved": self.approved,
            "canceled": self.canceled,
            "address": self.address,
            "dispatch_failed_reason": self.dispatch_failed_reason,
        }

    @workflow.run
    async def run(self, order_id: str, payment_id: str, items: List[Dict[str, Any]], address: Dict[str, Any]) -> str:
        self.order_id, self.payment_id = order_id, payment_id
        self.items, self.address = items or [], address or {}

        self.current_step = "receive"
        order = await workflow.execute_activity(receive_order_activity, args=[order_id, self.items, self.address], **ACT_OPTS)

        self.current_step = "validate"
        await workflow.execute_activity(validate_order_activity, args=[order], **ACT_OPTS)

        self.current_step = "manual_review"
        await workflow.wait_condition(lambda: self.approved or self.canceled, timeout=timedelta(seconds=4))
        if self.canceled:
            return "Canceled"

        self.current_step = "charge"
        await workflow.execute_activity(
            charge_payment_activity,
            args=[{"order_id": self.order_id, "items": self.items, "address": self.address}, self.payment_id],
            **ACT_OPTS
        )

        self.current_step = "shipping"
        child = await workflow.start_child_workflow(
            ShippingWorkflow.run,
            args=[{"order_id": self.order_id, "items": self.items, "address": self.address}],
            id=f"ship-{self.order_id}",
            task_queue="shipping-tq",
            retry_policy=RetryPolicy(maximum_attempts=1),
        )
        result = await child
        self.current_step = "shipped"
        return result
