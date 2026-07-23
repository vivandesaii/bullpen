import time
import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from datetime import datetime, timezone
from app.services.sqs_service import send_trade_message
from app.services.sessions import get_session
from app.services.rate_limit import check_rate_limit

router = APIRouter(prefix="/trades", tags=["trades"])  # Create a new router for trade-related endpoints

class TradeRequest(BaseModel):
    """Pydantic model for validating trade request payloads."""
    symbol: str
    quantity: int
    direction: str  # "buy" or "sell"
    price: float

@router.post("/", dependencies=[Depends(check_rate_limit)])  # check_rate_limit resolves the session itself, so the limit is per authenticated user
async def submit_trade(trade_request: TradeRequest, user_id: int = Depends(get_session)):
    """
    Endpoint to submit a trade request.
    Validates the request, sends it to the SQS queue, and returns a confirmation response.
    """
    trade_data = {
        "trade_id": str(uuid.uuid4()),  # Unique ID so the worker can correlate retries/logs for this trade
        "user_id": user_id,  # get_session returns the user ID directly (raises 401 if the session is invalid)
        "symbol": trade_request.symbol,
        "quantity": trade_request.quantity,
        "price": trade_request.price,
        "direction": trade_request.direction,
        "submitted_at": datetime.now(timezone.utc).isoformat(),  # Human-readable timestamp for audit/logging
        "submitted_at_unix": time.time()  # Epoch seconds for the worker's stale-trade check
        }

    # TODO: Persist the trade submission to PostgreSQL before or immediately after enqueueing it.
    # TODO: Write the raw SQL insert for trade submissions, including status and audit fields.
    await send_trade_message(trade_data, user_id)  # Send the trade message to SQS asynchronously

    return {"status": "queued","trade_id": trade_data["trade_id"], "message": "Trade Submitted. Processing Shortly."}  # Return a confirmation response to the client