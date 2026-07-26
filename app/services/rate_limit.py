from typing import Optional
from fastapi import Depends, HTTPException, Request

from app.redis_client import redis_client  # Reuse the shared Redis pool (settings.redis_url) instead of a hardcoded localhost client
from app.services.sessions import get_optional_session

async def check_rate_limit(
    request: Request,
    limit: int = 100,
    window: int = 60,
    user_id: Optional[int] = Depends(get_optional_session)
):
    """
    Checks if the client has exceeded the rate limit.

    Authenticated requests are keyed by user_id (server-side, so clients
    cannot spoof whose rate limit they consume). Unauthenticated requests
    (e.g. register, login, where no session can exist yet) fall back to
    the client's IP address.
    """
    key = f"rate_limit:{user_id}" if user_id is not None else f"rate_limit:{request.client.host}"

    async with redis_client.pipeline(transaction=True) as pipe: # transaction=True ensures that the commands are executed atomically
        pipe.incr(key) # Increment the count for the user
        pipe.expire(key, window, nx=True) # Only set the TTL if the key has none, so the window doesn't slide forward on every request
        results = await pipe.execute() # Execute the pipeline commands atomically

    count = results[0]

    if count > limit:
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Try again later.")
