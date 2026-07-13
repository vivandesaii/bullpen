from fastapi import APIRouter, HTTPException, Depends
from app.services.cache import get_cached, set_cache
from app.services.rate_limit import check_rate_limit
from app.services.sessions import get_session
import yfinance as yf

router = APIRouter(prefix="/prices", tags=["prices"])

@router.get("/{symbol}", dependencies=[Depends(check_rate_limit)]) # check_rate_limit resolves the session itself, so the limit is per authenticated user
async def get_price(symbol: str, user_id: int = Depends(get_session)):
    """
    Endpoint to fetch the current price of a given stock symbol.
    """
    symbol = symbol.upper()  # Normalize the symbol to uppercase for consistency

    # Check Redis cache first
    cached_price = await get_cached(f"price:{symbol}")

    # Cache hit so we return immediately
    if cached_price is not None:
        return {"symbol": symbol, "price": cached_price["price"], "source": "cache"}
    # Else cache miss, fetch from yfinance
    ticker = yf.Ticker(symbol)
    current_price = ticker.fast_info.last_price  # Fetch the current price of the stock using yfinance's fast_info for efficiency

    if current_price is None:
        raise HTTPException(status_code=404, detail=f"Could not fetch price for {symbol}")
    # Write to cache with 5s TTL
    await set_cache(f"price:{symbol}", {"price": current_price}, ttl=5)
    return {"symbol": symbol, "price": current_price, "source": "yfinance"}
    