"""Test configuration and fixtures."""
import pytest
import pytest_asyncio
import asyncio
from unittest.mock import AsyncMock, MagicMock
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from app.activities.order import (
    receive_order_activity,
    validate_order_activity,
    charge_payment_activity,
    mark_shipped_activity,
)
from app.activities.shipping import (
    prepare_package_activity,
    dispatch_carrier_activity,
)
from app.workflows.order_workflow import OrderWorkflow
from app.workflows.shipping_workflow import ShippingWorkflow


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def workflow_environment():
    """Create a Temporal test environment."""
    env = await WorkflowEnvironment.start_time_skipping()
    yield env
    await env.shutdown()


@pytest_asyncio.fixture
async def worker_with_activities(workflow_environment):
    """Create a worker with all activities registered."""
    worker = Worker(
        workflow_environment.client,
        task_queue="test-task-queue",
        workflows=[OrderWorkflow, ShippingWorkflow],
        activities=[
            receive_order_activity,
            validate_order_activity,
            charge_payment_activity,
            mark_shipped_activity,
            prepare_package_activity,
            dispatch_carrier_activity,
        ],
    )
    return worker


@pytest_asyncio.fixture
async def shipping_worker(workflow_environment):
    """Create a worker for shipping task queue."""
    worker = Worker(
        workflow_environment.client,
        task_queue="shipping-tq",
        workflows=[ShippingWorkflow],
        activities=[
            prepare_package_activity,
            dispatch_carrier_activity,
        ],
    )
    return worker


@pytest.fixture
def mock_db_session():
    """Mock database session."""
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    return mock_session


@pytest.fixture
def sample_order_data():
    """Sample order data for testing."""
    return {
        "order_id": "test-order-123",
        "payment_id": "payment-456",
        "items": [
            {"sku": "ITEM001", "quantity": 2, "price": 29.99},
            {"sku": "ITEM002", "quantity": 1, "price": 15.50}
        ],
        "address": {
            "street": "123 Test St",
            "city": "Test City",
            "state": "TS",
            "zip": "12345"
        }
    }


@pytest.fixture
def mock_business_functions(monkeypatch):
    """Mock all business logic functions."""
    from app.stubs import business
    
    # Mock order functions
    monkeypatch.setattr(business, "order_received", AsyncMock(return_value={
        "order_id": "test-order-123",
        "status": "received",
        "items": [],
        "address": {}
    }))
    
    monkeypatch.setattr(business, "order_validated", AsyncMock(return_value=True))
    
    monkeypatch.setattr(business, "payment_charged", AsyncMock(return_value={
        "payment_id": "payment-456",
        "status": "charged",
        "amount": 75.48
    }))
    
    monkeypatch.setattr(business, "order_shipped", AsyncMock(return_value="SHIP123"))
    
    # Mock shipping functions
    monkeypatch.setattr(business, "package_prepared", AsyncMock(return_value="PKG123"))
    monkeypatch.setattr(business, "carrier_dispatched", AsyncMock(return_value="CARRIER456"))
