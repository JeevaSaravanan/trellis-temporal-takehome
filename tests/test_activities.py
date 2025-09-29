"""Unit tests for Temporal activities."""
import pytest
from unittest.mock import AsyncMock, patch

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


class TestOrderActivities:
    """Test order-related activities."""

    @pytest.mark.asyncio
    async def test_receive_order_activity(self, mock_business_functions, sample_order_data):
        """Test order reception activity."""
        order_id = sample_order_data["order_id"]
        items = sample_order_data["items"]
        address = sample_order_data["address"]
        
        with patch('app.activities.order.db_session') as mock_session:
            mock_session.return_value.__aenter__ = AsyncMock()
            mock_session.return_value.__aexit__ = AsyncMock()
            
            result = await receive_order_activity(order_id, items, address)
            
            assert result["order_id"] == order_id
            assert result["status"] == "received"

    @pytest.mark.asyncio
    async def test_validate_order_activity(self, mock_business_functions, sample_order_data):
        """Test order validation activity."""
        order = {
            "order_id": sample_order_data["order_id"],
            "items": sample_order_data["items"],
            "address": sample_order_data["address"]
        }
        
        with patch('app.activities.order.db_session') as mock_session:
            mock_session.return_value.__aenter__ = AsyncMock()
            mock_session.return_value.__aexit__ = AsyncMock()
            
            result = await validate_order_activity(order)
            
            assert result is True

    @pytest.mark.asyncio
    async def test_charge_payment_activity(self, mock_business_functions, sample_order_data):
        """Test payment charging activity."""
        order = {
            "order_id": sample_order_data["order_id"],
            "items": sample_order_data["items"],
            "address": sample_order_data["address"]
        }
        payment_id = sample_order_data["payment_id"]
        
        with patch('app.activities.order.db_session') as mock_session:
            mock_session.return_value.__aenter__ = AsyncMock()
            mock_session.return_value.__aexit__ = AsyncMock()
            
            result = await charge_payment_activity(order, payment_id)
            
            assert result["payment_id"] == payment_id
            assert result["status"] == "charged"

    @pytest.mark.asyncio
    async def test_mark_shipped_activity(self, mock_business_functions, sample_order_data):
        """Test order shipping marking activity."""
        order = {
            "order_id": sample_order_data["order_id"],
            "items": sample_order_data["items"],
            "address": sample_order_data["address"]
        }
        
        with patch('app.activities.order.db_session') as mock_session:
            mock_session.return_value.__aenter__ = AsyncMock()
            mock_session.return_value.__aexit__ = AsyncMock()
            
            result = await mark_shipped_activity(order)
            
            assert result == "SHIP123"


class TestShippingActivities:
    """Test shipping-related activities."""

    @pytest.mark.asyncio
    async def test_prepare_package_activity(self, mock_business_functions, sample_order_data):
        """Test package preparation activity."""
        order = {
            "order_id": sample_order_data["order_id"],
            "items": sample_order_data["items"],
            "address": sample_order_data["address"]
        }
        
        with patch('app.activities.shipping.db_session') as mock_session:
            mock_session.return_value.__aenter__ = AsyncMock()
            mock_session.return_value.__aexit__ = AsyncMock()
            
            result = await prepare_package_activity(order)
            
            assert result == "PKG123"

    @pytest.mark.asyncio
    async def test_dispatch_carrier_activity(self, mock_business_functions, sample_order_data):
        """Test carrier dispatch activity."""
        order = {
            "order_id": sample_order_data["order_id"],
            "items": sample_order_data["items"],
            "address": sample_order_data["address"]
        }
        
        with patch('app.activities.shipping.db_session') as mock_session:
            mock_session.return_value.__aenter__ = AsyncMock()
            mock_session.return_value.__aexit__ = AsyncMock()
            
            result = await dispatch_carrier_activity(order)
            
            assert result == "CARRIER456"

    @pytest.mark.asyncio
    async def test_dispatch_carrier_activity_failure(self, mock_business_functions, sample_order_data):
        """Test carrier dispatch activity with failure."""
        from app.stubs import business
        
        # Make the carrier dispatch fail
        business.carrier_dispatched.side_effect = Exception("Carrier service unavailable")
        
        order = {
            "order_id": sample_order_data["order_id"],
            "items": sample_order_data["items"],
            "address": sample_order_data["address"]
        }
        
        with patch('app.activities.shipping.db_session') as mock_session:
            mock_session.return_value.__aenter__ = AsyncMock()
            mock_session.return_value.__aexit__ = AsyncMock()
            
            with pytest.raises(Exception, match="Carrier service unavailable"):
                await dispatch_carrier_activity(order)
