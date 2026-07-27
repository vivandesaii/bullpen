# Test under limit and over limit

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException
from app.services.rate_limit import check_rate_limit

def make_mock_pipeline(count):
    """Helper to mock the Redis pipeline context manager."""
    mock_pipe = AsyncMock()
    mock_pipe.execute = AsyncMock(return_value=[count, True])
    mock_pipe.incr = AsyncMock()
    mock_pipe.expire = AsyncMock()
    
    mock_pipeline_ctx = AsyncMock()
    mock_pipeline_ctx.__aenter__ = AsyncMock(return_value=mock_pipe)
    mock_pipeline_ctx.__aexit__ = AsyncMock(return_value=False)
    
    return mock_pipeline_ctx

@pytest.mark.asyncio
async def test_under_rate_limit():
    mock_request = MagicMock()
    mock_request.client.host = "127.0.0.1"

    with patch("app.services.rate_limit.redis_client") as mock_redis:
        mock_redis.pipeline = MagicMock(return_value=make_mock_pipeline(count=5))
        
        # Should not raise — 5 requests, limit is 100
        await check_rate_limit(request=mock_request, limit=100, window=60, user_id=1)

@pytest.mark.asyncio
async def test_over_rate_limit():
    mock_request = MagicMock()
    mock_request.client.host = "127.0.0.1"

    with patch("app.services.rate_limit.redis_client") as mock_redis:
        mock_redis.pipeline = MagicMock(return_value=make_mock_pipeline(count=101))
        
        with pytest.raises(HTTPException) as exc_info:
            await check_rate_limit(request=mock_request, limit=100, window=60, user_id=1)
        
        assert exc_info.value.status_code == 429
