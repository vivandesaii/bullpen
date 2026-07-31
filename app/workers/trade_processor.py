# This file is the "worker" — a separate process from the API that sits and
# waits for trades to show up in the SQS queue, then actually executes them
# against the database. The API just queues trades; this file is what really
# moves money and stock between accounts.

import boto3, json, time, logging
import redis
import yfinance as yf
from app.config import settings
from app.utils.retry import with_retry
from app.db.connection import get_connection, release_connection

# The Redis sorted-set key where we keep everyone's leaderboard score.
LEADERBOARD_KEY = "leaderboard:returns"

# This worker runs as a plain synchronous script (no async/await), so we use the
# normal blocking Redis client here, not the async one the FastAPI app uses.
# Mixing async Redis with asyncio.run() inside a sync script caused
# "Event loop is closed" crashes, so we keep this worker fully synchronous.
sync_redis_client = redis.from_url(settings.redis_url, decode_responses=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s"
)
logger = logging.getLogger("trade_processor")  # Logger so we can see what the worker is doing in the container logs

# Every user starts with this much fake cash. Used to calculate "what % has this
# user gained or lost so far" for the leaderboard. Keep this in sync with the
# default value on users.balance in app/db/migrations/001_create_tables.sql.
STARTING_BALANCE = 100000.00

# The SQS client this worker uses to pull trade messages off the queue.
# endpoint_url points at LocalStack in dev instead of real AWS.
sqs = boto3.client(
    'sqs',
    endpoint_url=settings.aws_endpoint_url,
    aws_access_key_id=settings.aws_access_key_id,
    aws_secret_access_key=settings.aws_secret_access_key,
    region_name=settings.aws_region
)


def _update_leaderboard(user_id: int, return_pct: float) -> None:
    """
    Saves how well this user is doing (their return %) in two places:
    1. Postgres — the permanent record, survives Redis restarts.
    2. Redis sorted set — fast to read, used to serve the live leaderboard.
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # "Upsert": insert a new row for this user, or if one already exists,
        # just overwrite it with the latest numbers.
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
        # Always close the DB connection, whether the insert worked or not,
        # so we don't leak connections.
        cursor.close()
        release_connection(conn)

    # Also update the fast, in-memory copy of the leaderboard in Redis.
    sync_redis_client.zadd(LEADERBOARD_KEY, {str(user_id): return_pct})


def _mark_trade_failed(cursor, trade_id: str) -> None:
    """Small helper: flips a trade's status to 'failed' and stamps when that happened."""
    cursor.execute(
        "UPDATE trades SET status = 'failed', executed_at = NOW() WHERE trade_id = %s",
        (trade_id,)
    )


def execute_trade(trade: dict, current_price: float) -> bool:
    """
    This is where the actual buying/selling happens against Postgres.

    Steps:
      1. Make sure we haven't already processed this exact trade before (see below).
      2. Check the user has enough cash (buy) or enough shares (sell).
      3. Update their cash balance and their holdings.
      4. Mark the trade as completed (or failed).
      5. Recalculate their overall return % and update the leaderboard.

    Returns True if the trade went through, False if it failed for a normal
    reason (not enough money/shares, user missing, etc).
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # --- Step 1: don't process the same trade twice ---
        # SQS can deliver the same message more than once, and our retry logic
        # can also call this function again after a partial failure. Without
        # this check, we'd double-charge or double-credit the same trade.
        # "FOR UPDATE" locks this row so no other worker can grab it at the
        # same time — like putting a temporary "do not touch" sign on it.
        cursor.execute("SELECT status FROM trades WHERE trade_id = %s FOR UPDATE", (trade['trade_id'],))
        trade_row = cursor.fetchone()
        if trade_row is None:
            # Shouldn't normally happen — the API should always insert the row first.
            logger.error(f"Trade {trade['trade_id']} not found in trades table")
            conn.commit()
            return False
        if trade_row['status'] != 'pending':
            # We've already finished this trade before (completed or failed).
            # Treat it as "done" so the caller doesn't retry it again.
            logger.info(f"Trade {trade['trade_id']} already {trade_row['status']}, skipping re-execution")
            conn.commit()
            return True

        # --- Step 2: look up the user's current cash balance ---
        # Also locked with FOR UPDATE so two trades for the same user can't
        # run at the same time and step on each other.
        cursor.execute("SELECT balance FROM users WHERE id = %s FOR UPDATE", (trade['user_id'],))
        user = cursor.fetchone()
        if user is None:
            logger.error(f"User {trade['user_id']} not found for trade {trade['trade_id']}")
            _mark_trade_failed(cursor, trade['trade_id'])
            conn.commit()
            return False

        balance = float(user['balance'])
        cost = current_price * trade['quantity']  # total dollar amount this trade is worth

        # Look up what the user currently holds of this stock (if anything).
        cursor.execute(
            "SELECT quantity, avg_price FROM holdings WHERE user_id = %s AND symbol = %s FOR UPDATE",
            (trade['user_id'], trade['symbol'])
        )
        holding = cursor.fetchone()

        if trade['direction'] == 'buy':
            # Can't buy more than you can afford.
            if balance < cost:
                logger.error(f"Insufficient balance for trade {trade['trade_id']}: has {balance}, needs {cost}")
                _mark_trade_failed(cursor, trade['trade_id'])
                conn.commit()
                return False

            new_balance = balance - cost  # spend the cash

            if holding is None:
                # First time buying this stock — create a new holdings row.
                cursor.execute(
                    "INSERT INTO holdings (user_id, symbol, quantity, avg_price) VALUES (%s, %s, %s, %s)",
                    (trade['user_id'], trade['symbol'], trade['quantity'], current_price)
                )
            else:
                # Already own some — blend the old and new price into a new
                # "average cost per share", like averaging two purchase prices together.
                new_quantity = holding['quantity'] + trade['quantity']
                new_avg_price = ((holding['quantity'] * float(holding['avg_price'])) + cost) / new_quantity
                cursor.execute(
                    "UPDATE holdings SET quantity = %s, avg_price = %s, updated_at = NOW() WHERE user_id = %s AND symbol = %s",
                    (new_quantity, new_avg_price, trade['user_id'], trade['symbol'])
                )

        else:  # direction == 'sell'
            # Can't sell shares you don't have.
            if holding is None or holding['quantity'] < trade['quantity']:
                logger.error(f"Insufficient holdings for trade {trade['trade_id']}")
                _mark_trade_failed(cursor, trade['trade_id'])
                conn.commit()
                return False

            new_balance = balance + cost  # selling adds cash back
            new_quantity = holding['quantity'] - trade['quantity']

            if new_quantity == 0:
                # Sold everything — remove the holding entirely instead of
                # leaving a row that says "0 shares".
                cursor.execute(
                    "DELETE FROM holdings WHERE user_id = %s AND symbol = %s",
                    (trade['user_id'], trade['symbol'])
                )
            else:
                # Still holding some — just reduce the quantity.
                # Note: avg_price doesn't change on a sell, only on a buy.
                cursor.execute(
                    "UPDATE holdings SET quantity = %s, updated_at = NOW() WHERE user_id = %s AND symbol = %s",
                    (new_quantity, trade['user_id'], trade['symbol'])
                )

        # --- Step 3 & 4: save the new balance and mark the trade done ---
        cursor.execute("UPDATE users SET balance = %s WHERE id = %s", (new_balance, trade['user_id']))
        cursor.execute(
            "UPDATE trades SET status = 'completed', executed_at = NOW() WHERE trade_id = %s",
            (trade['trade_id'],)
        )

        # Add up the value of everything this user currently holds, so we can
        # work out their total portfolio value (cash + stocks).
        cursor.execute(
            "SELECT COALESCE(SUM(quantity * avg_price), 0) AS holdings_value FROM holdings WHERE user_id = %s",
            (trade['user_id'],)
        )
        holdings_value = float(cursor.fetchone()['holdings_value'])

        # Everything above happens in one database transaction — commit it now
        # so it's all saved together, or none of it is (if something failed).
        conn.commit()

        # --- Step 5: work out the user's overall gain/loss % and update the leaderboard ---
        total_value = new_balance + holdings_value
        return_pct = ((total_value - STARTING_BALANCE) / STARTING_BALANCE) * 100
        _update_leaderboard(trade['user_id'], return_pct)

        return True  # trade succeeded

    except Exception as e:
        # Something unexpected went wrong (e.g. a DB connection hiccup).
        # Undo any half-finished changes so we don't leave the database in a
        # weird in-between state.
        conn.rollback()
        logger.error(f"Error executing trade {trade['trade_id']}: {e}")
        return False

    finally:
        # Always release the DB connection back to the pool, success or failure.
        cursor.close()
        release_connection(conn)


def process_trade(trade: dict) -> bool:
    """
    Takes one trade message (already pulled off the SQS queue) and runs it
    through validation, price lookup, and execution.

    Returns True if everything worked, False if it failed for any reason
    (bad input, bad price, or execute_trade() failing).
    """

    try:

        # Log what we're about to do, so we can trace it later if something goes wrong.
        logger.info(f"Processing: {trade['symbol']} {trade['quantity']} {trade['direction']}")

        # Basic sanity checks before we do anything expensive (like calling an
        # external price API). Reject obviously broken trades early.
        if trade['quantity'] <= 0 or trade['direction'] not in ['buy', 'sell'] or not trade['symbol'] or trade['quantity'] >= 10000:
            logger.error(f"Invalid trade quantity: {trade['quantity']} for trade {trade}")
            return False

        # Ask Yahoo Finance what this stock is trading at right now.
        # fast_info is a lighter/quicker version of the full ticker info.
        ticker = yf.Ticker(trade['symbol'])
        current_price = ticker.fast_info.last_price

        if current_price is None:
            # Symbol might be invalid, or the price API is having issues.
            logger.error(f"Could not fetch price for {trade['symbol']}")
            return False

        # Now actually do the money-moving part.
        if not execute_trade(trade, current_price):
            return False

        # We used to explicitly clear this user's cached portfolio here so the
        # next page load would show fresh numbers. That call was async and
        # this worker is sync, and mixing the two caused crashes. Instead, we
        # just let the cache's own 60-second TTL (set in portfolio.py) expire
        # naturally — the user's portfolio view will be at most 60s stale.
        logger.info(f"Trade executed — portfolio cache will expire naturally for user {trade['user_id']}")

        return True  # everything worked

    except Exception as e:
        # Catch-all safety net so one bad trade can't crash the whole worker loop.
        logger.error(f"Error processing trade {trade}: {e}")
        return False


def poll_and_process():
    """
    The main loop of the worker. Runs forever:
      1. Ask SQS "any new trade messages for me?"
      2. For each one, try to process it (with retries on failure).
      3. If it succeeded, delete it from the queue so it's not processed again.
      4. If it failed even after retries, leave it in the queue so SQS will
         redeliver it later for another attempt.
    """
    logger.info("Trade processor started. Polling SQS for messages...")
    while True:
        try:
            # Long-poll SQS: wait up to 20 seconds for messages instead of
            # hammering it with requests every second. Grab up to 10 at once.
            # VisibilityTimeout=300 means: once we grab a message, hide it from
            # other workers for 5 minutes while we work on it.
            response = sqs.receive_message(
                QueueUrl=settings.sqs_queue_url,
                MaxNumberOfMessages=10,
                WaitTimeSeconds=20,
                VisibilityTimeout=300
            )

            messages = response.get("Messages", [])
            for message in messages:
                body = json.loads(message["Body"])  # the actual trade data, as a dict
                receipt = message["ReceiptHandle"]   # a ticket we need to "delete" this message later

                # with_retry will call this function up to a few times if it
                # keeps failing, with a short pause growing between attempts
                # (exponential backoff) — useful for temporary glitches like a
                # slow network call to the price API.
                #
                # process_trade() tells us "did it work?" by returning
                # True/False rather than raising an error. with_retry only
                # understands errors, so this little wrapper turns a "False"
                # into an actual exception it can catch and retry on.
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
                    # Ran out of retries, or something permanent went wrong.
                    # We deliberately do NOT delete the message here — leaving
                    # it in the queue means SQS will offer it to us again
                    # later in case the problem was temporary.
                    success = False

                if success:
                    # Tell SQS "I'm done with this one, you can throw it away".
                    sqs.delete_message(
                        QueueUrl=settings.sqs_queue_url,
                        ReceiptHandle=receipt
                    )
                    logger.info("Trade processed and deleted")
                else:
                    logger.warning("Trade failed — will retry")
        except Exception as e:
            # Something went wrong just talking to SQS itself (network blip, etc).
            # Wait a bit before trying again instead of spinning in a tight loop.
            logger.error(f"Polling error: {e}")
            time.sleep(5)


if __name__ == "__main__":
    # This only runs when you execute this file directly
    # (e.g. `python -m app.workers.trade_processor`), not when it's imported.
    poll_and_process()
