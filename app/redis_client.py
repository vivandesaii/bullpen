import redis.asyncio as redis
from app.config import settings

# Set up a Redis connection pool to manage connections efficiently
redis_client = redis.from_url(
    settings.redis_url,
    decode_responses=True, # Ensure that responses are decoded to strings
    max_connections=20 # Limit the number of connections in the pool to prevent resource exhaustion
)
