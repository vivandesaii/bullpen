# get_cached, set_cached, invalidate_cache

import pytest
from unittest.mock import AsyncMock, patch
from app.services.cache import get_cached, set_cache, invalidate_cache

@pytest.mark.asyncio
async def test_get_cached_hit():
    with patch("app.services.cache.redis_client") as mock_redis:
        mock_redis.get = AsyncMock(return_value='{"price": 333.02}')
        
        result = await get_cached("price:AAPL")
        
        assert result == {"price": 333.02}
        mock_redis.get.assert_called_once_with("price:AAPL")


@pytest.mark.asyncio
async def test_get_cached_miss():
    with patch("app.services.cache.redis_client") as mock_redis:
        mock_redis.get = AsyncMock(return_value=None)

        result = await get_cached("Vivan")

        assert result == None
        mock_redis.get.assert_called_once_with("Vivan")


@pytest.mark.asyncio
async def test_set_cache():
    with patch("app.services.cache.redis_client") as mock_redis:
        mock_redis.setex = AsyncMock()

        await set_cache("price:AAPL", {"price": 333.02}, ttl=5)

        mock_redis.setex.assert_called_once_with("price:AAPL", 5, '{"price": 333.02}')


@pytest.mark.asyncio
async def test_invalidate_cache():
    with patch("app.services.cache.redis_client") as mock_redis:
        mock_redis.delete = AsyncMock()

        await invalidate_cache("price:AAPL")

        mock_redis.delete.assert_called_once_with("price:AAPL")