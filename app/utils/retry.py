import time
import logging
from app.exceptions import PermanentFailure

logger = logging.getLogger("retry") 

def with_retry(func, max_retries=3, base_delay=1.0,
               operation_name="operation"):
    for attempt in range(max_retries):
        try:
            return func()

        except PermanentFailure as e:
            # catches ALL subclasses:
            # InsufficientFundsError, InsufficientSharesError,
            # InvalidSymbolError, StaleTradeError,
            # ExchangeRejectedError
            # all of them stop immediately, no retry
            logger.error(f"{operation_name} permanent: {e}")
            raise

        except Exception as e:
            # transient -- network error, 5xx, timeout
            if attempt == max_retries - 1:
                logger.error(f"{operation_name} exhausted: {e}")
                raise
            delay = base_delay * (2 ** attempt)
            logger.warning(f"Retry {attempt+1} in {delay}s: {e}")
            time.sleep(delay)