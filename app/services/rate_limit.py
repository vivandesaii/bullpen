import redis.asyncio as redis
from fastapi import HTTPException, Request

redis_client = redis.from_url("redis://localhost:6379", decode_responses=True)

async def check_rate_limit(user_id: str, limit: int = 100, window: int = 60):           
    """Checks if the client has exceeded the rate limit."""
    key = f"rate_limit:{user_id}"

    async with redis_client.pipeline(transaction=True) as pipe: # transaction=True ensures that the commands are executed atomically
        await pipe.incr(key) # Increment the count for the user
        await pipe.expire(key, window) # Set the expiration time for the key to enforce
        results = await pipe.execute() # Execute the pipeline commands atomically
    
    count, ttl = results[0], results[1]

    if ttl == -1: # If the key is new and has no expiration, set it
        await redis_client.expire(key, window)

    if count > limit:
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Try again later.")
    





    
