import json
from typing import Any, Dict, Optional
from app.redis_client import redis_client

async def cached(key: str) -> Optional[Dict]:
    """Fetches a value from Redis cache and returns it as a dictionary if it exists."""

    value = await redis_client.get(key)
    if value is None:
        return None
    return json.loads(value)

async def set_cache(key: str, value: Any, ttl: int = 3600) -> None:
    """Sets a value in Redis cache with an optional expiration time."""
    
    await redis_client.setex(key, ttl, json.dumps(value)) # Store the value as a JSON string with an expiration time (TTL) in seconds


async def invalidate_cache(key: str) -> None:
    """Invalidates a cache entry by deleting the key from Redis."""
    
    await redis_client.delete(key) # Delete the key from Redis to invalidate the cache
