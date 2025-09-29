"""Simple integration test to verify Temporal setup works."""
import pytest
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from app.workflows.order_workflow import OrderWorkflow
from app.activities.order import receive_order_activity


class TestTemporalSetup:
    """Basic tests to verify Temporal testing setup."""

    @pytest.mark.asyncio
    async def test_workflow_environment_creation(self):
        """Test that we can create a workflow environment."""
        env = await WorkflowEnvironment.start_time_skipping()
        try:
            assert env.client is not None
        finally:
            await env.shutdown()
            
    @pytest.mark.asyncio 
    async def test_worker_creation(self, workflow_environment):
        """Test that we can create a worker with workflows and activities."""
        worker = Worker(
            workflow_environment.client,
            task_queue="test-queue",
            workflows=[OrderWorkflow],
            activities=[receive_order_activity],
        )
        assert worker is not None

    @pytest.mark.asyncio
    async def test_simple_workflow_start(self, workflow_environment, mock_business_functions):
        """Test that we can start a workflow."""
        worker = Worker(
            workflow_environment.client,
            task_queue="simple-test-queue",
            workflows=[OrderWorkflow],
            activities=[receive_order_activity],
        )
        
        async with worker:
            # Start a workflow
            handle = await workflow_environment.client.start_workflow(
                OrderWorkflow.run,
                args=["test-order", "test-payment", [], {}],
                id="simple-test-workflow",
                task_queue="simple-test-queue",
            )
            
            # Give it a tiny moment to start
            await workflow_environment.sleep(0.01)
            
            # Verify we can query it
            status = await handle.query(OrderWorkflow.status)
            assert status is not None
            assert "step" in status
            
            # Cancel it to clean up
            await handle.signal(OrderWorkflow.cancel_order, "Test cleanup")
            result = await handle.result()
            assert result == "Canceled"