from typing import Optional
from app.redis_client import redis_client
from app.db.connection import get_connection, release_connection

LEADERBOARD_KEY = "leaderboard:returns"

async def update_user_return(user_id: int, return_pct: float) -> None:
    """Updates the user's return percentage in the leaderboard."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO leaderboard_snapshots (user_id, return_pct, updated_at)
            VALUES (%s, %s, NOW())
            ON CONFLICT (user_id) DO UPDATE
            SET return_pct = EXCLUDED.return_pct, updated_at = NOW()
            """,
            (user_id, return_pct)
        )
        conn.commit()
    finally:
        cursor.close()
        release_connection(conn)

    await redis_client.zadd(LEADERBOARD_KEY, {str(user_id): return_pct}) # Add or update the user's score in the sorted set

async def _get_usernames(user_ids: list[int]) -> dict[int, str]:
    if not user_ids:
        return {}

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT id, username FROM users WHERE id = ANY(%s)",
            (user_ids,)
        )
        return {row["id"]: row["username"] for row in cursor.fetchall()}
    finally:
        cursor.close()
        release_connection(conn)

async def get_top_n(n: int) -> list[dict]:
    results = await redis_client.zrevrange(LEADERBOARD_KEY, 0, n - 1, withscores=True) # Get the top N users with their scores
    parsed = [(int(user_id), score) for user_id, score in results]
    usernames = await _get_usernames([user_id for user_id, _ in parsed])
    return [
        {"user_id": user_id, "username": usernames.get(user_id), "return_pct": score}
        for user_id, score in parsed
    ]

async def get_user_rank(user_id: int) -> Optional[dict]:
    rank = await redis_client.zrevrank(LEADERBOARD_KEY, str(user_id))
    score = await redis_client.zscore(LEADERBOARD_KEY, str(user_id))

    if rank is None:
        return None

    usernames = await _get_usernames([user_id])

    return {
        "user_id": user_id,
        "username": usernames.get(user_id),
        "rank": rank + 1,
        "return_pct": score
    }

