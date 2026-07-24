from fastapi import Depends, HTTPException

from app.redis_client import redis_client  # Reuse the shared Redis pool (settings.redis_url) instead of a hardcoded localhost client
from app.services.sessions import get_session

async def check_rate_limit(user_id: int = Depends(get_session), limit: int = 100, window: int = 60):
    """
    Checks if the client has exceeded the rate limit.

    user_id comes from the session dependency (server-side), so clients
    cannot spoof whose rate limit they consume.
    """
    key = f"rate_limit:{user_id}"

    async with redis_client.pipeline(transaction=True) as pipe: # transaction=True ensures that the commands are executed atomically
        pipe.incr(key) # Increment the count for the user
        pipe.expire(key, window, nx=True) # Only set the TTL if the key has none, so the window doesn't slide forward on every request
        results = await pipe.execute() # Execute the pipeline commands atomically

    count = results[0]

    if count > limit:
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Try again later.")
