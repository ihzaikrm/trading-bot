class SynclavixError(Exception):
    """Base exception for Synclavix."""
    pass

class DataFetchError(SynclavixError):
    """Raised when market data cannot be fetched."""
    pass

class LLMError(SynclavixError):
    """Raised when LLM call fails."""
    pass

class RiskLimitExceeded(SynclavixError):
    """Raised when circuit breaker or risk limits are triggered."""
    pass

class OrderExecutionError(SynclavixError):
    """Raised when order placement fails."""
    pass

class StateRecoveryError(SynclavixError):
    """Raised when checkpoint loading fails."""
    pass
