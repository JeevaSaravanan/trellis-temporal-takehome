# Order Lifecycle Orchestration with Temporal

A production-ready order processing system built with Temporal workflow orchestration, demonstrating fault-tolerant distributed computing with Python.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Starting Temporal Server and Database](#starting-temporal-server-and-database)
- [Running Workers](#running-workers)
- [Triggering Workflows](#triggering-workflows)
- [Sending Signals](#sending-signals)
- [Querying Workflow State](#querying-workflow-state)
- [Database Schema and Persistence](#database-schema-and-persistence)
- [Testing](#testing)
- [Project Structure](#project-structure)
- [Configuration](#configuration)

## Overview

This project implements a complete order lifecycle workflow using Temporal, demonstrating:

- **Order Processing**: Multi-step workflow from order creation to shipment
- **Manual Approval Gate**: Orders wait for manual approval before payment processing
- **Signal Handling**: Dynamic order cancellation and address updates
- **Child Workflows**: Shipping process runs as a separate workflow on dedicated task queue
- **Fault Tolerance**: Automatic retries with configurable policies
- **State Persistence**: PostgreSQL database for order, payment, and event tracking
- **Observability**: Comprehensive logging throughout the workflow lifecycle

### Order Workflow States

```
receive -> validate -> manual_review -> charge -> shipping -> shipped
                            |
                            v
                        canceled (if cancel signal received)
```

## Architecture

### Components

- **OrderWorkflow**: Main workflow orchestrating the complete order lifecycle
- **ShippingWorkflow**: Child workflow handling package preparation and carrier dispatch
- **Activities**: Individual business logic units (receive, validate, charge, prepare, dispatch)
- **Workers**: Process workflows and activities on specific task queues
  - `worker_orders`: Handles OrderWorkflow and order-related activities (task queue: `orders-tq`)
  - `worker_shipping`: Handles ShippingWorkflow and shipping activities (task queue: `shipping-tq`)
- **FastAPI**: REST API for triggering workflows and sending signals
- **PostgreSQL**: Persistent storage for orders, payments, and events

### Task Queue Architecture

- **orders-tq**: Primary task queue for order workflows and activities
- **shipping-tq**: Dedicated task queue for shipping workflows (child workflow isolation)

## Prerequisites

- Python 3.11+
- Docker and Docker Compose
- Make (optional, for using Makefile commands)

## Quick Start

```bash
# 1. Start all services (Temporal, PostgreSQL, API, Workers)
docker-compose up -d

# 2. Wait for services to be ready (~10 seconds)
docker-compose logs -f api

# 3. Create an order
curl -X POST http://localhost:8080/orders/order-001/start \
  -H "Content-Type: application/json" \
  -d '{
    "payment_id": "pay-001",
    "items": [{"sku": "ABC123", "qty": 2}],
    "address": {"street": "123 Main St", "city": "San Francisco"}
  }'

# 4. Approve the order
curl -X POST http://localhost:8080/signals/approve \
  -H "Content-Type: application/json" \
  -d '{"workflow_id": "order-order-001"}'

# 5. Check workflow status
curl http://localhost:8080/status/order-order-001
```

## Starting Temporal Server and Database

### Using Docker Compose (Recommended)

Start all services including Temporal server, PostgreSQL, API, and workers:

```bash
docker-compose up -d
```

This starts:
- **temporal**: Temporal server with web UI (port 7233 for gRPC, 8233 for UI)
- **db**: PostgreSQL database (port 5432, user: trellis, db: trellisdb)
- **api**: FastAPI REST API (port 8080)
- **worker_orders**: Order workflow worker
- **worker_shipping**: Shipping workflow worker

### Manual Setup

If you prefer to run services separately:

1. **Start PostgreSQL**:
```bash
docker run -d \
  --name postgres \
  -e POSTGRES_USER=trellis \
  -e POSTGRES_PASSWORD=trellis \
  -e POSTGRES_DB=trellisdb \
  -p 5432:5432 \
  postgres:16-alpine
```

2. **Start Temporal Server**:
```bash
docker run -d \
  --name temporal \
  -p 7233:7233 \
  -p 8233:8233 \
  temporalio/auto-setup:1.24.3
```

3. **Run Database Migrations**:
```bash
# Install dependencies
pip install -r requirements.txt

# Apply schema
psql -h localhost -U trellis -d trellisdb -f migrations/001_init.sql
```

### Accessing Services

- **Temporal Web UI**: http://localhost:8233
- **FastAPI Docs**: http://localhost:8080/docs
- **FastAPI OpenAPI**: http://localhost:8080/openapi.json
- **PostgreSQL**: localhost:5432 (user: trellis, password: trellis, db: trellisdb)

## Running Workers

Workers poll Temporal task queues and execute workflows and activities.

### Using Docker Compose

Workers start automatically with `docker-compose up -d`:

```bash
# View worker logs
docker-compose logs -f worker_orders
docker-compose logs -f worker_shipping
```

### Running Locally

For development, run workers locally:

```bash
# Terminal 1: Order worker
python -m app.workers.worker_orders

# Terminal 2: Shipping worker
python -m app.workers.worker_shipping
```

### Worker Configuration

**Order Worker** (`worker_orders.py`):
- Task Queue: `orders-tq`
- Workflows: `OrderWorkflow`
- Activities: `receive_order_activity`, `validate_order_activity`, `charge_payment_activity`

**Shipping Worker** (`worker_shipping.py`):
- Task Queue: `shipping-tq`
- Workflows: `ShippingWorkflow`
- Activities: `prepare_package_activity`, `dispatch_carrier_activity`

## Triggering Workflows

### Via REST API

**Start a new order workflow**:

```bash
curl -X POST http://localhost:8080/orders/{order_id}/start \
  -H "Content-Type: application/json" \
  -d '{
    "payment_id": "pay-123",
    "items": [
      {"sku": "WIDGET-001", "qty": 2},
      {"sku": "GADGET-002", "qty": 1}
    ],
    "address": {
      "street": "123 Main St",
      "city": "San Francisco",
      "state": "CA",
      "zip": "94105"
    }
  }'
```

**Response**:
```json
{
  "workflow_id": "order-{order_id}",
  "run_id": "...",
  "message": "Workflow started"
}
```

### Programmatically (Python)

```python
from temporalio.client import Client
from app.workflows.order_workflow import OrderWorkflow

async def start_order():
    client = await Client.connect("localhost:7233")
    
    handle = await client.start_workflow(
        OrderWorkflow.run,
        args=[
            "order-123",  # order_id
            "pay-123",    # payment_id
            [{"sku": "ABC", "qty": 1}],  # items
            {"street": "123 Main St", "city": "SF"}  # address
        ],
        id="order-order-123",
        task_queue="orders-tq"
    )
    
    result = await handle.result()
    print(f"Workflow completed: {result}")
```

## Sending Signals

Signals allow external systems to communicate with running workflows.

### Available Signals

1. **approve**: Approve order for payment and shipping
2. **cancel_order**: Cancel the order at any stage
3. **update_address**: Update shipping address before shipment

### Via REST API

**Approve Order**:
```bash
curl -X POST http://localhost:8080/signals/approve \
  -H "Content-Type: application/json" \
  -d '{"workflow_id": "order-order-123"}'
```

**Cancel Order**:
```bash
curl -X POST http://localhost:8080/signals/cancel \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_id": "order-order-123",
    "reason": "Customer requested cancellation"
  }'
```

**Update Address**:
```bash
curl -X POST http://localhost:8080/signals/update-address \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_id": "order-order-123",
    "new_address": {
      "street": "456 New St",
      "city": "Oakland",
      "state": "CA",
      "zip": "94601"
    }
  }'
```

### Programmatically (Python)

```python
from temporalio.client import Client

async def send_signals():
    client = await Client.connect("localhost:7233")
    handle = client.get_workflow_handle("order-order-123")
    
    # Approve order
    await handle.signal("approve")
    
    # Update address
    await handle.signal("update_address", {
        "street": "789 Oak Ave",
        "city": "Berkeley"
    })
    
    # Cancel order
    await handle.signal("cancel_order", "Changed mind")
```

## Querying Workflow State

### Via REST API

**Get Current Workflow Status**:
```bash
curl http://localhost:8080/status/{workflow_id}
```

**Response**:
```json
{
  "step": "manual_review",
  "approved": false,
  "canceled": false,
  "address": {
    "street": "123 Main St",
    "city": "San Francisco"
  },
  "dispatch_failed_reason": null
}
```

### Programmatically (Python)

```python
from temporalio.client import Client

async def query_status():
    client = await Client.connect("localhost:7233")
    handle = client.get_workflow_handle("order-order-123")
    
    # Query current status
    status = await handle.query("status")
    print(f"Current step: {status['step']}")
    print(f"Approved: {status['approved']}")
    print(f"Canceled: {status['canceled']}")
```

### Via Temporal Web UI

1. Navigate to http://localhost:8233
2. Find your workflow by ID (e.g., `order-order-123`)
3. Click on the workflow to see:
   - Current state and history
   - Pending activities
   - Signal history
   - Query results

## Database Schema and Persistence

### Schema Overview

The system uses PostgreSQL for persistent storage with three main tables:

**orders** - Stores order state:
```sql
CREATE TABLE orders (
    id VARCHAR(255) PRIMARY KEY,
    state VARCHAR(50) NOT NULL,
    address_json TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

**payments** - Tracks payment transactions:
```sql
CREATE TABLE payments (
    payment_id VARCHAR(255) PRIMARY KEY,
    order_id VARCHAR(255) REFERENCES orders(id),
    amount DECIMAL(10,2),
    status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW()
);
```

**events** - Audit log for all order events:
```sql
CREATE TABLE events (
    id SERIAL PRIMARY KEY,
    order_id VARCHAR(255) REFERENCES orders(id),
    type VARCHAR(100) NOT NULL,
    payload_json TEXT,
    ts TIMESTAMP DEFAULT NOW()
);
```

### Migrations

Database schema is version-controlled in `migrations/` directory.

**Apply migrations**:
```bash
# Using psql
psql -h localhost -U postgres -d orders -f migrations/001_init.sql

# Or via Docker
docker exec -i postgres psql -U postgres -d orders < migrations/001_init.sql
```

### Persistence Rationale

**Why PostgreSQL?**

1. **Durability**: Order and payment data must survive workflow restarts
2. **Auditability**: Events table provides complete audit trail
3. **Consistency**: ACID guarantees for financial transactions
4. **Queryability**: SQL enables complex reporting and analytics
5. **Integration**: Standard interface for external systems

**What's Persisted?**

- **orders**: Current order state, address (survives workflow replay)
- **payments**: Payment attempts and status (immutable records)
- **events**: All workflow events (complete audit trail)

**What's Not Persisted?**

- Workflow execution state (managed by Temporal)
- Activity retry attempts (Temporal history)
- Intermediate computation results (workflow variables)

**Data Flow**:
```
Activity executes -> Writes to DB -> Returns result -> Temporal records -> Workflow continues
                                                         in history
```

### Database Connection

The database connection is configured via environment variables and built in the application:

```python
# In docker-compose.yml
DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}

# For local development
DATABASE_URL: postgresql+asyncpg://trellis:trellis@localhost:5432/trellisdb
```

The connection uses `asyncpg` driver for async database operations with SQLAlchemy.

## Testing

The project includes comprehensive test suites for unit, integration, and end-to-end testing.

### Test Structure

```
tests/
├── conftest.py                      # Shared fixtures
├── test_activities_unit.py          # Unit tests for activities
├── test_activities.py               # Activity integration tests
├── test_workflows.py                # Workflow unit tests
├── test_integration_complete.py     # Full integration tests
└── test_temporal_integration.py     # Temporal-specific tests
```

### Running Tests

**Run all tests**:
```bash
pytest
```

**Run specific test file**:
```bash
pytest tests/test_integration_complete.py -v
```

**Run specific test**:
```bash
pytest tests/test_integration_complete.py::TestCompleteWorkflowIntegration::test_complete_workflow_with_approval -v
```

**Run with coverage**:
```bash
pytest --cov=app --cov-report=html
```

### Integration Tests

The integration test suite (`test_integration_complete.py`) includes 11 comprehensive tests:

**Complete Workflow Tests**:
- Full workflow from creation to shipment with approval
- Workflow with address update before approval
- Workflow timeout behavior without approval

**Cancel Order Tests**:
- Cancel order before approval (during manual review)
- Cancel order immediately after start
- Verify cancellation doesn't affect post-approval workflows

**Update Address Tests**:
- Update address during manual review
- Multiple address updates (last one wins)
- Address update after cancellation

**End-to-End Scenarios**:
- Complete flow with all operations (update, approve, complete)
- Workflow completion within time limits

### Test Configuration

Tests use Temporal's `WorkflowEnvironment` with time-skipping for fast execution:

```python
@pytest_asyncio.fixture
async def worker_and_client():
    async with await WorkflowEnvironment.start_time_skipping() as env:
        # Setup workers for both task queues
        # Return client and workers
        yield env.client, (orders_worker, shipping_worker)
```

### Handling Flaky Behavior

Tests are designed to handle `flaky_call()` which simulates real-world failures:

- **33% chance**: Raises RuntimeError
- **67% chance**: Sleeps for 300 seconds (timeout)

Tests accept both outcomes as valid:
- Success: Activities eventually pass after retries
- Expected Failure: All 3 retry attempts exhausted

This demonstrates Temporal's retry mechanism working correctly.

### Running Tests with Docker

```bash
# Run tests in Docker container
docker-compose run --rm api pytest tests/ -v

# Run specific test file
docker-compose run --rm api pytest tests/test_integration_complete.py -v
```

### Test Database

Tests use the same PostgreSQL instance but with isolated workflow IDs to prevent conflicts. Each test uses unique order IDs (e.g., `test-complete-001`, `test-cancel-001`).

## Project Structure

```
.
├── app/
│   ├── activities/
│   │   ├── order.py              # Order-related activities
│   │   └── shipping.py           # Shipping-related activities
│   ├── api/
│   │   └── main.py               # FastAPI REST endpoints
│   ├── stubs/
│   │   ├── business.py           # Business logic with DB operations
│   │   └── flaky.py              # Simulates failures for testing
│   ├── utils/
│   │   └── status_map.py         # Status code mappings
│   ├── workers/
│   │   ├── worker_orders.py      # Order workflow worker
│   │   └── worker_shipping.py    # Shipping workflow worker
│   ├── workflows/
│   │   ├── order_workflow.py     # Main OrderWorkflow
│   │   └── shipping_workflow.py  # ShippingWorkflow (child)
│   ├── config.py                 # Configuration settings
│   ├── db.py                     # Database connection setup
│   ├── logging_config.py         # Logging configuration
│   ├── models.py                 # Database models
│   └── schemas.py                # Pydantic schemas
├── migrations/
│   └── 001_init.sql              # Initial database schema
├── tests/
│   ├── conftest.py               # Test fixtures
│   └── test_*.py                 # Test files
├── docker-compose.yml            # Docker services configuration
├── Dockerfile                    # Container image definition
├── requirements.txt              # Python dependencies
├── Makefile                      # Convenience commands
└── README.md                     # This file
```

## Configuration

### Environment Variables

Configure the application via environment variables (see `.env` file):

```bash
# Database
POSTGRES_USER=trellis
POSTGRES_PASSWORD=trellis
POSTGRES_DB=trellisdb
HOST_DB_PORT=5432

# Temporal
TEMPORAL_TARGET=temporal:7233

# Task Queues
ORDERS_TASK_QUEUE=orders-tq
SHIPPING_TASK_QUEUE=shipping-tq

# API Configuration
API_HOST=0.0.0.0
API_PORT=8080

# Application (optional)
LOG_LEVEL=INFO
```

**Database URL format**:
```
postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}
```

For local development:
```
postgresql+asyncpg://trellis:trellis@localhost:5432/trellisdb
```

### Retry Policy Configuration

Activity retry configuration in `app/workflows/order_workflow.py`:

```python
ACT_OPTS = ActivityOptions(
    start_to_close_timeout=timedelta(seconds=1),
    schedule_to_close_timeout=timedelta(seconds=3),
    maximum_attempts=3,
    retry_policy=RetryPolicy(
        non_retryable_error_types=[]
    )
)
```

### Workflow Timeouts

```python
# Execution timeout for order workflow
execution_timeout=timedelta(minutes=10)

# Wait condition timeout for manual approval
await workflow.wait_condition(
    lambda: self.approved or self.canceled,
    timeout=timedelta(seconds=4)
)
```

## Development

### Local Development Setup

```bash
# 1. Clone repository
git clone <repository-url>
cd trellis-temporal-takehome

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Start infrastructure (Temporal and PostgreSQL)
docker-compose up -d temporal db

# Wait for database to be ready
sleep 5

# 5. Apply migrations
psql -h localhost -U trellis -d trellisdb -W -f migrations/001_init.sql
# Password: trellis

# 6. Set environment variables for local development
export DATABASE_URL="postgresql+asyncpg://trellis:trellis@localhost:5432/trellisdb"
export TEMPORAL_TARGET="localhost:7233"
export ORDERS_TASK_QUEUE="orders-tq"
export SHIPPING_TASK_QUEUE="shipping-tq"

# 7. Run workers (separate terminals)
python -m app.workers.worker_orders
python -m app.workers.worker_shipping

# 8. Run API (another terminal)
uvicorn app.api.main:app --reload --host 0.0.0.0 --port 8080
```

### Using Makefile

The Makefile is currently empty, but you can use docker-compose commands directly:

```bash
# Start all services
docker-compose up -d

# View logs for all services
docker-compose logs -f

# View logs for specific service
docker-compose logs -f api
docker-compose logs -f worker_orders
docker-compose logs -f worker_shipping

# Stop all services
docker-compose down

# Stop and remove volumes (clean slate)
docker-compose down -v

# Run tests in container
docker-compose run --rm api pytest tests/ -v

# Rebuild containers after code changes
docker-compose up -d --build
```

## Troubleshooting

### Workers not processing workflows

1. Check workers are running: `docker-compose ps`
2. Verify task queue names match between workflow start and worker registration
3. Check worker logs: `docker-compose logs worker_orders`

### Database connection errors

1. Ensure PostgreSQL is running: `docker-compose ps db`
2. Verify DATABASE_URL environment variable matches: `postgresql+asyncpg://trellis:trellis@localhost:5432/trellisdb`
3. Check migrations applied: `docker exec -it trellis-db psql -U trellis -d trellisdb -c "\dt"`
4. Check database logs: `docker-compose logs db`

### Workflows failing with "Activity timeout"

This is expected behavior with `flaky_call()` enabled. The system demonstrates fault tolerance by:
- Retrying activities up to 3 times
- Logging all retry attempts
- Eventually failing if all retries exhausted

### Cannot access Temporal Web UI

1. Ensure Temporal server is running: `docker-compose ps temporal`
2. Check port 8233 is not in use: `lsof -i :8233`
3. Access via: http://localhost:8233

### Cannot access FastAPI

1. Ensure API is running and healthy: `docker-compose ps api`
2. Check API logs: `docker-compose logs api`
3. Check port 8080 is not in use: `lsof -i :8080`
4. Access via: http://localhost:8080/docs


## License

This project is created for educational and demonstration purposes.trellis-temporal-takehome
Temporal’s open‑source SDK and dev server to orchestrate an Order Lifecycle.
