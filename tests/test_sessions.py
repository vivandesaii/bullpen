import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException
from app.services.sessions import create_session, get_session, delete_session, delete_all_sessions


@pytest.mark.asyncio
async def test_create_session():
    with patch("app.services.sessions.redis_client") as mock_redis: # the faker replaces redis_client with mock_redis
        mock_redis.setex = AsyncMock()
        mock_redis.sadd = AsyncMock()

        session_id = await create_session(user_id=1)

        assert isinstance(session_id, str)
        assert len(session_id) > 0

        mock_redis.setex.assert_called_once_with(f"session:{session_id}", 86400, "1") # was setex called with these

        mock_redis.sadd.assert_called_once_with("user_sessions:1", session_id) # was sadd called with these



@pytest.mark.asyncio
async def test_get_session_valid():
    with patch("app.services.sessions.redis_client") as mock_redis:
        mock_redis.get = AsyncMock(return_value="1")
        mock_redis.expire = AsyncMock()

        result = await get_session("some-token")

        assert result == 1
        mock_redis.get.assert_called_once_with("session:some-token")


@pytest.mark.asyncio
async def test_get_session_invalid():
    with patch("app.services.sessions.redis_client") as mock_redis:
        mock_redis.get = AsyncMock(return_value=None)

        with pytest.raises(HTTPException) as exc_info:
            await get_session("bad-token")

        assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_delete_session_valid():
    with patch("app.services.sessions.redis_client") as mock_redis:
        mock_redis.delete = AsyncMock()
        mock_redis.srem = AsyncMock()

        result = await delete_session("some-token",42)

        mock_redis.delete.assert_called_once_with("session:some-token")
        mock_redis.srem.assert_called_once_with("user_sessions:42", "some-token")
