from fastapi import APIRouter, HTTPException, Depends
from app.services.sessions import get_session
from app.services.rate_limit import check_rate_limit
from app.services.cache import get_cached, set_cache


router = APIRouter(prefix="/portfolio", tags=["portfolio"])

@router.get("/me", dependencies=[Depends(check_rate_limit)])  # check_rate_limit resolves the session itself, so the limit is per authenticated user
async def get_portfolio(user_id: int = Depends(get_session)):
    """
    Endpoint to fetch the portfolio of a given user.
    """
    # Redis check for cached portfolio data
    cached_portfolio = await get_cached(f"portfolio:{user_id}")
    if cached_portfolio is not None:
        return {"user_id": user_id, "portfolio": cached_portfolio, "source": "cache"}
    
    # If not cached, fetch from database (simulated here as an empty portfolio)
    # TODO: fetch from postgres 

    # Cache the portfolio data in Redis with a TTL of 60 seconds
    await set_cache(f"portfolio:{user_id}", {}, ttl=60)
    # Return the portfolio data
    return {"user_id": user_id, "portfolio": {}, "source": "database"}


