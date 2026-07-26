from fastapi import APIRouter, HTTPException, Depends
from app.services.sessions import get_session
from app.services.rate_limit import check_rate_limit
from app.services.cache import get_cached, set_cache
from app.db.connection import get_connection


router = APIRouter(prefix="/portfolio", tags=["portfolio"])

@router.get("/me", dependencies=[Depends(check_rate_limit)])  # check_rate_limit resolves the session itself, so the limit is per authenticated user
async def get_portfolio(user_id: int = Depends(get_session)):
    """
    Endpoint to fetch the portfolio of a given user.
    """

    conn = get_connection()
    cursor = conn.cursor()

    try:

        # Redis check for cached portfolio data
        cached_portfolio = await get_cached(f"portfolio:{user_id}")
        if cached_portfolio is not None:
            return {"user_id": user_id, "portfolio": cached_portfolio, "source": "cache"}
    

        cursor.execute(
            """
            SELECT id, balance FROM users
            WHERE id = %s
            """,
            (user_id,)
        )

        user = cursor.fetchone()

        if user is None:
            raise HTTPException(status_code=404, detail="User not found.")

        cursor.execute(
            """
            SELECT symbol, quantity, avg_price FROM holdings
            WHERE user_id = %s
            """,
            (user_id,)
        )

        holdings = cursor.fetchall()

        portfolio = {
            "balance": float(user["balance"]),
            "holdings": [
            {
            "symbol": h["symbol"],
            "quantity": h["quantity"],
            "avg_price": float(h["avg_price"])
            }
            for h in holdings
            ]
        }

        # Cache the portfolio data in Redis with a TTL of 60 seconds
        await set_cache(f"portfolio:{user_id}", portfolio, ttl=60)
        # Return the portfolio data
        return {"user_id": user_id, "portfolio": portfolio, "source": "database"}

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to fetch portfolio.")

    finally:
        cursor.close()
        conn.close()


