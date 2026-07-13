# app/exceptions.py
# all custom exceptions in one place
# imported by workers, services, and routes

class PermanentFailure(Exception):
    """
    Raised when an operation cannot succeed on retry.
    Signals: stop retrying, route to DLQ for investigation.
    Used across workers, HTTP clients, and service calls.
    """
    pass


class InsufficientFundsError(PermanentFailure):
    """
    User does not have enough cash balance to buy.
    Example: buying $10,000 of AAPL with $500 balance.
    Never retryable -- balance does not change between retries.
    """
    pass


class InsufficientSharesError(PermanentFailure):
    """
    User is trying to sell more shares than they own.
    Example: selling 1000 AAPL when user owns 50.
    Never retryable.
    """
    pass


class InvalidSymbolError(PermanentFailure):
    """
    Stock symbol does not exist or is no longer traded.
    Example: trading a delisted company.
    Never retryable -- symbol does not become valid on retry.
    """
    pass


class StaleTradeError(PermanentFailure):
    """
    Trade was submitted too long ago to execute safely.
    Example: trade sitting in queue for 6+ days.
    Market conditions have changed, submitted price is invalid.
    Never retryable -- age does not decrease on retry.
    """
    pass


class ExchangeRejectedError(PermanentFailure):
    """
    Exchange API returned a 4xx error rejecting the trade.
    Example: trade violates exchange rules, market is closed.
    Never retryable -- exchange will reject again for same reason.
    """
    pass