import json
from typing import Any, Dict, Optional
import secrets
from fastapi import Header, HTTPException
from app.redis_client import redis_client

SESSION_TTL = 86400 # Session time-to-live in seconds (24 hours)

async def create_session(user_id: int) -> str:
    """Creates a new session for the given user ID and returns the session token."""

    session_id = secrets.token_urlsafe(32) # Generate a secure random session token
    key = f"session:{session_id}"

    await redis_client.setex(key, SESSION_TTL, str(user_id)) # Store the session in Redis with an expiration time (TTL)
    await redis_client.sadd(f"user_sessions:{user_id}", session_id) # Add the session ID to the set of sessions for the user

    return session_id

async def get_session(session_id: str = Header(alias="X-Session-Id")) -> int:
    """FastAPI dependency: resolves the X-Session-Id header to a user ID.

    Raises 401 if the header is missing (FastAPI handles that) or the session
    is expired/invalid, so routes can rely on always getting a valid user ID.
    """

    key = f"session:{session_id}"
    value = await redis_client.get(key)
    if value is None:
        raise HTTPException(status_code=401, detail="Invalid or expired session.")

    await redis_client.expire(key, SESSION_TTL) # Refresh the session expiration time on access
    return int(value)

async def delete_session(session_id: str, user_id: int) -> None:
    """Deletes the session associated with the given session token."""

    await redis_client.delete(f"session:{session_id}") # Delete the session key from Redis
    await redis_client.srem(f"user_sessions:{user_id}", session_id) # Remove the session ID from the set of sessions for the user

async def delete_all_sessions(user_id: int) -> None:
    """Deletes all sessions associated with the given user ID."""

    session_ids = await redis_client.smembers(f"user_sessions:{user_id}") # Get all session IDs for the user

    for session_id in session_ids:
        await redis_client.delete(f"session:{session_id}") # Delete each session key from Redis
    
    await redis_client.delete(f"user_sessions:{user_id}") # Delete the set of sessions for the user from Redis