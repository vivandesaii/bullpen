import asyncio
import time
from fastapi import APIRouter, HTTPException, Depends
from app.services.cache import get_cached, set_cache
from app.services.rate_limit import check_rate_limit
from app.services.sessions import get_session
import yfinance as yf
from pydantic import BaseModel

router = APIRouter(prefix="/prices", tags=["prices"])

class PriceResponse(BaseModel):
    symbol: str
    price: float
    source: str
    lookup_ms: float

class TickerResult(BaseModel):
    symbol: str
    name: str | None
    exchange: str | None

# Registered before /{symbol} so "search" is never swallowed as a ticker symbol.
@router.get("/search", response_model=list[TickerResult], dependencies=[Depends(check_rate_limit)])
async def search_tickers(q: str, user_id: int = Depends(get_session)):
    """
    Endpoint to search for ticker symbols by company name or partial symbol,
    used to power the frontend's autocomplete dropdown.
    """
    def _search():
        results = yf.Search(q, max_results=8)
        return results.quotes

    quotes = await asyncio.to_thread(_search)  # yf.Search does a blocking network call

    return [
        {
            "symbol": r.get("symbol"),
            "name": r.get("longname") or r.get("shortname"),
            "exchange": r.get("exchange")
        }
        for r in quotes if r.get("symbol")
    ]

@router.get("/{symbol}", response_model=PriceResponse, dependencies=[Depends(check_rate_limit)]) # check_rate_limit resolves the session itself, so the limit is per authenticated user
async def get_price(symbol: str, user_id: int = Depends(get_session)):
    """
    Endpoint to fetch the current price of a given stock symbol.
    """
    symbol = symbol.upper()  # Normalize the symbol to uppercase for consistency

    start = time.perf_counter()

    # Check Redis cache first
    cached_price = await get_cached(f"price:{symbol}")

    # Cache hit so we return immediately
    if cached_price is not None:
        lookup_ms = (time.perf_counter() - start) * 1000
        return {"symbol": symbol, "price": cached_price["price"], "source": "cache", "lookup_ms": lookup_ms}
    # Else cache miss, fetch from yfinance
    ticker = yf.Ticker(symbol)
    current_price = ticker.fast_info.last_price  # Fetch the current price of the stock using yfinance's fast_info for efficiency

    if current_price is None:
        raise HTTPException(status_code=404, detail=f"Could not fetch price for {symbol}")
    # Write to cache with 5s TTL
    await set_cache(f"price:{symbol}", {"price": current_price}, ttl=5)
    lookup_ms = (time.perf_counter() - start) * 1000
    return {"symbol": symbol, "price": current_price, "source": "yfinance", "lookup_ms": lookup_ms}
    