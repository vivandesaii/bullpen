from typing import Optional
from app.redis_client import redis_client

LEADERBOARD_KEY = "leaderboard:returns"

async def update_user_return(user_id: int, return_pct: float) -> None:
    """Updates the user's return percentage in the leaderboard."""
    await redis_client.zadd(LEADERBOARD_KEY, {str(user_id): return_pct}) # Add or update the user's score in the sorted set

async def get_top_n(n: int) -> list[dict]:
    results = await redis_client.zrevrange(LEADERBOARD_KEY, 0, n - 1, withscores=True) # Get the top N users with their scores
    return [
        {"user_id": int(user_id), "return_pct": score} for user_id, score in results
    ]

async def get_user_rank(user_id: int) -> Optional[dict]:
    rank = await redis_client.zrevrank(LEADERBOARD_KEY, str(user_id))
    score = await redis_client.zscore(LEADERBOARD_KEY, str(user_id))
    
    if rank is None:
        return None
    
    return {
        "user_id": user_id,
        "rank": rank + 1,
        "return_pct": score
    }

