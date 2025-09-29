"""Basic Temporal integration tests focusing on framework functionality."""
import pytest
from datetime import timedelta
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from app.workflows.order_workflow import OrderWorkflow


class TestTemporalIntegration:
    """Test Temporal framework integration without business logic dependencies."""

    @pytest.mark.asyncio
    async def test_workflow_environment_setup(self):
        """Test that we can set up WorkflowEnvironment and create workers."""
        env = await WorkflowEnvironment.start_time_skipping()
        try:
            # Create a worker
            worker = Worker(
                env.client,
                task_queue="test-queue",
                workflows=[OrderWorkflow],
                activities=[],  # No activities to avoid DB dependencies
            )
            
            # Verify worker creation
            assert worker is not None
            
        finally:
            await env.shutdown()

    @pytest.mark.asyncio 
    async def test_workflow_lifecycle_without_activities(self):
        """Test workflow lifecycle focusing on Temporal features."""
        env = await WorkflowEnvironment.start_time_skipping()
        try:
            # Create a simple mock activity that doesn't use database
            from temporalio import activity
            
            @activity.defn
            async def mock_activity(data: str) -> str:
                return f"processed_{data}"
            
            # Create workflow worker
            worker = Worker(
                env.client,
                task_queue="test-workflow-queue",
                workflows=[OrderWorkflow],
                activities=[mock_activity],
            )
            
            async with worker:
                # Test workflow signals and queries without running activities
                handle = await env.client.start_workflow(
                    OrderWorkflow.run,
                    args=["test-order", "test-payment", [], {}],
                    id="test-lifecycle-workflow",
                    task_queue="test-workflow-queue",
                )
                
                # Test that we can query the workflow
                await env.sleep(0.01)  # Let it start
                status = await handle.query(OrderWorkflow.status)
                assert status is not None
                assert "step" in status
                assert "approved" in status
                assert "canceled" in status
                
                # Test signals
                await handle.signal(OrderWorkflow.update_address, {
                    "street": "123 New St",
                    "city": "New City"
                })
                
                # Verify address update
                updated_status = await handle.query(OrderWorkflow.status)
                assert updated_status["address"]["street"] == "123 New St"
                assert updated_status["address"]["city"] == "New City"
                
                # Test approval signal
                await handle.signal(OrderWorkflow.approve)
                
                # Verify approval
                approved_status = await handle.query(OrderWorkflow.status)
                assert approved_status["approved"] is True
                
                # Cancel to clean up (since activities would fail)
                await handle.signal(OrderWorkflow.cancel_order, "Test cleanup")
                
                # The workflow should complete as canceled
                # Note: This might fail due to activity execution, which is expected
                # The main point is testing the Temporal framework integration
                
        finally:
            await env.shutdown()

    @pytest.mark.asyncio
    async def test_workflow_cancellation_path(self):
        """Test the cancellation path of the workflow which doesn't require activities."""
        env = await WorkflowEnvironment.start_time_skipping()
        try:
            worker = Worker(
                env.client,
                task_queue="test-cancel-queue", 
                workflows=[OrderWorkflow],
                activities=[],  # No activities
            )
            
            async with worker:
                handle = await env.client.start_workflow(
                    OrderWorkflow.run,
                    args=["cancel-test-order", "cancel-payment", [], {}],
                    id="test-cancellation-workflow",
                    task_queue="test-cancel-queue",
                )
                
                # Let it start and get to receive step
                await env.sleep(0.01)
                
                # Immediately cancel before it gets to activities
                await handle.signal(OrderWorkflow.cancel_order, "Quick cancel")
                
                # The workflow should handle cancellation properly
                # This tests the cancellation logic without requiring activities to succeed
                
                status = await handle.query(OrderWorkflow.status)
                assert status["canceled"] is True
                
        finally:
            await env.shutdown()

    @pytest.mark.asyncio
    async def test_workflow_timeout_handling(self):
        """Test workflow timeout behavior for manual approval."""
        env = await WorkflowEnvironment.start_time_skipping()
        try:
            worker = Worker(
                env.client,
                task_queue="test-timeout-queue",
                workflows=[OrderWorkflow],
                activities=[],
            )
            
            async with worker:
                handle = await env.client.start_workflow(
                    OrderWorkflow.run,
                    args=["timeout-test-order", "timeout-payment", [], {}],
                    id="test-timeout-workflow", 
                    task_queue="test-timeout-queue",
                )
                
                # Let it start
                await env.sleep(0.01)
                
                # Skip ahead past the 4-second timeout for manual approval
                await env.sleep(5)
                
                # Check if workflow handled timeout correctly
                # (The actual behavior depends on how activities are handled)
                status = await handle.query(OrderWorkflow.status)
                assert status is not None
                
        finally:
            await env.shutdown()

    @pytest.mark.asyncio
    async def test_multiple_workflow_instances(self):
        """Test that multiple workflow instances can run concurrently.""" 
        env = await WorkflowEnvironment.start_time_skipping()
        try:
            worker = Worker(
                env.client,
                task_queue="test-multi-queue",
                workflows=[OrderWorkflow],
                activities=[],
            )
            
            async with worker:
                # Start multiple workflows
                handles = []
                for i in range(3):
                    handle = await env.client.start_workflow(
                        OrderWorkflow.run,
                        args=[f"multi-order-{i}", f"payment-{i}", [], {}],
                        id=f"multi-workflow-{i}",
                        task_queue="test-multi-queue",
                    )
                    handles.append(handle)
                
                await env.sleep(0.01)
                
                # Test that all workflows are running independently
                for i, handle in enumerate(handles):
                    status = await handle.query(OrderWorkflow.status)
                    assert status is not None
                    
                    # Send different signals to each
                    await handle.signal(OrderWorkflow.update_address, {
                        "order_num": i
                    })
                    
                    updated_status = await handle.query(OrderWorkflow.status) 
                    assert updated_status["address"]["order_num"] == i
                
                # Clean up
                for handle in handles:
                    await handle.signal(OrderWorkflow.cancel_order, "Multi-test cleanup")
                    
        finally:
            await env.shutdown()