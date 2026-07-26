import boto3, json, time, logging
import asyncio
import yfinance as yf
from app.config import settings
from app.services.cache import invalidate_cache
from app.services.leaderboard import update_user_return
from app.utils.retry import with_retry
from app.db.connection import get_connection


logger = logging.getLogger("trade_processor") # Configure a logger for the trade processor to log messages and errors

STARTING_BALANCE = 100000.00  # Must match users.balance default in app/db/migrations/001_create_tables.sql

sqs = boto3.client(
    'sqs',
    endpoint_url=settings.aws_endpoint_url,
    aws_access_key_id=settings.aws_access_key_id,
    aws_secret_access_key=settings.aws_secret_access_key,
    region_name=settings.aws_region
)

def _mark_trade_failed(cursor, trade_id: str) -> None:
    cursor.execute(
        "UPDATE trades SET status = 'failed', executed_at = NOW() WHERE trade_id = %s",
        (trade_id,)
    )


def execute_trade(trade: dict, current_price: float) -> bool:
    """
    Executes a validated trade against Postgres: checks funds/holdings,
    updates balance and holdings, and marks the trade completed or failed.
    Row locks on users/holdings keep concurrent trades for the same user serialized.
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT balance FROM users WHERE id = %s FOR UPDATE", (trade['user_id'],))
        user = cursor.fetchone()
        if user is None:
            logger.error(f"User {trade['user_id']} not found for trade {trade['trade_id']}")
            _mark_trade_failed(cursor, trade['trade_id'])
            conn.commit()
            return False

        balance = float(user['balance'])
        cost = current_price * trade['quantity']

        cursor.execute(
            "SELECT quantity, avg_price FROM holdings WHERE user_id = %s AND symbol = %s FOR UPDATE",
            (trade['user_id'], trade['symbol'])
        )
        holding = cursor.fetchone()

        if trade['direction'] == 'buy':
            if balance < cost:
                logger.error(f"Insufficient balance for trade {trade['trade_id']}: has {balance}, needs {cost}")
                _mark_trade_failed(cursor, trade['trade_id'])
                conn.commit()
                return False

            new_balance = balance - cost
            if holding is None:
                cursor.execute(
                    "INSERT INTO holdings (user_id, symbol, quantity, avg_price) VALUES (%s, %s, %s, %s)",
                    (trade['user_id'], trade['symbol'], trade['quantity'], current_price)
                )
            else:
                new_quantity = holding['quantity'] + trade['quantity']
                new_avg_price = ((holding['quantity'] * float(holding['avg_price'])) + cost) / new_quantity
                cursor.execute(
                    "UPDATE holdings SET quantity = %s, avg_price = %s, updated_at = NOW() WHERE user_id = %s AND symbol = %s",
                    (new_quantity, new_avg_price, trade['user_id'], trade['symbol'])
                )

        else:  # sell
            if holding is None or holding['quantity'] < trade['quantity']:
                logger.error(f"Insufficient holdings for trade {trade['trade_id']}")
                _mark_trade_failed(cursor, trade['trade_id'])
                conn.commit()
                return False

            new_balance = balance + cost
            new_quantity = holding['quantity'] - trade['quantity']
            if new_quantity == 0:
                cursor.execute(
                    "DELETE FROM holdings WHERE user_id = %s AND symbol = %s",
                    (trade['user_id'], trade['symbol'])
                )
            else:
                cursor.execute(
                    "UPDATE holdings SET quantity = %s, updated_at = NOW() WHERE user_id = %s AND symbol = %s",
                    (new_quantity, trade['user_id'], trade['symbol'])
                )

        cursor.execute("UPDATE users SET balance = %s WHERE id = %s", (new_balance, trade['user_id']))
        cursor.execute(
            "UPDATE trades SET status = 'completed', executed_at = NOW() WHERE trade_id = %s",
            (trade['trade_id'],)
        )

        cursor.execute(
            "SELECT COALESCE(SUM(quantity * avg_price), 0) AS holdings_value FROM holdings WHERE user_id = %s",
            (trade['user_id'],)
        )
        holdings_value = float(cursor.fetchone()['holdings_value'])
        conn.commit()

        total_value = new_balance + holdings_value
        return_pct = ((total_value - STARTING_BALANCE) / STARTING_BALANCE) * 100
        asyncio.run(update_user_return(trade['user_id'], return_pct))

        return True

    except Exception as e:
        conn.rollback()
        logger.error(f"Error executing trade {trade['trade_id']}: {e}")
        return False

    finally:
        cursor.close()
        conn.close()


def process_trade(trade: dict) -> bool:
    """
    Process a trade message from the SQS queue.
    This function simulates trade processing logic, which could include validation, database operations, etc.
    """

    try:

        # Log the trade being processed for auditing and debugging purposes
        logger.info(f"Processing: {trade['symbol']} {trade['quantity']} {trade['direction']}")  # Log the incoming trade for auditing and debugging purposes
        
        # Validate trade (e.g., quantity > 0, direction is 'buy' or 'sell', symbol is valid, etc.)
        if trade['quantity'] <= 0 or trade['direction'] not in ['buy', 'sell'] or not trade['symbol'] or trade['quantity'] >= 10000:
            logger.error(f"Invalid trade quantity: {trade['quantity']} for trade {trade}")
            return False
        
        # Fetch current price via yfinance
        ticker = yf.Ticker(trade['symbol'])
        current_price = ticker.fast_info.last_price  # Fetch the current price of the stock using yfinance's fast_info for efficiency

        if current_price is None:
            logger.error(f"Could not fetch price for {trade['symbol']}")
            return False


        if not execute_trade(trade, current_price):
            return False

        # Invalidate Redis cache for this user's portfolio
        # sync function so we use asyncio.run to call the async invalidate_cache function
        asyncio.run(invalidate_cache(f"portfolio:{trade['user_id']}"))  


        return True  # Return True to indicate successful processing of the trade

    except Exception as e:
        logger.error(f"Error processing trade {trade}: {e}")
        return False

def poll_and_process():
    logger.info("Trade processor started. Polling SQS for messages...")
    while True:
        try:
            response = sqs.receive_message(
                QueueUrl=settings.sqs_queue_url,
                MaxNumberOfMessages=10,
                WaitTimeSeconds=20,
                VisibilityTimeout=300
            )

            messages = response.get("Messages", [])
            for message in messages:
                body = json.loads(message["Body"])
                receipt = message["ReceiptHandle"]

                # Wrap processing in with_retry: transient failures (network, yfinance
                # timeouts) are retried with exponential backoff; PermanentFailure
                # subclasses raise immediately and are not retried.
                # process_trade signals failure by returning False, not raising, so
                # _process_or_raise converts False into an exception with_retry can see.
                def _process_or_raise():
                    if not process_trade(body):
                        raise RuntimeError("process_trade returned False")

                try:
                    with_retry(
                        _process_or_raise,
                        max_retries=3,
                        base_delay=1.0,
                        operation_name=f"trade:{body.get('trade_id', 'unknown')}"
                    )
                    success = True
                except Exception:
                    success = False  # Retries exhausted or permanent failure — leave message for SQS redelivery

                if success:
                    sqs.delete_message(
                        QueueUrl=settings.sqs_queue_url,
                        ReceiptHandle=receipt
                    )
                    logger.info("Trade processed and deleted")
                else:
                    logger.warning("Trade failed — will retry")
        except Exception as e:
            logger.error(f"Polling error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    poll_and_process()  # Start the trade processor when the script is run directly