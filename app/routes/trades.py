import time
import uuid
from fastapi import APIRouter, Depends, HTTPException
from typing import Literal
from pydantic import BaseModel
from datetime import datetime, timezone
from app.services.sqs_service import send_trade_message
from app.services.sessions import get_session
from app.services.rate_limit import check_rate_limit
from app.db.connection import get_connection

router = APIRouter(prefix="/trades", tags=["trades"])  # Create a new router for trade-related endpoints

class TradeRequest(BaseModel):
    """Pydantic model for validating trade request payloads."""
    symbol: str
    quantity: int
    direction: Literal["buy", "sell"]  # "buy" or "sell"
    price: float

@router.post("", dependencies=[Depends(check_rate_limit)])  # check_rate_limit resolves the session itself, so the limit is per authenticated user
async def submit_trade(trade_request: TradeRequest, user_id: int = Depends(get_session)):
    """
    Endpoint to submit a trade request.
    Validates the request, sends it to the SQS queue, and returns a confirmation response.
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:

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

        cursor.execute(
            """
            INSERT INTO trades (trade_id, user_id, symbol, quantity, price, direction, status, submitted_at)
            VALUES (%s, %s, %s, %s, %s, %s, 'pending', %s)
            RETURNING id
            """,
            (
                trade_data["trade_id"],
                user_id,
                trade_request.symbol,
                trade_request.quantity,
                trade_request.price,
                trade_request.direction,
                trade_data["submitted_at"]
            )
        )
        conn.commit()
        
        await send_trade_message(trade_data, user_id)  # Send the trade message to SQS asynchronously

        return {"status": "queued","trade_id": trade_data["trade_id"], "message": "Trade Submitted. Processing Shortly."}  # Return a confirmation response to the client

    except HTTPException:
        raise
    
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail="Failed to submit trade.")

    finally:
        cursor.close()
        conn.close()
