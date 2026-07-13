import boto3, json, time, logging
import asyncio
import yfinance as yf
from app.config import settings
from app.services.cache import invalidate_cache
from app.utils.retry import with_retry


logger = logging.getLogger("trade_processor") # Configure a logger for the trade processor to log messages and errors

sqs = boto3.client(
    'sqs',
    aws_access_key_id=settings.aws_access_key_id,
    aws_secret_access_key=settings.aws_secret_access_key,
    region_name=settings.aws_region
)

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

        # Check user has sufficient virtual balance
        # Execute trade — update holdings, deduct balance, write trade record

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