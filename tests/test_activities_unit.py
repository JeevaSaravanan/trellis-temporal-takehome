"""Unit tests for activities using Temporal's ActivityEnvironment."""
import pytest
from unittest.mock import patch, AsyncMock
from temporalio.testing import ActivityEnvironment

from app.activities.order import (
    receive_order_activity,
    validate_order_activity,
    charge_payment_activity,
)


class TestActivitiesWithActivityEnvironment:
    """Test activities using Temporal's ActivityEnvironment for isolation."""

    @pytest.mark.asyncio
    async def test_receive_order_activity_isolated(self):
        """Test order reception activity in isolation."""
        # Mock the business function directly to match actual return format
        with patch('app.stubs.business.order_received', new_callable=AsyncMock) as mock_order_received:
            mock_order_received.return_value = {
                "order_id": "test-123",
                "items": [],
                "address": {}
            }
            
            # Mock the database session
            with patch('app.activities.order.db_session') as mock_db:
                mock_session = AsyncMock()
                mock_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)
                mock_db.return_value.__aexit__ = AsyncMock(return_value=None)
                
                # Run activity in ActivityEnvironment
                activity_env = ActivityEnvironment()
                
                async def run_activity():
                    return await receive_order_activity("test-123", [], {})
                
                result = await activity_env.run(run_activity)
                
                assert result["order_id"] == "test-123"
                assert "items" in result
                assert "address" in result
                mock_order_received.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_order_activity_isolated(self):
        """Test order validation activity in isolation."""
        with patch('app.stubs.business.order_validated', new_callable=AsyncMock) as mock_validated:
            mock_validated.return_value = True
            
            with patch('app.activities.order.db_session') as mock_db:
                mock_session = AsyncMock()
                mock_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)
                mock_db.return_value.__aexit__ = AsyncMock(return_value=None)
                
                activity_env = ActivityEnvironment()
                
                async def run_activity():
                    return await validate_order_activity({"order_id": "test-123"})
                
                result = await activity_env.run(run_activity)
                
                assert result is True
                mock_validated.assert_called_once()

    @pytest.mark.asyncio
    async def test_charge_payment_activity_isolated(self):
        """Test payment charging activity in isolation."""
        with patch('app.stubs.business.payment_charged', new_callable=AsyncMock) as mock_charged:
            mock_charged.return_value = {
                "payment_id": "pay-456",
                "status": "charged",
                "amount": 100.0
            }
            
            with patch('app.activities.order.db_session') as mock_db:
                mock_session = AsyncMock()
                mock_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)
                mock_db.return_value.__aexit__ = AsyncMock(return_value=None)
                
                activity_env = ActivityEnvironment()
                
                async def run_activity():
                    return await charge_payment_activity({"order_id": "test-123"}, "pay-456")
                
                result = await activity_env.run(run_activity)
                
                assert result["payment_id"] == "pay-456"
                assert result["status"] == "charged"
                mock_charged.assert_called_once()